"""
Сервис для работы с LLM
"""
import asyncio
import os
import time
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict
from llama_cpp import Llama

from app.config.settings import config
from app.config.logging import get_logger

logger = get_logger(__name__)


class LLMService:
    """Сервис для работы с языковой моделью"""

    def __init__(self):
        """
        Инициализация сервиса LLM
        """
        self.config = config.llm
        self.llm = None
        self._initialize_model()

    def _get_model_path(self) -> str:
        """
        Получение корректного пути к модели

        Returns:
            Абсолютный путь к файлу модели
        """
        model_path = self.config.model_path

        # Если путь относительный, делаем его относительно корня проекта
        if not os.path.isabs(model_path):
            # Получаем корневую директорию проекта (на 2 уровня выше от этого файла)
            project_root = Path(__file__).parent.parent.parent
            model_path = project_root / model_path

        # Преобразуем в абсолютный путь
        model_path = Path(model_path).resolve()

        logger.debug(f"Путь к модели: {model_path}")

        # Проверяем существование файла
        if not model_path.exists():
            raise FileNotFoundError(f"Файл модели не найден: {model_path}")

        return str(model_path)

    def _initialize_model(self):
        """Инициализация языковой модели"""
        try:
            model_path = self._get_model_path()
            logger.info(f"Загрузка модели: {model_path}")

            self.llm = Llama(
                model_path=model_path,
                n_ctx=self.config.n_ctx,
                n_threads=self.config.n_threads,
                n_gpu_layers=self.config.n_gpu_layers,
                verbose=False,
                seed=-1
            )

            logger.info("Модель успешно загружена")

        except Exception as e:
            logger.error(f"Ошибка загрузки модели: {e}")
            raise

    def prepare_messages_context(self, messages_with_metadata: List[Tuple[str, Dict]]) -> str:
        """
        Подготовка контекста из сообщений для LLM

        Args:
            messages_with_metadata: Список сообщений с метаданными

        Returns:
            Форматированный контекст
        """
        messages = []

        for doc, metadata in messages_with_metadata:
            # Получаем timestamp
            timestamp_value = metadata['timestamp']

            # Преобразуем в datetime
            if isinstance(timestamp_value, (int, float)):
                timestamp = datetime.fromtimestamp(timestamp_value)
            elif isinstance(timestamp_value, str):
                try:
                    timestamp = datetime.fromtimestamp(float(timestamp_value))
                except ValueError:
                    timestamp = datetime.fromisoformat(timestamp_value)
            else:
                timestamp = datetime.now()

            username = metadata.get('username', 'Unknown')
            full_name = metadata.get('full_name', username)
            display_name = full_name if full_name != "Unknown" else username

            messages.append(
                f"[{timestamp.strftime('%H:%M')}] {display_name}: {doc}"
            )

        # Ограничиваем контекст последними 200 сообщениями
        return "\n".join(messages[-200:])

    def generate_summary_prompt(
        self,
        messages_context: str,
        time_desc: str,
        message_count: int
    ) -> str:
        """
        Генерация промпта для создания сводки

        Args:
            messages_context: Контекст сообщений
            time_desc: Описание временного периода
            message_count: Количество сообщений

        Returns:
            Готовый промпт
        """
        # Адаптивный уровень детализации
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

        return prompt

    async def generate_summary(
        self,
        messages_context: str,
        time_desc: str,
        message_count: int
    ) -> str:
        """
        Генерация сводки с помощью LLM

        Args:
            messages_context: Контекст сообщений
            time_desc: Описание временного периода
            message_count: Количество сообщений

        Returns:
            Сгенерированная сводка
        """
        try:
            prompt = self.generate_summary_prompt(messages_context, time_desc, message_count)

            logger.debug(f"Генерация сводки для {message_count} сообщений")
            logger.debug(f"Промпт (первые 500 символов): {prompt[:500]}...")

            # Запускаем генерацию в отдельном потоке
            loop = asyncio.get_event_loop()
            start_time = time.time()

            response = await loop.run_in_executor(
                None,
                lambda: self.llm(
                    prompt,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    top_p=self.config.top_p,
                    stop=["<|im_end|>", "<|im_start|>"]
                )
            )

            elapsed_time = time.time() - start_time
            logger.info(f"Генерация завершена за {elapsed_time:.2f} секунд")

            summary = response['choices'][0]['text'].strip()

            # Добавляем предупреждение для малоактивных чатов
            if len(summary) < 50 and message_count > 5:
                summary = f"⚠️ Переписка была малоактивной.\n\n{summary}"

            logger.debug(f"Сгенерированная сводка: {summary}")
            return summary

        except Exception as e:
            logger.error(f"Ошибка при генерации сводки: {e}")
            raise

    def health_check(self) -> bool:
        """
        Проверка работоспособности модели

        Returns:
            True если модель работает
        """
        try:
            # Простой тест генерации
            test_response = self.llm(
                "Привет! Как дела?",
                max_tokens=10,
                temperature=0.1
            )
            return len(test_response['choices'][0]['text']) > 0
        except Exception as e:
            logger.error(f"LLM health check failed: {e}")
            return False
