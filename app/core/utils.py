import hashlib
import re
from typing import List, Dict, Any


def hash_content(content: str) -> str:
    """Создание SHA256 хеша контента"""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def extract_time_period(message_text: str) -> int:
    """Извлечение временного периода из сообщения"""
    message_lower = message_text.lower()

    # Поиск конкретных упоминаний времени
    if 'час' in message_lower:
        match = re.search(r'(\d+)\s*час', message_lower)
        if match:
            return int(match.group(1))
        else:
            return 1  # "последний час"

    elif any(word in message_lower for word in ['день', 'сутки']):
        return 24

    elif 'неделя' in message_lower:
        return 168  # 7 * 24

    else:
        return 24  # По умолчанию


def is_bot_mentioned(message_text: str, bot_names: List[str]) -> bool:
    """Проверка упоминания бота в сообщении"""
    message_lower = message_text.lower()
    return any(name.lower() in message_lower for name in bot_names)


def format_conversation(messages: List[Dict[str, Any]]) -> str:
    """Форматирование переписки для анализа"""
    conversation_lines = []

    for msg in messages:
        timestamp = msg['created_at'].strftime("%H:%M")
        username = msg.get('username', 'Unknown')
        content = msg['content']

        if msg.get('is_bot_message'):
            username = "🤖 Bratishka"

        conversation_lines.append(f"[{timestamp}] {username}: {content}")

    return "\n".join(conversation_lines)


def chunk_messages(messages: List[Any], max_chunk_size: int = 100) -> List[List[Any]]:
    """Разбиение сообщений на чанки для обработки"""
    chunks = []
    for i in range(0, len(messages), max_chunk_size):
        chunks.append(messages[i:i + max_chunk_size])
    return chunks


def validate_email(email: str) -> bool:
    """Простая валидация email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_phone(phone: str) -> bool:
    """Простая валидация телефона"""
    cleaned = re.sub(r'[^\d+]', '', phone)
    return len(cleaned) >= 10


def safe_int(value: Any, default: int = 0) -> int:
    """Безопасное преобразование в int"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default
