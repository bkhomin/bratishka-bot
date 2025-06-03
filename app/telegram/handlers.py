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

# Константы Telegram
TELEGRAM_MAX_MESSAGE_LENGTH = 4096
TELEGRAM_SAFE_LENGTH = 4000  # Оставляем запас для форматирования


class TelegramHandlers:
    """Класс для обработки сообщений Telegram бота"""

    def __init__(
            self,
            chroma_service: ChromaService,
            llm_service: LLMService,
            bot_username: str,
            default_time_hours: int = 2
    ):
        self.chroma_service = chroma_service
        self.llm_service = llm_service  # Может быть None
        self.bot_username = bot_username.replace('@', '')
        self.default_time_hours = default_time_hours
        self.intent_recognizer = IntentRecognizer()

    def _truncate_text(self, text: str, max_length: int = TELEGRAM_SAFE_LENGTH) -> str:
        """
        Обрезает текст до максимальной длины, сохраняя целостность
        """
        if len(text) <= max_length:
            return text

        # Обрезаем по предложениям
        sentences = text.split('.')
        result = ""

        for sentence in sentences:
            test_result = result + sentence + "."
            if len(test_result) > max_length - 50:
                break
            result = test_result

        # Если результат слишком короткий, обрезаем по словам
        if len(result) < max_length // 2:
            words = text.split()
            result = ""
            for word in words:
                test_result = result + " " + word if result else word
                if len(test_result) > max_length - 20:
                    break
                result = test_result

        # Добавляем многоточие если текст был обрезан
        if len(result) < len(text):
            result = result.rstrip() + "..."

        return result

    def _split_long_message(self, text: str, max_length: int = TELEGRAM_SAFE_LENGTH) -> list[str]:
        """
        Разбивает длинное сообщение на части
        """
        if len(text) <= max_length:
            return [text]

        parts = []
        current_part = ""

        paragraphs = text.split('\n\n')

        for paragraph in paragraphs:
            if len(paragraph) > max_length:
                sentences = paragraph.split('.')
                for sentence in sentences:
                    if not sentence.strip():
                        continue

                    sentence = sentence.strip() + '.'

                    if len(current_part + '\n' + sentence) > max_length:
                        if current_part:
                            parts.append(current_part.strip())
                            current_part = sentence
                        else:
                            parts.append(self._truncate_text(sentence, max_length))
                    else:
                        current_part += '\n' + sentence if current_part else sentence
            else:
                if len(current_part + '\n\n' + paragraph) > max_length:
                    if current_part:
                        parts.append(current_part.strip())
                        current_part = paragraph
                    else:
                        parts.append(paragraph)
                else:
                    current_part += '\n\n' + paragraph if current_part else paragraph

        if current_part:
            parts.append(current_part.strip())

        return parts

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        if self.llm_service:
            model_status = self.llm_service.get_status()
        else:
            model_status = "🔴 Сервис недоступен"

        message_text = (
            f"👋 Привет! Я @{self.bot_username} - бот для анализа переписки.\n\n"
            f"Статус модели: {model_status}\n\n"
            "🔹 Добавьте меня в чат и я начну сохранять сообщения\n"
            "🔹 Обращайтесь ко мне через @:\n\n"
            "Примеры:\n"
            f"• @{self.bot_username} о чём договорились?\n"
            f"• @{self.bot_username} сводку\n\n"
            f"По умолчанию анализирую последние {self.default_time_hours} часа."
        )

        await update.message.reply_text(self._truncate_text(message_text))

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = (
            "🤖 КОМАНДЫ БОТА:\n\n"
            "• /start - начало работы\n"
            "• /help - эта справка\n"
            "• /stats - статистика чата\n\n"
            "КАК ЗАПРОСИТЬ СВОДКУ:\n"
            f"Упомяните @{self.bot_username} и опишите что хотите:\n\n"
            "📋 ПРИМЕРЫ ЗАПРОСОВ:\n"
            f"• @{self.bot_username} сводка\n"
            f"• @{self.bot_username} о чём договорились?\n"
            f"• @{self.bot_username} что обсуждали за час?\n\n"
            "⏰ ВРЕМЕННЫЕ ИНТЕРВАЛЫ:\n"
            "• \"сейчас\" - последние 10 минут\n"
            "• \"за X минут/часов/дней\"\n"
            "• \"вчера\" - весь вчерашний день\n"
            "• \"всё время\" - вся история"
        )

        await update.message.reply_text(self._truncate_text(help_text))

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /stats"""
        try:
            chat_id = update.message.chat_id
            stats = self.chroma_service.get_collection_stats(chat_id)

            if self.llm_service:
                model_status = self.llm_service.get_status()
            else:
                model_status = "🔴 Сервис недоступен"

            chroma_status = "🟢 работает" if self.chroma_service.health_check() else "🔴 недоступна"

            stats_text = (
                f"📊 СТАТИСТИКА ЧАТА:\n\n"
                f"💬 Сохранено сообщений: {stats['total_messages']}\n"
                f"🆔 ID чата: {chat_id}\n"
                f"🤖 Бот: @{self.bot_username}\n\n"
                f"СТАТУС СЕРВИСОВ:\n"
                f"🧠 LLM модель: {model_status}\n"
                f"🗄️ ChromaDB: {chroma_status}"
            )

            await update.message.reply_text(self._truncate_text(stats_text))

        except Exception as e:
            logger.error(f"Ошибка в команде stats: {e}")
            await update.message.reply_text(
                "❌ Ошибка при получении статистики. Попробуйте позже."
            )

    async def process_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Основной обработчик входящих сообщений"""
        message = update.message
        if not message or not message.text:
            return

        try:
            intent = self.intent_recognizer.recognize_intent(
                message.text,
                self.bot_username
            )

            if intent and intent.type == 'summary':
                await self._handle_summary_request(message, intent)
            else:
                await self._save_message(message)

        except Exception as e:
            logger.error(f"Ошибка при обработке сообщения: {e}", exc_info=True)

    async def _save_message(self, message):
        """Сохранение сообщения в ChromaDB"""
        try:
            success = self.chroma_service.save_message(message)
            if success:
                logger.debug(f"Сообщение {message.message_id} сохранено")
            else:
                logger.warning(f"Не удалось сохранить сообщение {message.message_id}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении сообщения: {e}")

    async def _handle_summary_request(self, message, intent: Intent):
        """Обработка запроса на генерацию сводки"""

        # Проверяем наличие LLM сервиса
        if not self.llm_service:
            await message.reply_text(
                "❌ LLM сервис недоступен. Бот работает только в режиме сохранения сообщений."
            )
            return

        # Проверяем статус модели
        if self.llm_service.is_loading:
            await message.reply_text(
                "⏳ Модель все еще загружается. Попробуйте через минуту.\n"
                f"Статус: {self.llm_service.get_status()}"
            )
            return

        if not self.llm_service.is_initialized:
            await message.reply_text(
                f"❌ LLM модель недоступна.\n"
                f"Статус: {self.llm_service.get_status()}"
            )
            return

        chat_id = message.chat_id
        time_intent = intent.time_intent

        time_desc = self.intent_recognizer.get_time_description(
            time_intent,
            self.default_time_hours
        )

        status_message = await message.reply_text(
            f"🔄 Анализирую сообщения {time_desc}..."
        )

        try:
            start_time, end_time = self._calculate_time_range(time_intent, chat_id)

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

            messages_context = self.llm_service.prepare_messages_context(
                messages_with_metadata
            )

            summary = await self.llm_service.generate_summary(
                messages_context,
                time_desc,
                len(messages_with_metadata)
            )

            # Формируем заголовок
            header = (
                f"📋 СВОДКА {time_desc.upper()}\n"
                f"Проанализировано сообщений: {len(messages_with_metadata)}\n\n"
            )

            full_message = header + summary

            # Проверяем длину и разбиваем если нужно
            if len(full_message) <= TELEGRAM_SAFE_LENGTH:
                await status_message.edit_text(full_message)
            else:
                # Сообщение слишком длинное, разбиваем на части
                await status_message.edit_text(header.strip())

                summary_parts = self._split_long_message(summary)

                for i, part in enumerate(summary_parts):
                    if i == 0:
                        part_header = "📄 Часть 1:\n\n"
                    else:
                        part_header = f"📄 Часть {i+1}:\n\n"

                    part_message = part_header + part

                    if len(part_message) > TELEGRAM_SAFE_LENGTH:
                        part_message = part_header + self._truncate_text(part, TELEGRAM_SAFE_LENGTH - len(part_header))

                    await message.reply_text(part_message)

        except Exception as e:
            logger.error(f"Ошибка при генерации сводки: {e}", exc_info=True)
            error_message = (
                "❌ Произошла ошибка при генерации сводки. "
                "Попробуйте позже или обратитесь к администратору."
            )

            try:
                await status_message.edit_text(error_message)
            except Exception:
                await message.reply_text(error_message)

    def _calculate_time_range(self, time_intent, chat_id: int) -> tuple[datetime, datetime]:
        """Вычисление временного диапазона"""
        now = datetime.now()

        if time_intent.is_yesterday:
            yesterday = now - timedelta(days=1)
            start = datetime.combine(yesterday.date(), datetime.min.time())
            end = datetime.combine(yesterday.date(), datetime.max.time())
        elif time_intent.is_all_time:
            start = datetime.fromtimestamp(0)
            end = now
        elif time_intent.period:
            start = now - time_intent.period
            end = now
        else:
            start = now - timedelta(hours=self.default_time_hours)
            end = now

        return start, end
