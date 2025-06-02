import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import message_cache, make_cache_key
from app.core.utils import hash_content
from app.database.models import Message

logger = logging.getLogger(__name__)


class MessageService:
    """Оптимизированный сервис для управления сообщениями"""

    async def save_message(self, db: AsyncSession, message_data: Dict[str, Any]) -> Message:
        """Сохранение сообщения с дедупликацией"""
        # Добавляем хеш контента для дедупликации
        if 'content' in message_data:
            message_data['content_hash'] = hash_content(message_data['content'])

        message = Message(**message_data)
        db.add(message)
        await db.commit()
        await db.refresh(message)

        # Инвалидируем кеш
        cache_key = make_cache_key("chat_messages", message_data.get('chat_id'))
        await message_cache.delete(cache_key)

        return message

    async def get_chat_messages(
            self,
            db: AsyncSession,
            chat_id: str,
            hours_back: int = 24,
            limit: int = 1000,
            use_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """Получение сообщений чата с кешированием"""
        cache_key = make_cache_key("chat_messages", chat_id, hours_back, limit)

        if use_cache:
            cached_result = await message_cache.get(cache_key)
            if cached_result:
                return cached_result

        time_threshold = datetime.utcnow() - timedelta(hours=hours_back)

        # Оптимизированный запрос с join
        query = text("""
            SELECT 
                m.id, m.content, m.created_at, m.is_bot_message,
                u.first_name, u.last_name, u.telegram_username
            FROM messages m
            LEFT JOIN users u ON m.user_id = u.id
            WHERE m.chat_id = :chat_id 
                AND m.created_at >= :time_threshold
            ORDER BY m.created_at DESC
            LIMIT :limit
        """)

        result = await db.execute(
            query,
            {
                'chat_id': chat_id,
                'time_threshold': time_threshold,
                'limit': limit
            }
        )

        messages = []
        for row in result:
            username = row.telegram_username
            if not username and row.first_name:
                username = f"{row.first_name} {row.last_name or ''}".strip()

            messages.append({
                'id': row.id,
                'content': row.content,
                'created_at': row.created_at,
                'is_bot_message': row.is_bot_message,
                'username': username or 'Unknown'
            })

        # Обращаем порядок для хронологического
        messages.reverse()

        if use_cache:
            await message_cache.set(cache_key, messages, ttl=300)  # 5 минут

        return messages

    async def get_recent_messages_count(self, db: AsyncSession, chat_id: str, hours: int = 1) -> int:
        """Получение количества недавних сообщений"""
        time_threshold = datetime.utcnow() - timedelta(hours=hours)

        query = text("""
            SELECT COUNT(*) 
            FROM messages 
            WHERE chat_id = :chat_id 
                AND created_at >= :time_threshold
        """)

        result = await db.execute(
            query,
            {'chat_id': chat_id, 'time_threshold': time_threshold}
        )

        return result.scalar() or 0

    async def cleanup_old_messages(self, db: AsyncSession, days_old: int = 30) -> int:
        """Очистка старых сообщений для экономии места"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        query = text("""
            DELETE FROM messages 
            WHERE created_at < :cutoff_date 
                AND is_bot_message = false
        """)

        result = await db.execute(query, {'cutoff_date': cutoff_date})
        await db.commit()

        return result.rowcount
