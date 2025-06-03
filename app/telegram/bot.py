"""
Основной класс Telegram бота
"""
import signal
import sys
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from app.config.settings import config
from app.config.logging import get_logger
from app.services.chroma_service import ChromaService
from app.services.llm_service import LLMService
from app.telegram.handlers import TelegramHandlers

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
        self._running = False

        # Настройка graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Обработчик сигналов для graceful shutdown"""
        logger.info(f"Получен сигнал {signum}, завершаем работу...")
        self._running = False
        sys.exit(0)

    async def initialize(self):
        """Инициализация всех компонентов бота"""
        try:
            logger.info("Инициализация компонентов бота...")

            # Инициализируем ChromaDB первым
            self.chroma_service = ChromaService()

            # Создаем приложение Telegram с увеличенными таймаутами
            self.application = Application.builder().token(
                self.config.telegram.token
            ).connect_timeout(30.0).read_timeout(20.0).write_timeout(20.0).build()

            # Инициализируем обработчики с placeholder LLM
            self.handlers = TelegramHandlers(
                chroma_service=self.chroma_service,
                llm_service=None,  # Пока None
                bot_username=self.config.telegram.username,
                default_time_hours=self.config.telegram.default_time_hours
            )

            # Регистрируем обработчики
            self._register_handlers()

            # Проверяем здоровье ChromaDB
            if not self.chroma_service.health_check():
                raise RuntimeError("ChromaDB недоступен")

            logger.info("Основные компоненты инициализированы успешно")

            # Инициализируем LLM асинхронно
            try:
                logger.info("Попытка инициализации LLM...")
                self.llm_service = LLMService()
                self.handlers.llm_service = self.llm_service
                logger.info("LLM сервис инициализирован")
            except Exception as e:
                logger.error(f"Ошибка инициализации LLM: {e}")
                logger.info("Бот будет работать без LLM функций")

        except Exception as e:
            logger.error(f"Ошибка при инициализации: {e}")
            raise

    def _register_handlers(self):
        """Регистрация обработчиков сообщений"""
        logger.info("Регистрация обработчиков...")

        # Обработчик ошибок
        async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
            """Обработчик ошибок"""
            logger.error(f"Exception while handling an update: {context.error}")

            # Пытаемся отправить сообщение об ошибке пользователю
            if isinstance(update, Update) and update.effective_message:
                try:
                    await update.effective_message.reply_text(
                        "❌ Произошла ошибка при обработке команды. Попробуйте позже."
                    )
                except Exception as e:
                    logger.error(f"Не удалось отправить сообщение об ошибке: {e}")

        self.application.add_error_handler(error_handler)

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

    async def run_async(self):
        """Асинхронный запуск бота"""
        try:
            await self.initialize()

            logger.info(f"Бот @{self.config.telegram.username} запущен и готов к работе!")

            # ИСПРАВЛЕННЫЙ запуск с обработкой ошибок
            try:
                await self.application.initialize()
                await self.application.start()
                await self.application.updater.start_polling(
                    allowed_updates=Update.ALL_TYPES,
                    drop_pending_updates=True
                )

                self._running = True
                logger.info("✅ Бот успешно запущен и ожидает сообщения!")

                # Ждем бесконечно с проверкой статуса
                while self._running:
                    await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Ошибка при запуске Telegram бота: {e}")
                logger.info("Возможные причины:")
                logger.info("1. Проблемы с интернет соединением")
                logger.info("2. Неверный TELEGRAM_BOT_TOKEN")
                logger.info("3. Telegram API недоступен")

                # Пытаемся запуститься без Telegram (только локальные функции)
                logger.info("Попытка запуска в автономном режиме...")
                self._running = True
                while self._running:
                    await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("Получено прерывание от пользователя")
            self._running = False
        except Exception as e:
            logger.error(f"Критическая ошибка в асинхронном режиме: {e}")
            raise
        finally:
            # ИСПРАВЛЕННОЕ корректное завершение
            await self._safe_shutdown()

    async def _safe_shutdown(self):
        """Безопасное завершение работы"""
        try:
            logger.info("Безопасное завершение работы...")

            if self.application and hasattr(self.application, 'updater'):
                try:
                    if self.application.updater.running:
                        await self.application.updater.stop()
                        logger.info("Updater остановлен")
                except Exception as e:
                    logger.warning(f"Ошибка при остановке updater: {e}")

                try:
                    await self.application.stop()
                    logger.info("Application остановлено")
                except Exception as e:
                    logger.warning(f"Ошибка при остановке application: {e}")

                try:
                    await self.application.shutdown()
                    logger.info("Application завершено")
                except Exception as e:
                    logger.warning(f"Ошибка при завершении application: {e}")

        except Exception as e:
            logger.error(f"Ошибка при безопасном завершении: {e}")

    def stop(self):
        """Остановка бота"""
        self._running = False
