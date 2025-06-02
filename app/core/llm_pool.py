import asyncio
import logging
from typing import Dict

from llama_cpp import Llama

from app.config import Config

logger = logging.getLogger(__name__)


class LLMPool:
    """Пул LLM для оптимизации ресурсов"""

    def __init__(self, pool_size: int = 2):
        self.pool_size = pool_size
        self._pool: asyncio.Queue = asyncio.Queue(maxsize=pool_size)
        self._initialized = False
        self._lock = asyncio.Lock()

    async def initialize(self):
        """Инициализация пула"""
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            logger.info(f"Инициализация пула LLM с {self.pool_size} экземплярами")

            for i in range(self.pool_size):
                try:
                    llm = Llama(
                        model_path=Config.LLAMA_MODEL_PATH,
                        n_ctx=Config.LLAMA_N_CTX,
                        n_threads=Config.LLAMA_N_THREADS,
                        verbose=False
                    )
                    await self._pool.put(llm)
                    logger.info(f"LLM экземпляр {i + 1} создан")
                except Exception as e:
                    logger.error(f"Ошибка создания LLM экземпляра {i + 1}: {e}")
                    raise

            self._initialized = True
            logger.info("Пул LLM инициализирован")

    async def get_llm(self) -> Llama:
        """Получение LLM из пула"""
        if not self._initialized:
            await self.initialize()

        return await self._pool.get()

    async def return_llm(self, llm: Llama) -> None:
        """Возврат LLM в пул"""
        await self._pool.put(llm)

    async def shutdown(self):
        """Завершение работы пула"""
        logger.info("Завершение работы пула LLM")
        while not self._pool.empty():
            llm = await self._pool.get()
            # LLM в llama-cpp-python не требует явного закрытия
        self._initialized = False


# Глобальный пул LLM
llm_pool = LLMPool(pool_size=2)


class OptimizedLLM:
    """Оптимизированный LLM с пулом соединений"""

    def __init__(self):
        self.pool = llm_pool

    async def generate(self, prompt: str, **kwargs) -> str:
        """Генерация ответа с использованием пула"""
        llm = await self.pool.get_llm()
        try:
            result = llm(
                prompt,
                max_tokens=kwargs.get('max_tokens', 512),
                temperature=kwargs.get('temperature', Config.LLAMA_TEMPERATURE),
                top_p=kwargs.get('top_p', Config.LLAMA_TOP_P),
                stop=kwargs.get('stop', ["<｜User｜>", "\n\n"]),
                echo=False
            )
            return result['choices'][0]['text'].strip()
        finally:
            await self.pool.return_llm(llm)

    async def reasoning_generate(self, prompt: str, **kwargs) -> Dict[str, str]:
        """Генерация с процессом рассуждений"""
        llm = await self.pool.get_llm()
        try:
            thinking_prompt = f"<｜thinking｜>\n{prompt}\n<｜/thinking｜>\n\n<｜User｜>{prompt}<｜Assistant｜>"

            result = llm(
                thinking_prompt,
                max_tokens=kwargs.get('max_tokens', 1024),
                temperature=kwargs.get('temperature', Config.LLAMA_TEMPERATURE),
                top_p=kwargs.get('top_p', Config.LLAMA_TOP_P),
                stop=kwargs.get('stop', ["<｜User｜>"]),
                echo=False
            )

            response_text = result['choices'][0]['text'].strip()

            # Разделение на рассуждения и ответ
            if "<｜thinking｜>" in response_text and "<｜/thinking｜>" in response_text:
                thinking_start = response_text.find("<｜thinking｜>") + len("<｜thinking｜>")
                thinking_end = response_text.find("<｜/thinking｜>")
                thinking = response_text[thinking_start:thinking_end].strip()
                answer = response_text[thinking_end + len("<｜/thinking｜>"):].strip()
            else:
                thinking = ""
                answer = response_text

            return {
                "thinking": thinking,
                "answer": answer
            }
        finally:
            await self.pool.return_llm(llm)
