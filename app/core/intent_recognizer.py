"""
Распознаватель намерений пользователя
"""
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from app.config.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TimeIntent:
    """Класс для хранения распознанного временного намерения"""
    period: Optional[timedelta] = None
    is_yesterday: bool = False
    is_all_time: bool = False
    is_now: bool = False
    exact_minutes: Optional[int] = None
    raw_text: str = ""


@dataclass
class Intent:
    """Базовый класс намерения"""
    type: str
    confidence: float
    time_intent: Optional[TimeIntent] = None
    raw_text: str = ""


class IntentRecognizer:
    """Распознаватель намерений пользователя с улучшенным NLP"""

    def __init__(self):
        """Инициализация распознавателя"""
        # Определяем ключевые слова для разных типов намерений
        self.summary_keywords = {
            'высокий': ['договорились', 'сводка', 'протокол', 'резюме', 'итог', 'суммари'],
            'средний': ['что было', 'обсуждали', 'говорили', 'решили'],
            'низкий': ['расскажи', 'покажи', 'что']
        }

        self.time_keywords = {
            'now': ['сейчас', 'только что', 'прямо сейчас', 'минуту назад'],
            'yesterday': ['вчера', 'вчерашн'],
            'all_time': ['всё время', 'с начала', 'всегда', 'за всё время'],
            'recent': ['недавно', 'последнее время', 'за последние']
        }

        # Паттерны для извлечения времени
        self.time_patterns = [
            (r'за\s+(\d+)\s*минут', 'minutes'),
            (r'за\s+(\d+)\s*час', 'hours'),
            (r'за\s+(\d+)\s*дн', 'days'),
            (r'за\s+(\d+)\s*недел', 'weeks'),
            (r'последн[ие]{0,2}\s+(\d+)\s*минут', 'minutes'),
            (r'последн[ие]{0,2}\s+(\d+)\s*час', 'hours'),
            (r'последн[ие]{0,2}\s+(\d+)\s*дн', 'days'),
        ]

    def recognize_intent(self, text: str, bot_username: str) -> Optional[Intent]:
        """
        Распознавание намерения пользователя

        Args:
            text: Текст сообщения
            bot_username: Имя бота для проверки обращения

        Returns:
            Распознанное намерение или None
        """
        # Проверяем, обращаются ли к боту
        if f"@{bot_username}" not in text:
            return None

        # Очищаем текст от упоминания бота
        clean_text = text.replace(f"@{bot_username}", "").strip()

        # Распознаем тип намерения
        intent_type, confidence = self._classify_intent(clean_text)

        if intent_type == 'summary':
            time_intent = self._extract_time_intent(clean_text)
            return Intent(
                type=intent_type,
                confidence=confidence,
                time_intent=time_intent,
                raw_text=text
            )

        return None

    def _classify_intent(self, text: str) -> tuple[str, float]:
        """
        Классификация типа намерения

        Args:
            text: Очищенный текст

        Returns:
            Тип намерения и уверенность
        """
        text_lower = text.lower()

        # Подсчитываем совпадения ключевых слов для сводки
        summary_score = 0
        total_words = len(text_lower.split())

        for priority, keywords in self.summary_keywords.items():
            weight = {'высокий': 3, 'средний': 2, 'низкий': 1}[priority]
            for keyword in keywords:
                if keyword in text_lower:
                    summary_score += weight

        # Нормализуем счет
        if total_words > 0:
            confidence = min(summary_score / (total_words * 0.5), 1.0)
        else:
            confidence = 0

        # Проверяем пороговое значение
        if confidence > 0.3:
            return 'summary', confidence

        # Если есть вопросительные слова + временные маркеры = запрос сводки
        question_words = ['что', 'как', 'когда', 'где', 'почему']
        has_question = any(word in text_lower for word in question_words)
        has_time = any(
            any(keyword in text_lower for keyword in keywords)
            for keywords in self.time_keywords.values()
        )

        if has_question and has_time:
            return 'summary', 0.7

        return 'unknown', 0.0

    def _extract_time_intent(self, text: str) -> TimeIntent:
        """
        Извлечение временного намерения

        Args:
            text: Текст для анализа

        Returns:
            Объект TimeIntent
        """
        text_lower = text.lower()
        intent = TimeIntent(raw_text=text)

        # Проверяем ключевые слова времени
        for time_type, keywords in self.time_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                if time_type == 'now':
                    intent.is_now = True
                    intent.period = timedelta(minutes=10)
                elif time_type == 'yesterday':
                    intent.is_yesterday = True
                elif time_type == 'all_time':
                    intent.is_all_time = True
                break

        # Извлекаем точные временные интервалы
        for pattern, time_unit in self.time_patterns:
            match = re.search(pattern, text_lower)
            if match:
                value = int(match.group(1))
                intent.exact_minutes = value if time_unit == 'minutes' else None

                if time_unit == 'minutes':
                    intent.period = timedelta(minutes=value)
                elif time_unit == 'hours':
                    intent.period = timedelta(hours=value)
                elif time_unit == 'days':
                    intent.period = timedelta(days=value)
                elif time_unit == 'weeks':
                    intent.period = timedelta(weeks=value)
                break

        return intent

    def get_time_description(self, time_intent: TimeIntent, default_hours: int = 2) -> str:
        """
        Получение текстового описания временного интервала

        Args:
            time_intent: Временное намерение
            default_hours: Количество часов по умолчанию

        Returns:
            Текстовое описание
        """
        if time_intent.is_yesterday:
            return "за вчерашний день"
        elif time_intent.is_all_time:
            return "за всё время"
        elif time_intent.is_now:
            return "за последние 10 минут"
        elif time_intent.exact_minutes:
            return f"за последние {time_intent.exact_minutes} минут"
        elif time_intent.period:
            if time_intent.period.days > 0:
                return f"за последние {time_intent.period.days} дней"
            elif time_intent.period.seconds >= 3600:
                hours = time_intent.period.seconds // 3600
                return f"за последние {hours} часов"
            else:
                minutes = time_intent.period.seconds // 60
                return f"за последние {minutes} минут"
        else:
            return f"за последние {default_hours} часа"
