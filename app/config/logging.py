"""
Конфигурация логирования
"""
import logging
import sys
from typing import Optional


def setup_logging(level: str = 'INFO', debug: bool = False) -> logging.Logger:
    """
    Настройка логирования для приложения

    Args:
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR)
        debug: Режим отладки

    Returns:
        Настроенный logger
    """
    # Конфигурируем корневой logger
    logging.basicConfig(
        level=getattr(logging, level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Настраиваем уровни для внешних библиотек
    logging.getLogger('telegram').setLevel(logging.INFO)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)

    # В debug режиме показываем больше информации
    if debug:
        logging.getLogger('llama_cpp').setLevel(logging.DEBUG)
        logging.getLogger('chromadb').setLevel(logging.DEBUG)
    else:
        logging.getLogger('llama_cpp').setLevel(logging.WARNING)
        logging.getLogger('chromadb').setLevel(logging.WARNING)

    return logging.getLogger(__name__)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Получение logger для модуля

    Args:
        name: Имя модуля (обычно __name__)

    Returns:
        Logger для модуля
    """
    return logging.getLogger(name or __name__)
