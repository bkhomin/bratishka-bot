import asyncio
import logging
import sys
import signal
from app.telegram.bot import BratishkaBot
from app.database.connection import init_db
from app.config import Config

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bratishka_agent.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Отключаем избыточное логирование
logging.getLogger('telegram').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('asyncio').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


class BratishkaApp:
    """Главное приложение"""

    def __init__(self):
        self.bot = None
        self.running = False

    async def startup(self):
        """Запуск приложения"""
        logger.info("🚀 Запуск Bratishka AI Agent...")

        try:
            # Валидация конфигурации
            config_errors = Config.validate()
            if config_errors:
                for error in config_errors:
                    logger.error(f"❌ {error}")
                sys.exit(1)

            # Инициализация базы данных
            await init_db()

            # Создание и инициализация бота
            self.bot = BratishkaBot()
            await self.bot.initialize()

            logger.info("✅ Bratishka AI Agent успешно запущен")
            self.running = True

            # Запуск бота
            await self.bot.start_polling()

        except Exception as e:
            logger.error(f"💥 Критическая ошибка: {e}")
            await self.shutdown()
            sys.exit(1)

    async def shutdown(self):
        """Завершение работы"""
        if self.running:
            logger.info("🛑 Завершение работы Bratishka AI Agent...")

            if self.bot:
                await self.bot.stop()

            self.running = False
            logger.info("✅ Bratishka AI Agent остановлен")

    def setup_signal_handlers(self):
        """Настройка обработчиков сигналов"""

        def signal_handler(signum, frame):
            logger.info(f"📡 Получен сигнал {signum}")
            asyncio.create_task(self.shutdown())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Главная функция"""
    app = BratishkaApp()
    app.setup_signal_handlers()

    try:
        await app.startup()
    except KeyboardInterrupt:
        logger.info("⌨️ Получен сигнал остановки от клавиатуры")
    finally:
        await app.shutdown()


if __name__ == "__main__":
    # Настройка для разных платформ
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🔚 Программа завершена")
