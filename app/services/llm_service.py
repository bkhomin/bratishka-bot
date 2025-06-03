"""
Сервис для работы с LLM
"""
import asyncio
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict, Optional

from app.config.settings import config
from app.config.logging import get_logger

logger = get_logger(__name__)


class LLMService:
    """Сервис для работы с языковой моделью"""

    def __init__(self):
        """
        Инициализация сервиса LLM - НЕ БЛОКИРУЮЩАЯ
        """
        self.config = config.llm
        self.llm: Optional[object] = None
        self.is_initialized = False
        self.is_loading = False
        self.initialization_error = None
        self.loading_thread = None

        # Создаем индикатор запуска сразу
        self._create_startup_indicator()

        # Запускаем загрузку модели в отдельном потоке
        self._start_background_loading()

    def _create_startup_indicator(self):
        """Создает индикатор что сервис запустился"""
        try:
            os.makedirs('/tmp', exist_ok=True)
            with open('/tmp/service_started', 'w') as f:
                f.write(f'Service started at {datetime.now().isoformat()}')
        except Exception as e:
            logger.warning(f"Не удалось создать индикатор запуска: {e}")

    def _start_background_loading(self):
        """Запускает загрузку модели в фоновом потоке"""
        logger.info("Запуск фоновой загрузки модели...")
        self.is_loading = True
        self.loading_thread = threading.Thread(target=self._load_model_background, daemon=True)
        self.loading_thread.start()

    def _load_model_background(self):
        """Фоновая загрузка модели"""
        try:
            # Проверяем модель
            if not self._check_model_exists():
                self.initialization_error = f"Файл модели не найден: {self.config.model_path}"
                logger.error(self.initialization_error)
                self.is_loading = False
                return

            # Проверяем память (но не блокируем загрузку)
            self._check_memory_requirements()

            # Загружаем модель
            self._initialize_model_safe()

        except Exception as e:
            logger.error(f"Ошибка фоновой загрузки LLM: {e}")
            self.initialization_error = str(e)
        finally:
            self.is_loading = False

    def _check_model_exists(self) -> bool:
        """Проверяет существование файла модели"""
        model_path = Path(self.config.model_path)
        exists = model_path.exists()

        if not exists:
            logger.error(f"Файл модели не найден: {self.config.model_path}")
            logger.error(f"Текущая директория: {os.getcwd()}")
            try:
                models_dir = Path('models')
                if models_dir.exists():
                    files = list(models_dir.glob('*'))
                    logger.error(f"Файлы в директории models/: {files}")
                else:
                    logger.error("Директория models/ не существует")
            except Exception as e:
                logger.error(f"Ошибка при проверке директории models/: {e}")

        return exists

    def _check_memory_requirements(self):
        """Проверяет требования к памяти"""
        try:
            model_path = Path(self.config.model_path)
            file_size_gb = model_path.stat().st_size / (1024**3)
            logger.info(f"Размер модели: {file_size_gb:.2f} GB")

            try:
                import psutil
                memory = psutil.virtual_memory()
                available_gb = memory.available / (1024**3)
                logger.info(f"Доступная память: {available_gb:.2f} GB")

                required_gb = file_size_gb * 1.2
                if available_gb < required_gb:
                    logger.warning(f"Мало памяти: нужно ~{required_gb:.2f} GB, доступно {available_gb:.2f} GB")
                    logger.info("Попробуем загрузить с минимальными параметрами...")

            except ImportError:
                logger.warning("psutil не доступен, пропускаем проверку памяти")

        except Exception as e:
            logger.error(f"Ошибка при проверке памяти: {e}")

    def _initialize_model_safe(self):
        """Безопасная инициализация модели"""
        try:
            # Импортируем llama_cpp только при необходимости
            from llama_cpp import Llama

            logger.info(f"🔄 Начинаем загрузку модели: {self.config.model_path}")
            logger.info(f"⚙️ Параметры: n_ctx={self.config.n_ctx}, n_threads={self.config.n_threads}")

            start_time = time.time()

            # КРИТИЧНО: Минимальные параметры для стабильности
            self.llm = Llama(
                model_path=self.config.model_path,
                n_ctx=config.llm.n_ctx,  # Жестко ограничиваем
                n_threads=config.llm.n_threads,  # Минимум потоков
                n_gpu_layers=config.llm.n_gpu_layers,  # Без GPU
                verbose=False,
                seed=-1,
                use_mlock=False,  # Критично для Docker
                use_mmap=True,
                n_batch=256,  # Минимальный batch
                low_vram=False,
                logits_all=False,
                vocab_only=False,
                embedding=False
            )

            load_time = time.time() - start_time
            logger.info(f"✅ Модель загружена за {load_time:.2f} секунд")

            # Простой тест
            logger.info("🧪 Тестовая генерация...")
            test_start = time.time()
            test_result = self.llm("Test", max_tokens=3, temperature=0.1)
            test_time = time.time() - test_start
            logger.info(f"✅ Тест успешен за {test_time:.2f} секунд")

            self.is_initialized = True

            # Создаем индикатор успешной загрузки
            try:
                with open('/tmp/model_loaded', 'w') as f:
                    f.write(f'Model loaded at {datetime.now().isoformat()}')
                logger.info("📝 Создан индикатор успешной загрузки модели")
            except Exception as e:
                logger.warning(f"Не удалось создать индикатор загрузки: {e}")

        except ImportError as e:
            logger.error(f"❌ Ошибка импорта llama_cpp: {e}")
            self.initialization_error = f"llama_cpp недоступен: {e}"
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки модели: {e}")
            self.initialization_error = str(e)
            self.is_initialized = False

    def get_status(self) -> str:
        """Получить текущий статус сервиса"""
        if self.is_initialized:
            return "🟢 Модель готова"
        elif self.is_loading:
            return "🟡 Загрузка модели..."
        elif self.initialization_error:
            return f"🔴 Ошибка: {self.initialization_error}"
        else:
            return "⚪ Не инициализирован"

    def prepare_messages_context(self, messages_with_metadata: List[Tuple[str, Dict]]) -> str:
        """Подготовка контекста из сообщений для LLM"""
        messages = []

        for doc, metadata in messages_with_metadata:
            timestamp_value = metadata['timestamp']

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

        return "\n".join(messages[-50:])  # Ограничиваем до 50 сообщений

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
            detail_level = "лаконичную"
        elif message_count < 50:
            detail_level = "краткую"
        elif message_count < 200:
            detail_level = "структурированную"
        else:
            detail_level = "детальную"

        prompt = f"""<|im_start|>system
Ты - русскоговорящий ассистент для анализа переписки в Telegram чате. Твоя задача - создать {detail_level} сводку переписки.
<|im_end|>
<|im_start|>user
Проанализируй переписку {time_desc} и создай сводку.

Структура сводки:
1. Основные обсуждаемые темы
3. Важные события или новости
2. Ключевые решения и договоренности (если были)
4. Суть конфликтов или споров (если были)
5. Нерешённые вопросы (если есть)

Требования к ответу:
- НЕ повторяй информацию в сводке
- НЕ придумывай то, чего не было в переписке
- НЕ используй Markdown и HTML, только простой текст
- Если по какому-то из пунктов сводки нечего писать (например, не было конфликтов или не достигнуты договорённости) - не упоминай этот пункт в сводке
- Используй эмодзи для структурирования
- Будь конкретен, избегай общих фраз
- Если информации мало - так и напиши, не нужно делать выводы на основании недостаточной информации

Переписка чата:
{messages_context}
<|im_end|>
<|im_start|>assistant"""

        return prompt

    async def generate_summary(self, messages_context: str, time_desc: str, message_count: int) -> str:
        """Генерация сводки с помощью LLM"""

        if self.is_loading:
            return f"⏳ Модель все еще загружается. Попробуйте через минуту."

        if not self.is_initialized or not self.llm:
            error_msg = f"❌ LLM модель недоступна"
            if self.initialization_error:
                error_msg += f": {self.initialization_error}"
            return error_msg

        try:
            prompt = self.generate_summary_prompt(messages_context, time_desc, message_count)

            logger.info(f"Генерация сводки для {message_count} сообщений")
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
            return f"❌ Ошибка при генерации: {str(e)}"

    def health_check(self) -> bool:
        """Проверка работоспособности модели"""
        return True  # Всегда возвращаем True для сервиса

