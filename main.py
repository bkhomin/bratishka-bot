import asyncio
import logging
from datetime import datetime, timedelta
import time
import re
from typing import List, Dict, Optional, Tuple
import os
from dataclasses import dataclass

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
from llama_cpp import Llama
import chromadb
from chromadb.config import Settings

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger('telegram').setLevel(logging.INFO)
logging.getLogger('httpx').setLevel(logging.WARN)
logging.getLogger('asyncio').setLevel(logging.INFO)
logging.getLogger('llama_cpp').setLevel(logging.DEBUG)
logger = logging.getLogger(__name__)


@dataclass
class TimeIntent:
    """Класс для хранения распознанного временного намерения"""
    period: Optional[timedelta] = None
    is_yesterday: bool = False
    is_all_time: bool = False
    is_now: bool = False
    exact_minutes: Optional[int] = None
    raw_text: str = ""


class IntentRecognizer:
    """Распознаватель намерений пользователя"""

    # Паттерны для различных типов запросов
    SUMMARY_PATTERNS = [
        r'о ч[её]м.*договорились',
        r'к чему.*вс[её]',
        r'сводк[ау]',
        r'протокол',
        r'резюм[ие]',
        r'итог[и]?',
        r'суммар[и]?'
    ]

    NOW_PATTERNS = [
        r'что.*было.*сейчас',
        r'что.*сейчас.*было',
        r'только что',
        r'прямо сейчас'
    ]

    YESTERDAY_PATTERNS = [
        r'вчера',
        r'вчерашн'
    ]

    ALL_TIME_PATTERNS = [
        r'нормально.*общались',
        r'вс[её].*время',
        r'за вс[её].*время',
        r'с.*самого.*начала'
    ]

    TIME_EXTRACTION_PATTERNS = [
        (r'за.*(\d+)\s*минут', 'minutes'),
        (r'за.*(\d+)\s*час', 'hours'),
        (r'за.*(\d+)\s*дн', 'days'),
        (r'за.*(\d+)\s*недел', 'weeks'),
        (r'за.*последн[ие]{1,2}\s*(\d+)\s*минут', 'minutes'),
        (r'за.*последн[ие]{1,2}\s*(\d+)\s*час', 'hours'),
        (r'за.*последн[ие]{1,2}\s*(\d+)\s*дн', 'days'),
    ]

    @classmethod
    def extract_time_intent(cls, text: str) -> TimeIntent:
        """Извлечение временного намерения из текста"""
        text_lower = text.lower()
        intent = TimeIntent(raw_text=text)

        # Проверяем "сейчас"
        for pattern in cls.NOW_PATTERNS:
            if re.search(pattern, text_lower):
                intent.is_now = True
                intent.period = timedelta(minutes=10)
                return intent

        # Проверяем "вчера"
        for pattern in cls.YESTERDAY_PATTERNS:
            if re.search(pattern, text_lower):
                intent.is_yesterday = True
                return intent

        # Проверяем "всё время"
        for pattern in cls.ALL_TIME_PATTERNS:
            if re.search(pattern, text_lower):
                intent.is_all_time = True
                return intent

        # Извлекаем точное время
        for pattern, time_type in cls.TIME_EXTRACTION_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                value = int(match.group(1))
                if time_type == 'minutes':
                    intent.period = timedelta(minutes=value)
                    intent.exact_minutes = value
                elif time_type == 'hours':
                    intent.period = timedelta(hours=value)
                elif time_type == 'days':
                    intent.period = timedelta(days=value)
                elif time_type == 'weeks':
                    intent.period = timedelta(weeks=value)
                return intent

        return intent

    @classmethod
    def is_summary_request(cls, text: str) -> bool:
        """Проверка, является ли сообщение запросом на сводку"""
        text_lower = text.lower()
        for pattern in cls.SUMMARY_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        return False


