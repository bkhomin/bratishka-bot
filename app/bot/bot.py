"""
Основной класс Telegram бота
"""
import signal
import sys
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from app.config.settings import config
from app.config.logging import get_logger
from app.services.chroma_service import ChromaService
from app.services.llm_service import LLMService
from app.bot.handlers import TelegramHandlers

logger = get_logger(__name__)


class TelegramBot:
    """Основной класс Telegram бота"""

    def __init__(self):
        """
        Инициализация бота
        """
        self.config = config
        self.application = None
        self.chroma_service = None
        self.llm_service = None
        self.handlers = None

        # Настройка graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Обработчик сигналов для graceful shutdown"""
        logger.info(f"Получен сигнал {signum}, завершаем работу...")
        self.stop()
        sys.exit(0)

    async def initialize(self):
        """Инициализация всех компонентов бота"""
        try:
            logger.info("Инициализация компонентов бота...")

            # Инициализируем сервисы
            self.chroma_service = ChromaService()
            self.llm_service = LLMService()

            # Инициализируем обработчики
            self.handlers = TelegramHandlers(
                chroma_service=self.chroma_service,
                llm_service=self.llm_service,
                bot_username=self.config.telegram.username,
                default_time_hours=self.config.telegram.default_time_hours
            )

            # Создаем приложение Telegram
            self.application = Application.builder().token(
                self.config.telegram.token
            ).build()

            # Регистрируем обработчики команд
            self._register_handlers()

            # Проверяем здоровье сервисов
            await self._health_check()

            logger.info("Инициализация завершена успешно")

        except Exception as e:
            logger.error(f"Ошибка при инициализации: {e}")
            raise

    def _register_handlers(self):
        """Регистрация обработчиков сообщений"""
        logger.info("Регистрация обработчиков...")

        # Команды
        self.application.add_handler(
            CommandHandler("start", self.handlers.start_command)
        )
        self.application.add_handler(
            CommandHandler("help", self.handlers.help_command)
        )
        self.application.add_handler(
            CommandHandler("stats", self.handlers.stats_command)
        )

        # Обработчик сообщений в группах
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP),
                self.handlers.process_message
            )
        )

        # Обработчик личных сообщений
        self.application.add_handler(
            MessageHandler(
                filters.TEXT & filters.ChatType.PRIVATE,
                self.handlers.start_command
            )
        )

        logger.info("Обработчики зарегистрированы")

    async def _health_check(self):
        """Проверка здоровья всех сервисов"""
        logger.info("Проверка здоровья сервисов...")

        # Проверяем ChromaDB
        if not self.chroma_service.health_check():
            raise RuntimeError("ChromaDB недоступен")

        # Проверяем LLM
        if not self.llm_service.health_check():
            raise RuntimeError("LLM недоступен")

        logger.info("Все сервисы работают корректно")

    def run(self):
        """Запуск бота"""
        try:
            logger.info(f"Запуск бота @{self.config.telegram.username}...")

            # Запускаем polling
            self.application.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )

        except Exception as e:
            logger.error(f"Ошибка при запуске бота: {e}")
            raise

    def stop(self):
        """Остановка бота"""
        try:
            logger.info("Остановка бота...")

            if self.application:
                self.application.stop()

            logger.info("Бот остановлен")

        except Exception as e:
            logger.error(f"Ошибка при остановке бота: {e}")

    async def run_async(self):
        """Асинхронный запуск бота"""
        try:
            await self.initialize()

            logger.info(f"Бот @{self.config.telegram.username} запущен и готов к работе!")

            # Запускаем бота
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True
            )

            # Ждем пока бот работает - ИСПРАВЛЕНО
            await self.application.updater.idle()

        except Exception as e:
            logger.error(f"Ошибка в асинхронном режиме: {e}")
            raise
        finally:
            # Корректное завершение
            if self.application:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
