"""
Обработчики сообщений Telegram бота
"""
from datetime import datetime, timedelta

from app.config.logging import get_logger
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from app.core.intent_recognizer import IntentRecognizer, Intent
from app.services.chroma_service import ChromaService
from app.services.llm_service import LLMService

logger = get_logger(__name__)


class TelegramHandlers:
    """Класс для обработки сообщений Telegram бота"""

    def __init__(
            self,
            chroma_service: ChromaService,
            llm_service: LLMService,
            bot_username: str,
            default_time_hours: int = 2
    ):
        """
        Инициализация обработчиков

        Args:
            chroma_service: Сервис ChromaDB
            llm_service: Сервис LLM
            bot_username: Имя бота
            default_time_hours: Часы по умолчанию для анализа
        """
        self.chroma_service = chroma_service
        self.llm_service = llm_service
        self.bot_username = bot_username.replace('@', '')
        self.default_time_hours = default_time_hours
        self.intent_recognizer = IntentRecognizer()

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        await update.message.reply_text(
            f"👋 Привет! Я @{self.bot_username} - бот для анализа переписки.\n\n"
            "🔹 Добавьте меня в чат и я начну сохранять сообщения\n"
            "🔹 Обращайтесь ко мне через @:\n\n"
            "Примеры:\n"
            f"• @{self.bot_username} о чём договорились?\n"
            f"• @{self.bot_username} сводку\n"
            f"• @{self.bot_username} что это было сейчас?\n"
            f"• @{self.bot_username} сводка за 30 минут\n"
            f"• @{self.bot_username} о чём вчера говорили?\n\n"
            f"По умолчанию анализирую последние {self.default_time_hours} часа."
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        await update.message.reply_text(
            "🤖 *Команды бота:*\n\n"
            "• `/start` - начало работы\n"
            "• `/help` - эта справка\n"
            "• `/stats` - статистика чата\n\n"
            "*Как запросить сводку:*\n"
            f"Упомяните @{self.bot_username} и опишите что хотите:\n\n"
            "📋 *Примеры запросов:*\n"
            f"• @{self.bot_username} сводка\n"
            f"• @{self.bot_username} о чём договорились?\n"
            f"• @{self.bot_username} что обсуждали за час?\n"
            f"• @{self.bot_username} сводка за вчера\n\n"
            "⏰ *Временные интервалы:*\n"
            "• \"сейчас\" - последние 10 минут\n"
            "• \"за X минут/часов/дней\"\n"
            "• \"вчера\" - весь вчерашний день\n"
            "• \"всё время\" - вся история\n",
            parse_mode=ParseMode.MARKDOWN
        )

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /stats"""
        chat_id = update.message.chat_id
        stats = self.chroma_service.get_collection_stats(chat_id)

        await update.message.reply_text(
            f"📊 *Статистика чата:*\n\n"
            f"💬 Сохранено сообщений: {stats['total_messages']}\n"
            f"🆔 ID чата: `{chat_id}`\n"
            f"🤖 Бот: @{self.bot_username}",
            parse_mode=ParseMode.MARKDOWN
        )

    async def process_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Основной обработчик входящих сообщений

        Args:
            update: Обновление от Telegram
            context: Контекст бота
        """
        message = update.message
        if not message or not message.text:
            return

        try:
            # Распознаем намерение
            intent = self.intent_recognizer.recognize_intent(
                message.text,
                self.bot_username
            )

            if intent and intent.type == 'summary':
                # Обрабатываем запрос на сводку
                await self._handle_summary_request(message, intent)
            else:
                # Сохраняем обычное сообщение
                await self._save_message(message)

        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения: {e}", exc_info=True)

    async def _save_message(self, message):
        """
        Сохранение сообщения в ChromaDB

        Args:
            message: Сообщение Telegram
        """
        try:
            success = self.chroma_service.save_message(message)
            if success:
                logger.debug(f"Сообщение {message.message_id} сохранено")
            else:
                logger.warning(f"Не удалось сохранить сообщение {message.message_id}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении сообщения: {e}")

    async def _handle_summary_request(self, message, intent: Intent):
        """
        Обработка запроса на генерацию сводки

        Args:
            message: Сообщение Telegram
            intent: Распознанное намерение
        """
        chat_id = message.chat_id
        time_intent = intent.time_intent

        # Получаем описание временного интервала
        time_desc = self.intent_recognizer.get_time_description(
            time_intent,
            self.default_time_hours
        )

        # Показываем статус
        status_message = await message.reply_text(
            f"🔄 Анализирую сообщения {time_desc}..."
        )

        try:
            # Вычисляем временной диапазон
            start_time, end_time = self._calculate_time_range(time_intent, chat_id)

            # Получаем сообщения из ChromaDB
            messages_with_metadata = self.chroma_service.get_messages_by_time(
                chat_id,
                int(start_time.timestamp()),
                int(end_time.timestamp())
            )

            if not messages_with_metadata:
                await status_message.edit_text(
                    f"🤷‍♂️ Не найдено сообщений {time_desc}"
                )
                return

            # Подготавливаем контекст для LLM
            messages_context = self.llm_service.prepare_messages_context(
                messages_with_metadata
            )

            # Генерируем сводку
            summary = await self.llm_service.generate_summary(
                messages_context,
                time_desc,
                len(messages_with_metadata)
            )

            # Отправляем результат
            await status_message.edit_text(
                f"📋 *Сводка {time_desc}*\n"
                f"_Проанализировано сообщений: {len(messages_with_metadata)}_\n\n"
                f"{summary}",
                parse_mode=ParseMode.MARKDOWN
            )

        except Exception as e:
            logger.error(f"Ошибка при генерации сводки: {e}", exc_info=True)
            await status_message.edit_text(
                "❌ Произошла ошибка при генерации сводки. "
                "Попробуйте позже или обратитесь к администратору."
            )

    def _calculate_time_range(self, time_intent, chat_id: int) -> tuple[datetime, datetime]:
        """
        Вычисление временного диапазона

        Args:
            time_intent: Временное намерение
            chat_id: ID чата

        Returns:
            Кортеж (начало, конец) временного диапазона
        """
        now = datetime.now()

        if time_intent.is_yesterday:
            # Вчерашний день с 00:00 до 23:59
            yesterday = now - timedelta(days=1)
            start = datetime.combine(yesterday.date(), datetime.min.time())
            end = datetime.combine(yesterday.date(), datetime.max.time())
        elif time_intent.is_all_time:
            # Всё время с начала эпохи
            start = datetime.fromtimestamp(0)
            end = now
        elif time_intent.period:
            # Конкретный период
            start = now - time_intent.period
            end = now
        else:
            # Дефолтный период
            start = now - timedelta(hours=self.default_time_hours)
            end = now

        return start, end
