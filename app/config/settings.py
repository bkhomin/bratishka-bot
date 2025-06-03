"""
Конфигурация приложения
"""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()


@dataclass
class TelegramConfig:
    """Конфигурация Telegram бота"""
    token: str
    username: str
    default_time_hours: int = 2

    @classmethod
    def from_env(cls) -> 'TelegramConfig':
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN не установлен!")

        return cls(
            token=token,
            username=os.getenv('BOT_USERNAME', 'bratishka_bot'),
            default_time_hours=int(os.getenv('DEFAULT_TIME_HOURS', '2'))
        )


@dataclass
class LLMConfig:
    """Конфигурация LLM модели"""
    model_path: str
    n_ctx: int = 8192
    n_threads: int = 4
    n_gpu_layers: int = 0
    temperature: float = 0.6
    top_p: float = 0.95
    max_tokens: int = 8192

    @classmethod
    def from_env(cls) -> 'LLMConfig':
        model_path = os.getenv('MODEL_PATH', './models/DeepSeek-R1-0528-Qwen3-8B-Q4_K_M.gguf')
        if not model_path:
            raise ValueError("MODEL_PATH не установлен!")

        return cls(
            model_path=model_path,
            n_ctx=int(os.getenv('MODEL_CTX', '8192')),
            n_threads=int(os.getenv('MODEL_THREADS', '4')),
            n_gpu_layers=int(os.getenv('MODEL_GPU_LAYERS', '0')),
            temperature=float(os.getenv('MODEL_TEMPERATURE', '0.6')),
            top_p=float(os.getenv('MODEL_TOP_P', '0.95')),
            max_tokens=int(os.getenv('MODEL_MAX_TOKENS', '8192'))
        )


@dataclass
class ChromaConfig:
    """Конфигурация ChromaDB"""
    host: str = 'localhost'
    port: int = 8000

    @classmethod
    def from_env(cls) -> 'ChromaConfig':
        return cls(
            host=os.getenv('CHROMA_HOST', 'localhost'),
            port=int(os.getenv('CHROMA_PORT', '8000'))
        )


@dataclass
class AppConfig:
    """Основная конфигурация приложения"""
    telegram: TelegramConfig
    llm: LLMConfig
    chroma: ChromaConfig
    debug: bool = False
    log_level: str = 'INFO'

    @classmethod
    def from_env(cls) -> 'AppConfig':
        return cls(
            telegram=TelegramConfig.from_env(),
            llm=LLMConfig.from_env(),
            chroma=ChromaConfig.from_env(),
            debug=os.getenv('DEBUG', '0').lower() in ('1', 'true', 'yes'),
            log_level=os.getenv('LOG_LEVEL', 'INFO').upper()
        )


# Глобальный экземпляр конфигурации
config = AppConfig.from_env()
