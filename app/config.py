import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

# Загружаем .env файл из корня проекта
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, '.env')

if os.path.exists(env_path):
    load_dotenv(env_path)
    print(f"✅ Загружен .env файл: {env_path}")
else:
    print(f"⚠️ .env файл не найден: {env_path}")
    print("Создайте .env файл в корне проекта или установите переменные окружения")


class Config:
    # LLM настройки
    LLAMA_MODEL_PATH = os.getenv("LLAMA_MODEL_PATH")
    LLAMA_N_CTX = int(os.getenv("LLAMA_N_CTX", 8192))
    LLAMA_N_THREADS = int(os.getenv("LLAMA_N_THREADS", 8))
    LLAMA_TEMPERATURE = float(os.getenv("LLAMA_TEMPERATURE", 0.6))
    LLAMA_TOP_P = float(os.getenv("LLAMA_TOP_P", 0.95))

    # Database components
    DATABASE_HOST = os.getenv("DATABASE_HOST", "localhost")
    DATABASE_PORT = int(os.getenv("DATABASE_PORT", 5432))
    DATABASE_NAME = os.getenv("DATABASE_NAME")
    DATABASE_USER = os.getenv("DATABASE_USER")
    DATABASE_USER_PASSWORD = os.getenv("DATABASE_USER_PASSWORD")

    DATABASE_POOL_SIZE = int(os.getenv("DATABASE_POOL_SIZE", 20))
    DATABASE_MAX_OVERFLOW = int(os.getenv("DATABASE_MAX_OVERFLOW", 30))

    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "bratishka")

    # LDAP (опционально)
    LDAP_SERVER = os.getenv("LDAP_SERVER")
    LDAP_BASE_DN = os.getenv("LDAP_BASE_DN")
    LDAP_BIND_DN = os.getenv("LDAP_BIND_DN")
    LDAP_BIND_PASSWORD = os.getenv("LDAP_BIND_PASSWORD")
    LDAP_USER_SEARCH_BASE = os.getenv("LDAP_USER_SEARCH_BASE")
    LDAP_USER_SEARCH_FILTER = os.getenv("LDAP_USER_SEARCH_FILTER", "(telegramId={telegram_id})")

    # Email
    EMAIL_HOST = os.getenv("EMAIL_HOST")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
    EMAIL_USER = os.getenv("EMAIL_USER")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

    # Performance
    MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", 10))
    MESSAGE_CACHE_SIZE = int(os.getenv("MESSAGE_CACHE_SIZE", 1000))
    CONTEXT_CACHE_TTL = int(os.getenv("CONTEXT_CACHE_TTL", 3600))

    # Agent settings
    DEFAULT_SUMMARY_HOURS = int(os.getenv("DEFAULT_SUMMARY_HOURS", 24))
    REGISTRATION_SESSION_TIMEOUT = int(os.getenv("REGISTRATION_SESSION_TIMEOUT", 30))
    BOT_NAME = os.getenv("BOT_NAME", "bratishka")

    @classmethod
    def get_database_url(self) -> str:
        """Собирает DATABASE_URL из компонентов"""
        if not all([self.DATABASE_USER, self.DATABASE_USER_PASSWORD, self.DATABASE_HOST, self.DATABASE_NAME]):
            return ""

        # Экранируем специальные символы в пароле
        password = quote_plus(self.DATABASE_USER_PASSWORD)
        user = quote_plus(self.DATABASE_USER)

        return f"postgresql://{user}:{password}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"

    @classmethod
    def validate(cls) -> list[str]:
        """Валидация обязательных настроек"""
        errors = []

        config_instance = cls()

        if not config_instance.LLAMA_MODEL_PATH:
            errors.append("LLAMA_MODEL_PATH не установлен")

        # Проверяем компоненты DATABASE_URL
        if not config_instance.DATABASE_NAME:
            errors.append("DATABASE_NAME не установлен")
        if not config_instance.DATABASE_USER:
            errors.append("DATABASE_USER не установлен")
        if not config_instance.DATABASE_USER_PASSWORD:
            errors.append("DATABASE_USER_PASSWORD не установлен")
        if not config_instance.DATABASE_HOST:
            errors.append("DATABASE_HOST не установлен")

        if not config_instance.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN не установлен")

        return errors

    @classmethod
    def is_ldap_enabled(cls) -> bool:
        """Проверка включен ли LDAP (исправлена property ошибка)"""
        return bool(cls.LDAP_SERVER)

    @classmethod
    def print_debug_info(cls):
        """Отладочная информация о конфигурации"""
        print("\n" + "=" * 50)
        print("🔧 КОНФИГУРАЦИЯ BRATISHKA")
        print("=" * 50)

        print(f"📂 Корень проекта: {project_root}")
        print(f"📄 .env файл: {env_path}")
        print(f"📄 .env существует: {os.path.exists(env_path)}")

        print("\n📊 ОСНОВНЫЕ НАСТРОЙКИ:")
        print(f"DATABASE_URL: {'✅ установлен' if cls.DATABASE_URL else '❌ не установлен'}")
        print(f"TELEGRAM_BOT_TOKEN: {'✅ установлен' if cls.TELEGRAM_BOT_TOKEN else '❌ не установлен'}")
        print(f"LLAMA_MODEL_PATH: {cls.LLAMA_MODEL_PATH or '❌ не установлен'}")

        if cls.LLAMA_MODEL_PATH:
            print(f"Модель существует: {'✅' if os.path.exists(cls.LLAMA_MODEL_PATH) else '❌'}")

        print(f"\n📧 EMAIL настройки:")
        print(f"EMAIL_HOST: {cls.EMAIL_HOST or '❌ не установлен'}")
        print(f"EMAIL_USER: {'✅ установлен' if cls.EMAIL_USER else '❌ не установлен'}")

        print(f"\n🔗 LDAP: {'✅ включен' if cls.is_ldap_enabled() else '❌ отключен'}")

        print("=" * 50)


# Печатаем отладочную информацию при импорте модуля
if __name__ == "__main__" or os.getenv("DEBUG_CONFIG"):
    Config.print_debug_info()
