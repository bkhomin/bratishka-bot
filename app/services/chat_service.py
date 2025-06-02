import logging
from typing import Optional, List

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Chat, ChatParticipant, User

logger = logging.getLogger(__name__)


class ChatService:
    """Сервис для управления чатами"""

    async def get_or_create_chat(self, db: AsyncSession, telegram_chat_id: int, chat_data: dict) -> Chat:
        """Получение существующего чата или создание нового"""
        # Поиск существующего чата
        result = await db.execute(
            select(Chat).where(Chat.telegram_chat_id == telegram_chat_id)
        )
        chat = result.scalar_one_or_none()

        if chat:
            # Обновление данных чата если нужно
            if chat.title != chat_data.get('title') or chat.description != chat_data.get('description'):
                chat.title = chat_data.get('title')
                chat.description = chat_data.get('description')
                await db.commit()
            return chat

        # Создание нового чата
        chat = Chat(
            telegram_chat_id=telegram_chat_id,
            chat_type=chat_data.get('type', 'private'),
            title=chat_data.get('title'),
            description=chat_data.get('description')
        )

        db.add(chat)
        await db.commit()
        await db.refresh(chat)

        return chat

    async def add_participant(self, db: AsyncSession, chat_id: str, user_id: str) -> ChatParticipant:
        """Добавление участника в чат"""
        # Проверяем, не является ли пользователь уже участником
        result = await db.execute(
            select(ChatParticipant).where(
                and_(
                    ChatParticipant.chat_id == chat_id,
                    ChatParticipant.user_id == user_id
                )
            )
        )
        participant = result.scalar_one_or_none()

        if participant:
            if not participant.is_active:
                participant.is_active = True
                await db.commit()
            return participant

        # Создание нового участника
        participant = ChatParticipant(
            chat_id=chat_id,
            user_id=user_id,
            is_active=True
        )

        db.add(participant)
        await db.commit()
        await db.refresh(participant)

        return participant

    async def get_chat_participants(self, db: AsyncSession, chat_id: str) -> List[User]:
        """Получение списка участников чата"""
        result = await db.execute(
            select(User).join(ChatParticipant).where(
                and_(
                    ChatParticipant.chat_id == chat_id,
                    ChatParticipant.is_active == True
                )
            )
        )
        return result.scalars().all()

    async def get_chat_by_telegram_id(self, db: AsyncSession, telegram_chat_id: int) -> Optional[Chat]:
        """Получение чата по telegram_chat_id"""
        result = await db.execute(
            select(Chat).where(Chat.telegram_chat_id == telegram_chat_id)
        )
        return result.scalar_one_or_none()
