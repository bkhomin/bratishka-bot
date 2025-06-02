import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import Config
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()


def get_database_url():
    """Безопасное получение DATABASE_URL с проверками"""
    database_url = Config.DATABASE_URL

    if not database_url:
        # Fallback URL для разработки
        logger.warning("DATABASE_URL не установлен, используется fallback для разработки")
        return None

    # Определяем драйвер
    if "asyncpg" in database_url:
        return database_url
    elif "psycopg" in database_url:
        return database_url
    else:
        # По умолчанию добавляем asyncpg
        if database_url.startswith("postgresql://"):
            return database_url.replace("postgresql://", "postgresql+asyncpg://")
        else:
            return database_url


# Получаем URL с проверками
try:
    database_url = get_database_url()
    logger.info(f"Используется DATABASE_URL: {database_url.split('@')[0]}@***")
except Exception as e:
    logger.error(f"Ошибка получения DATABASE_URL: {e}")
    database_url = "postgresql+asyncpg://postgres:password@localhost:5432/bratishka_agent"

# Создаем движок только если URL корректный
engine = None
async_session = None

try:
    # Оптимизированный движок
    engine = create_async_engine(
        database_url,
        echo=False,
        pool_size=Config.DATABASE_POOL_SIZE,
        max_overflow=Config.DATABASE_MAX_OVERFLOW,
        pool_pre_ping=True,
        pool_recycle=3600,
    )

    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    logger.info("✅ SQLAlchemy движок создан успешно")

except Exception as e:
    logger.error(f"❌ Ошибка создания SQLAlchemy движка: {e}")
    print(f"❌ Ошибка базы данных: {e}")
    print("Проверьте DATABASE_URL в .env файле")


async def get_db():
    """Dependency для получения сессии базы данных"""
    if not async_session:
        raise RuntimeError("База данных не инициализирована")

    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Инициализация базы данных"""
    if not engine:
        raise RuntimeError("Движок базы данных не создан")

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ База данных инициализирована")
    except Exception as e:
        logger.error(f"❌ Ошибка инициализации базы данных: {e}")
        raise


class DatabaseManager:
    """Простой менеджер для выполнения raw SQL запросов"""

    def __init__(self):
        self.engine = engine

    async def execute_query(self, query: str, *args):
        """Выполнение запроса через SQLAlchemy"""
        if not self.engine:
            raise RuntimeError("База данных не инициализирована")

        async with async_session() as session:
            try:
                result = await session.execute(query, args)
                await session.commit()
                return result.fetchall()
            except Exception as e:
                await session.rollback()
                raise

    async def execute_command(self, query: str, *args):
        """Выполнение команды через SQLAlchemy"""
        if not self.engine:
            raise RuntimeError("База данных не инициализирована")

        async with async_session() as session:
            try:
                result = await session.execute(query, args)
                await session.commit()
                return result.rowcount
            except Exception as e:
                await session.rollback()
                raise

    async def init_pool(self):
        """Заглушка для совместимости"""
        if self.engine:
            logger.info("✅ Используется SQLAlchemy пул соединений")
        else:
            raise RuntimeError("Движок базы данных не создан")

    async def close_pool(self):
        """Закрытие пула"""
        if self.engine:
            await self.engine.dispose()
            logger.info("✅ Пул соединений закрыт")

    async def test_connection(self):
        """Тестирование соединения с базой данных"""
        if not self.engine:
            raise RuntimeError("Движок базы данных не создан")

        try:
            async with self.engine.connect() as conn:
                result = await conn.execute("SELECT 1")
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Ошибка тестирования соединения: {e}")
            return False


# Глобальный экземпляр менеджера
db_manager = DatabaseManager()
