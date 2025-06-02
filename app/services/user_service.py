from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from app.database.models import User, RegistrationSession, UserRole
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class UserService:
    """Сервис для управления пользователями"""

    async def create_user(self, db: AsyncSession, user_data: Dict[str, Any]) -> User:
        """Создание нового пользователя"""
        user = User(**user_data)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    async def get_user_by_telegram_id(self, db: AsyncSession, telegram_id: int) -> Optional[User]:
        """Получение пользователя по telegram_id"""
        result = await db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def update_user(self, db: AsyncSession, user_id: str, updates: Dict[str, Any]) -> Optional[User]:
        """Обновление данных пользователя"""
        await db.execute(
            update(User).where(User.id == user_id).values(**updates)
        )
        await db.commit()
        return await self.get_user_by_id(db, user_id)

    async def get_user_by_id(self, db: AsyncSession, user_id: str) -> Optional[User]:
        """Получение пользователя по ID"""
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()


class RegistrationService:
    """Сервис для управления регистрацией пользователей"""

    REGISTRATION_STEPS = [
        'first_name', 'last_name', 'telegram_username',
        'phone', 'email', 'domain_login', 'confirm'
    ]

    STEP_PROMPTS = {
        'first_name': 'Введите имя:',
        'last_name': 'Введите фамилию:',
        'telegram_username': 'Введите username в Telegram (без @):',
        'phone': 'Введите номер телефона:',
        'email': 'Введите email:',
        'domain_login': 'Введите доменный логин:',
        'confirm': 'Подтвердите данные'
    }

    async def start_registration(self, db: AsyncSession, telegram_id: int, chat_id: int) -> RegistrationSession:
        """Начало процесса регистрации"""
        # Удаляем существующие сессии
        await db.execute(
            delete(RegistrationSession).where(RegistrationSession.telegram_id == telegram_id)
        )

        # Создаем новую сессию
        session = RegistrationSession(
            telegram_id=telegram_id,
            chat_id=chat_id,
            current_step='first_name',
            session_data={},
            expires_at=datetime.utcnow() + timedelta(minutes=30)
        )

        db.add(session)
        await db.commit()
        await db.refresh(session)

        return session

    async def get_registration_session(self, db: AsyncSession, telegram_id: int) -> Optional[RegistrationSession]:
        """Получение активной сессии регистрации"""
        result = await db.execute(
            select(RegistrationSession).where(
                RegistrationSession.telegram_id == telegram_id,
                RegistrationSession.expires_at > datetime.utcnow()
            )
        )
        return result.scalar_one_or_none()

    async def process_registration_step(self, db: AsyncSession, telegram_id: int, user_input: str) -> Dict[str, Any]:
        """Обработка шага регистрации"""
        session = await self.get_registration_session(db, telegram_id)

        if not session:
            return {'status': 'error', 'message': 'Сессия регистрации не найдена или истекла'}

        current_step = session.current_step

        # Валидация ввода
        validation_result = self._validate_input(current_step, user_input)
        if not validation_result['valid']:
            return {
                'status': 'error',
                'message': validation_result['message'],
                'prompt': self.STEP_PROMPTS[current_step]
            }

        # Сохранение данных
        session.session_data[current_step] = user_input

        # Переход к следующему шагу
        current_index = self.REGISTRATION_STEPS.index(current_step)
        if current_index < len(self.REGISTRATION_STEPS) - 1:
            next_step = self.REGISTRATION_STEPS[current_index + 1]
            session.current_step = next_step
            await db.commit()

            if next_step == 'confirm':
                return {
                    'status': 'confirm',
                    'message': self._format_confirmation_message(session.session_data),
                    'data': session.session_data
                }
            else:
                return {
                    'status': 'continue',
                    'message': self.STEP_PROMPTS[next_step],
                    'step': next_step
                }
        else:
            # Завершение регистрации
            return await self._complete_registration(db, session)

    async def confirm_registration(self, db: AsyncSession, telegram_id: int) -> Dict[str, Any]:
        """Подтверждение регистрации"""
        session = await self.get_registration_session(db, telegram_id)

        if not session:
            return {'status': 'error', 'message': 'Сессия регистрации не найдена'}

        return await self._complete_registration(db, session)

    async def _complete_registration(self, db: AsyncSession, session: RegistrationSession) -> Dict[str, Any]:
        """Завершение процесса регистрации"""
        try:
            # Создание пользователя
            user_data = {
                'telegram_id': session.telegram_id,
                'first_name': session.session_data.get('first_name'),
                'last_name': session.session_data.get('last_name'),
                'telegram_username': session.session_data.get('telegram_username'),
                'phone': session.session_data.get('phone'),
                'email': session.session_data.get('email'),
                'domain_login': session.session_data.get('domain_login'),
                'role': UserRole.USER,
                'is_registered': True,
                'ldap_verified': False
            }

            user = User(**user_data)
            db.add(user)

            # Удаление сессии регистрации
            await db.delete(session)

            await db.commit()

            return {
                'status': 'success',
                'message': f'Пользователь {user.first_name} {user.last_name} успешно зарегистрирован!',
                'user': user
            }

        except Exception as e:
            logger.error(f"Ошибка завершения регистрации: {e}")
            await db.rollback()
            return {'status': 'error', 'message': 'Ошибка при регистрации пользователя'}

    def _validate_input(self, step: str, user_input: str) -> Dict[str, Any]:
        """Валидация пользовательского ввода"""
        user_input = user_input.strip()

        if not user_input:
            return {'valid': False, 'message': 'Поле не может быть пустым'}

        if step == 'email':
            if '@' not in user_input or '.' not in user_input:
                return {'valid': False, 'message': 'Некорректный формат email'}

        elif step == 'phone':
            # Простая валидация номера телефона
            if len(user_input.replace('+', '').replace('-', '').replace(' ', '')) < 10:
                return {'valid': False, 'message': 'Некорректный формат номера телефона'}

        elif step in ['first_name', 'last_name']:
            if len(user_input) < 2:
                return {'valid': False, 'message': 'Слишком короткое значение'}

        return {'valid': True}

    def _format_confirmation_message(self, data: Dict[str, str]) -> str:
        """Форматирование сообщения подтверждения"""
        return f"""Проверьте введенные данные:

👤 Имя: {data.get('first_name')}
👤 Фамилия: {data.get('last_name')}
📱 Telegram: @{data.get('telegram_username', 'не указан')}
📞 Телефон: {data.get('phone', 'не указан')}
📧 Email: {data.get('email', 'не указан')}
💻 Доменный логин: {data.get('domain_login', 'не указан')}

Все верно? Отправьте "да" для подтверждения или "нет" для отмены."""
