"""
Базовая логика приложения
"""

from app.config.logging import setup_logging, get_logger
from .intent_recognizer import IntentRecognizer, TimeIntent, Intent

__all__ = ['setup_logging', 'get_logger', 'IntentRecognizer', 'TimeIntent', 'Intent']