class RAGTelegramBot:
    def __init__(self, config: Dict):
        """
        Инициализация бота с RAG функциональностью

        Args:
            config: Конфигурация бота
        """
        self.config = config
        self.bot_username = config.get('bot_username', 'bratishka')
        self.default_time_hours = config.get('default_time_hours', 2)

        # Инициализация LLM
        logger.info(f"Загрузка модели: {config['model_path']}")
        self.llm = Llama(
            model_path=config['model_path'],
            n_ctx=config.get('n_ctx', 8192),
            n_threads=config.get('n_threads', 4),
            n_gpu_layers=config.get('n_gpu_layers', 0),
            verbose=False,
            seed=-1  # Добавлено для совместимости с новой версией
        )

        # Инициализация ChromaDB
        self.chroma_client = chromadb.PersistentClient(
            path=config['chroma_db_path'],
            settings=Settings(anonymized_telemetry=False)
        )

        # Создаём отдельные коллекции для каждого чата (будем создавать динамически)
        self.collections = {}

    def _get_collection_for_chat(self, chat_id: int) -> chromadb.Collection:
        """Получение или создание коллекции для конкретного чата"""
        collection_name = f"chat_{chat_id}"

        if chat_id not in self.collections:
            self.collections[chat_id] = self.chroma_client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"Создана/получена коллекция для чата {chat_id}")

        return self.collections[chat_id]

    def _generate_message_id(self, chat_id: int, message_id: int) -> str:
        """Генерация уникального ID для сообщения"""
        return f"{chat_id}_{message_id}"

    async def process_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка входящих сообщений"""
        message = update.message
        if not message or not message.text:
            return

        # Проверяем, не является ли это запросом к боту
        if f"@{self.bot_username}" in message.text:
            # Если сообщение адресовано боту, проверяем намерение
            if IntentRecognizer.is_summary_request(message.text):
                await self.generate_summary(update, context)
            return

        # Сохраняем сообщение в векторную БД
        await self._save_message_to_chroma(message)

    async def _save_message_to_chroma(self, message):
        """Сохранение сообщения в ChromaDB"""
        chat_id = message.chat_id
        collection = self._get_collection_for_chat(chat_id)

        # Подготавливаем текст
        message_text = message.text or message.caption or ""
        if not message_text:
            return

        # Метаданные сообщения
        metadata = {
            "chat_id": str(chat_id),
            "message_id": str(message.message_id),
            "user_id": str(message.from_user.id),
            "username": message.from_user.username or message.from_user.first_name or "Unknown",
            "full_name": f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip(),
            "timestamp": int(message.date.timestamp()),  # Сохраняем как timestamp (число)
        }

        if message.reply_to_message:
            metadata["reply_to_message_id"] = str(message.reply_to_message.message_id)

        # Сохраняем в коллекцию чата
        doc_id = self._generate_message_id(chat_id, message.message_id)

        try:
            collection.add(
                documents=[message_text],
                metadatas=[metadata],
                ids=[doc_id]
            )
            logger.debug(f"Сохранено сообщение {doc_id} из чата {chat_id}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении сообщения: {e}")

    def _calculate_time_range(self, time_intent: TimeIntent, chat_id: int) -> Tuple[datetime, datetime]:
        """Вычисление временного диапазона на основе намерения"""
        now = datetime.now()

        if time_intent.is_yesterday:
            # Вчерашний день с 00:00 до 23:59
            yesterday = now - timedelta(days=1)
            start = datetime.combine(yesterday.date(), time.min)
            end = datetime.combine(yesterday.date(), time.max)
        elif time_intent.is_all_time:
            # Всё время с момента создания времени
            start = datetime.min
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

    async def generate_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Генерация сводки по сообщениям чата"""
        message = update.message
        chat_id = message.chat_id

        # Извлекаем временное намерение
        time_intent = IntentRecognizer.extract_time_intent(message.text)
        start_time, end_time = self._calculate_time_range(time_intent, chat_id)

        # Формируем сообщение о начале анализа
        if time_intent.is_yesterday:
            time_desc = "за вчерашний день"
        elif time_intent.is_all_time:
            time_desc = "за всё время"
        elif time_intent.is_now:
            time_desc = "за последние 10 минут"
        elif time_intent.exact_minutes:
            time_desc = f"за последние {time_intent.exact_minutes} минут"
        elif time_intent.period:
            time_desc = f"за {time_intent.period}"
        else:
            time_desc = f"за последние {self.default_time_hours} часа"

        status_message = await message.reply_text(f"🔄 Анализирую сообщения {time_desc}...")

        try:
            # Получаем коллекцию чата
            collection = self._get_collection_for_chat(chat_id)

            # Преобразуем даты в timestamp (число)
            start_timestamp = int(start_time.timestamp())
            end_timestamp = int(end_time.timestamp())

            # Формируем фильтр по времени
            where_filter = {
                "$and": [
                    {"timestamp": {"$gte": start_timestamp}},
                    {"timestamp": {"$lte": end_timestamp}}
                ]
            }

            # Получаем сообщения за период
            results = collection.query(
                query_texts=[""],
                n_results=1000,
                where=where_filter
            )

            # Сортируем сообщения по времени
            messages_with_metadata = list(zip(results['documents'][0], results['metadatas'][0]))
            messages_with_metadata.sort(key=lambda x: x[1]['timestamp'])

            # Логируем информацию о сообщениях
            logger.debug(f"Обработка {len(messages_with_metadata)} сообщений")
            for i, (doc, meta) in enumerate(messages_with_metadata[:3]):  # Логируем первые 3 сообщения
                logger.debug(f"Сообщение {i + 1}: {meta.get('username')} @ {meta.get('timestamp')}: {doc[:50]}...")

            # Формируем контекст для LLM
            messages_context = self._prepare_messages_context(messages_with_metadata)

            # Генерируем сводку
            logger.info("Начинаю генерацию сводки с помощью LLM...")
            summary = await self._generate_summary_with_llm(
                messages_context,
                time_desc,
                len(messages_with_metadata)
            )
            logger.info("Генерация сводки завершена")

            # Отправляем результат
            await status_message.edit_text(
                f"📋 *Сводка {time_desc}*\n"
                f"_Проанализировано сообщений: {len(messages_with_metadata)}_\n\n"
                f"{summary}",
                parse_mode=ParseMode.MARKDOWN
            )

        except Exception as e:
            logger.error(f"Ошибка при генерации сводки: {e}", exc_info=True)
            await status_message.edit_text("❌ Произошла ошибка при генерации сводки.")

    def _prepare_messages_context(self, messages_with_metadata: List[Tuple[str, Dict]]) -> str:
        """Подготовка контекста из сообщений для LLM"""
        messages = []

        for doc, metadata in messages_with_metadata:
            # Получаем timestamp (может быть числом или строкой)
            timestamp_value = metadata['timestamp']

            # Преобразуем в datetime
            if isinstance(timestamp_value, (int, float)):
                timestamp = datetime.fromtimestamp(timestamp_value)
            elif isinstance(timestamp_value, str):
                try:
                    # Пробуем сначала как число (на случай если строка содержит число)
                    timestamp = datetime.fromtimestamp(float(timestamp_value))
                except ValueError:
                    # Если не число, пробуем как строку ISO формата
                    timestamp = datetime.fromisoformat(timestamp_value)
            else:
                # Если непонятный формат, используем текущее время
                timestamp = datetime.now()

            username = metadata.get('username', 'Unknown')
            full_name = metadata.get('full_name', username)

            # Используем имя пользователя для контекста
            display_name = full_name if full_name != "Unknown" else username

            messages.append(
                f"[{timestamp.strftime('%H:%M')}] {display_name}: {doc}"
            )

        return "\n".join(messages[-200:])  # Ограничиваем последними 200 сообщениями

    async def _generate_summary_with_llm(self, messages_context: str, time_desc: str, message_count: int) -> str:
        """Генерация сводки с помощью LLM"""
        logger.info(f"Подготовка промпта для {message_count} сообщений")

        # Адаптивный промпт
        if message_count < 10:
            detail_level = "очень краткую"
        elif message_count < 50:
            detail_level = "краткую"
        elif message_count < 200:
            detail_level = "структурированную"
        else:
            detail_level = "детальную"

        prompt = f"""<|im_start|>system
    Ты - русскоговорящий ассистент для анализа переписки в Telegram чате. Твоя задача - создать {detail_level} и информативную сводку переписки.
    <|im_end|>
    <|im_start|>user
    Проанализируй переписку {time_desc} и создай сводку.

    Требования к сводке:
    1. Выдели основные обсуждаемые темы
    2. Укажи ключевые решения и договоренности (если были)
    3. Отметь важные события или новости
    4. Если были конфликты или споры - кратко опиши суть
    5. Выдели нерешённые вопросы (если есть)
    6. Не дублируй информацию на английском языке

    Формат ответа:
    - Используй эмодзи для структурирования
    - Будь конкретен, избегай общих фраз
    - Если информации мало - так и напиши
    - НЕ придумывай то, чего не было в переписке

    Переписка чата:
    {messages_context}
    <|im_end|>
    <|im_start|>assistant"""

        logger.debug(f"Сгенерированный промпт:\n{prompt[:500]}...")  # Логируем начало промпта

        try:
            # Запускаем генерацию в отдельном потоке
            loop = asyncio.get_event_loop()
            logger.info("Начинаю генерацию ответа LLM...")
            start_time = time.time()

            response = await loop.run_in_executor(
                None,
                lambda: self.llm(
                    prompt,
                    max_tokens=8192,
                    temperature=0.6,
                    top_p=0.95,
                    stop=["<|im_end|>", "<|im_start|>"]
                )
            )

            elapsed_time = time.time() - start_time
            logger.info(f"Генерация завершена за {elapsed_time:.2f} секунд")

            summary = response['choices'][0]['text'].strip()
            logger.debug(f"Полученная сводка:\n{summary}")

            if len(summary) < 50 and message_count > 5:
                summary = f"⚠️ Переписка была малоактивной.\n\n{summary}"

            return summary

        except Exception as e:
            logger.error(f"Ошибка при генерации сводки LLM: {e}")
            raise

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

    def run(self, token: str):
        """Запуск бота"""
        application = Application.builder().token(token).build()

        # Регистрация обработчиков
        application.add_handler(CommandHandler("start", self.start_command))

        # Обработчик всех сообщений в группах
        application.add_handler(MessageHandler(
            filters.TEXT & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP),
            self.process_message
        ))

        # Обработчик личных сообщений
        application.add_handler(MessageHandler(
            filters.TEXT & filters.ChatType.PRIVATE,
            self.start_command
        ))

        # Запуск бота
        logger.info(f"Бот @{self.bot_username} запущен!")
        application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    # Загружаем переменные окружения
    from dotenv import load_dotenv

    load_dotenv()

    config = {
        'bot_username': os.getenv('BOT_USERNAME', 'bratishka'),
        'default_time_hours': int(os.getenv('DEFAULT_TIME_HOURS', '2')),
        'model_path': os.getenv('MODEL_PATH', './models/DeepSeek-R1-0528-Qwen3-8B-Q4_K_M.gguf'),
        'chroma_db_path': os.getenv('CHROMA_DB_PATH', './chroma_db'),
        'n_ctx': int(os.getenv('MODEL_CTX', '8192')),
        'n_threads': int(os.getenv('MODEL_THREADS', '4')),
        'n_gpu_layers': int(os.getenv('MODEL_GPU_LAYERS', '0')),
    }

    # Telegram Bot Token
    BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN не установлен!")
        exit(1)

    # Создаём и запускаем бота
    bot = RAGTelegramBot(config)
    bot.run(BOT_TOKEN)
