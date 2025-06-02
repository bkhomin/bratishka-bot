import logging
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import user_cache, make_cache_key
from app.database.models import User, UserRole
from app.services.ldap_service import LDAPService

logger = logging.getLogger(__name__)


class AuthService:
    """Оптимизированный сервис аутентификации"""

    def __init__(self, ldap_service: Optional[LDAPService]):
        self.ldap_service = ldap_service

    async def authenticate_user(self, db: AsyncSession, telegram_id: int) -> Optional[User]:
        """Аутентификация с кешированием"""
        # Проверяем кеш
        cache_key = make_cache_key("user_auth", telegram_id)
        cached_user = await user_cache.get(cache_key)
        if cached_user:
            return cached_user

        try:
            # Поиск в БД с join для роли
            result = await db.execute(
                select(User, UserRole)
                .join(UserRole, User.role_id == UserRole.id)
                .where(User.telegram_id == telegram_id)
            )

            row = result.first()
            if row:
                user, role = row
                user.role_name = role.name  # Добавляем имя роли

                # Кешируем результат
                await user_cache.set(cache_key, user, ttl=900)  # 15 минут

                logger.info(f"Пользователь найден в БД: {user.telegram_id}")
                return user

            # Поиск в LDAP если включен
            if self.ldap_service:
                ldap_user = await self.ldap_service.find_user_by_telegram_id(telegram_id)

                if ldap_user:
                    user = await self._create_user_from_ldap(db, ldap_user, telegram_id)
                    await user_cache.set(cache_key, user, ttl=900)
                    logger.info(f"Пользователь создан из LDAP: {telegram_id}")
                    return user

            logger.warning(f"Пользователь не найден: {telegram_id}")
            return None

        except Exception as e:
            logger.error(f"Ошибка аутентификации пользователя {telegram_id}: {e}")
            return None

    async def _create_user_from_ldap(self, db: AsyncSession, ldap_user: dict, telegram_id: int) -> User:
        """Создание пользователя из LDAP"""
        user = User(
            first_name=ldap_user.get("givenName", "").strip() or "Unknown",
            last_name=ldap_user.get("sn", "").strip() or "User",
            telegram_id=telegram_id,
            telegram_username=ldap_user.get("telegramUsername"),
            phone=ldap_user.get("telephoneNumber"),
            email=ldap_user.get("mail"),
            domain_login=ldap_user.get("sAMAccountName"),
            role_id=1,  # По умолчанию роль 'user'
            is_registered=True,
            ldap_verified=True
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)

        return user

    async def is_admin(self, db: AsyncSession, telegram_id: int) -> bool:
        """Проверка прав администратора"""
        cache_key = make_cache_key("user_admin", telegram_id)
        cached_result = await user_cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        try:
            result = await db.execute(
                select(User, UserRole)
                .join(UserRole, User.role_id == UserRole.id)
                .where(
                    User.telegram_id == telegram_id,
                    UserRole.name == "admin"
                )
            )

            is_admin = result.first() is not None

            # Кешируем результат
            await user_cache.set(cache_key, is_admin, ttl=1800)  # 30 минут

            return is_admin

        except Exception as e:
            logger.error(f"Ошибка проверки прав администратора {telegram_id}: {e}")
            return False

    async def check_access(self, db: AsyncSession, telegram_id: int) -> Tuple[Optional[User], str]:
        """Проверка доступа пользователя"""
        user = await self.authenticate_user(db, telegram_id)

        if user:
            return user, "authenticated"
        else:
            return None, "❌ Доступ запрещен. Обратитесь к администратору"

    async def invalidate_user_cache(self, telegram_id: int):
        """Инвалидация кеша пользователя"""
        auth_key = make_cache_key("user_auth", telegram_id)
        admin_key = make_cache_key("user_admin", telegram_id)

        await user_cache.delete(auth_key)
        await user_cache.delete(admin_key)
