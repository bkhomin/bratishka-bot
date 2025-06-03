"""
Сервис для работы с ChromaDB
"""
from typing import List, Dict, Tuple

import chromadb
from chromadb.config import Settings
from telegram import Message

from app.config.logging import get_logger
from app.config.settings import config

logger = get_logger(__name__)


class ChromaService:
    """Сервис для работы с векторной базой данных ChromaDB"""

    def __init__(self):
        """
        Инициализация сервиса ChromaDB
        """
        self.config = config.chroma
        self.client = None
        self.collections = {}
        self._connect()

    def _connect(self):
        """Подключение к ChromaDB"""
        try:
            self.client = chromadb.HttpClient(
                host=self.config.host,
                port=self.config.port,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )

            # Проверяем подключение
            self.client.heartbeat()
            logger.info(f"Подключено к ChromaDB: {self.config.host}:{self.config.port}")

        except Exception as e:
            logger.error(f"Ошибка подключения к ChromaDB: {e}")
            raise

    def get_collection_for_chat(self, chat_id: int) -> chromadb.Collection:
        """
        Получение или создание коллекции для конкретного чата

        Args:
            chat_id: ID чата

        Returns:
            Коллекция ChromaDB
        """
        collection_name = f"chat_{abs(chat_id)}"  # Используем abs для отрицательных ID

        if chat_id not in self.collections:
            try:
                self.collections[chat_id] = self.client.get_or_create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
                logger.debug(f"Получена коллекция для чата {chat_id}")
            except Exception as e:
                logger.error(f"Ошибка создания коллекции для чата {chat_id}: {e}")
                raise

        return self.collections[chat_id]

    def save_message(self, message: Message) -> bool:
        """
        Сохранение сообщения в векторную БД

        Args:
            message: Сообщение Telegram

        Returns:
            True если сохранено успешно
        """
        try:
            chat_id = message.chat_id
            collection = self.get_collection_for_chat(chat_id)

            # Подготавливаем текст
            message_text = message.text or message.caption or ""
            if not message_text:
                return False

            # Метаданные сообщения
            metadata = {
                "chat_id": str(chat_id),
                "message_id": str(message.message_id),
                "user_id": str(message.from_user.id),
                "username": message.from_user.username or message.from_user.first_name or "Unknown",
                "full_name": f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip(),
                "timestamp": int(message.date.timestamp()),
            }

            if message.reply_to_message:
                metadata["reply_to_message_id"] = str(message.reply_to_message.message_id)

            # Генерируем уникальный ID
            doc_id = f"{chat_id}_{message.message_id}"

            # Сохраняем в коллекцию
            collection.add(
                documents=[message_text],
                metadatas=[metadata],
                ids=[doc_id]
            )

            logger.debug(f"Сохранено сообщение {doc_id} из чата {chat_id}")
            return True

        except Exception as e:
            logger.error(f"Ошибка при сохранении сообщения: {e}")
            return False

    def get_messages_by_time(
        self,
        chat_id: int,
        start_timestamp: int,
        end_timestamp: int,
        limit: int = 1000
    ) -> List[Tuple[str, Dict]]:
        """
        Получение сообщений за временной период

        Args:
            chat_id: ID чата
            start_timestamp: Начальный timestamp
            end_timestamp: Конечный timestamp
            limit: Максимальное количество сообщений

        Returns:
            Список кортежей (текст, метаданные)
        """
        try:
            collection = self.get_collection_for_chat(chat_id)

            # Формируем фильтр по времени
            where_filter = {
                "$and": [
                    {"timestamp": {"$gte": start_timestamp}},
                    {"timestamp": {"$lte": end_timestamp}}
                ]
            }

            # Получаем сообщения
            results = collection.query(
                query_texts=[""],
                n_results=limit,
                where=where_filter
            )

            # Объединяем документы с метаданными
            messages_with_metadata = list(zip(
                results['documents'][0],
                results['metadatas'][0]
            ))

            # Сортируем по времени
            messages_with_metadata.sort(key=lambda x: x[1]['timestamp'])

            logger.debug(f"Получено {len(messages_with_metadata)} сообщений из чата {chat_id}")
            return messages_with_metadata

        except Exception as e:
            logger.error(f"Ошибка при получении сообщений: {e}")
            return []

    def get_collection_stats(self, chat_id: int) -> Dict[str, int]:
        """
        Получение статистики коллекции чата

        Args:
            chat_id: ID чата

        Returns:
            Словарь со статистикой
        """
        try:
            collection = self.get_collection_for_chat(chat_id)
            count = collection.count()

            return {
                "total_messages": count,
                "chat_id": chat_id
            }

        except Exception as e:
            logger.error(f"Ошибка при получении статистики: {e}")
            return {"total_messages": 0, "chat_id": chat_id}

    def health_check(self) -> bool:
        """
        Проверка здоровья соединения с ChromaDB

        Returns:
            True если соединение работает
        """
        try:
            self.client.heartbeat()
            return True
        except Exception as e:
            logger.error(f"ChromaDB health check failed: {e}")
            return False
