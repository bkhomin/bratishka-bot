import logging
from datetime import datetime
from typing import List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import context_cache, make_cache_key
from app.core.llm_pool import OptimizedLLM
from app.core.utils import format_conversation
from app.services.message_service import MessageService

logger = logging.getLogger(__name__)


class SummaryService:
    """Оптимизированный сервис для создания сводок"""

    def __init__(self):
        self.llm = OptimizedLLM()
        self.message_service = MessageService()

    async def create_chat_summary(
            self,
            db: AsyncSession,
            chat_id: str,
            hours_back: int = 24,
            include_reasoning: bool = False,
            use_cache: bool = False
    ) -> Dict[str, Any]:
        """Создание сводки с кешированием"""
        try:
            # Проверяем кеш
            cache_key = make_cache_key("summary", chat_id, hours_back, include_reasoning)

            if use_cache:
                cached_result = await context_cache.get(cache_key)
                if cached_result:
                    logger.info(f"Найдена кешированная сводка для чата {chat_id}")
                    return cached_result

            # Получение сообщений
            messages = await self.message_service.get_chat_messages(db, chat_id, hours_back)

            if not messages:
                return {
                    'status': 'empty',
                    'message': f'В чате нет сообщений за последние {hours_back} часов'
                }

            if len(messages) < 3:  # Слишком мало сообщений для анализа
                return {
                    'status': 'insufficient',
                    'message': 'Недостаточно сообщений для создания сводки'
                }

            # Форматирование переписки
            conversation_text = format_conversation(messages)

            # Создание промпта
            summary_prompt = self._create_optimized_prompt(conversation_text, hours_back)

            # Генерация сводки
            if include_reasoning:
                result = await self.llm.reasoning_generate(summary_prompt)
                summary_text = result["answer"]
                reasoning = result["thinking"]
            else:
                summary_text = await self.llm.generate(summary_prompt, max_tokens=512)
                reasoning = None

            # Подсчет участников
            unique_users = set()
            for msg in messages:
                if not msg['is_bot_message'] and msg['username'] != 'Unknown':
                    unique_users.add(msg['username'])

            result = {
                'status': 'success',
                'summary': summary_text,
                'reasoning': reasoning,
                'participants_count': len(unique_users),
                'messages_count': len(messages),
                'time_period': f'{hours_back} часов',
                'participants': list(unique_users)
            }

            # Кешируем результат
            if use_cache and result['status'] == 'success':
                await context_cache.set(cache_key, result, ttl=1800)  # 30 минут

            return result

        except Exception as e:
            logger.error(f"Ошибка создания сводки для чата {chat_id}: {e}")
            return {
                'status': 'error',
                'message': f'Ошибка при создании сводки: {str(e)}'
            }

    def _create_optimized_prompt(self, conversation: str, hours_back: int) -> str:
        """Создание оптимизированного промпта"""
        current_time = datetime.now().strftime("%H:%M %d.%m.%Y")

        # Ограничиваем размер контекста
        max_chars = 4000
        if len(conversation) > max_chars:
            conversation = "...\n" + conversation[-max_chars:]

        prompt = f"""Проанализируй корпоративную переписку за {hours_back} часов и создай краткую сводку.

Время: {current_time}

ПЕРЕПИСКА:
{conversation}

Создай структурированную сводку:
1. 📋 ОСНОВНЫЕ ТЕМЫ
2. ✅ РЕШЕНИЯ И ДОГОВОРЕННОСТИ  
3. ⏰ СРОКИ И ЗАДАЧИ
4. 👥 ОТВЕТСТВЕННЫЕ

Отвечай кратко и по делу."""

        return prompt

    async def extract_action_items(self, summary_text: str) -> List[Dict[str, Any]]:
        """Извлечение action items из сводки"""
        try:
            action_prompt = f"""Извлеки из следующей сводки конкретные задачи и действия:

{summary_text}

Верни в формате:
- ЗАДАЧА: описание
- ОТВЕТСТВЕННЫЙ: имя
- СРОК: дата

Если информации нет, укажи "не указано"."""

            result = await self.llm.generate(action_prompt, max_tokens=256)

            # Простой парсинг результата
            actions = []
            lines = result.split('\n')
            current_action = {}

            for line in lines:
                line = line.strip()
                if line.startswith('- ЗАДАЧА:'):
                    if current_action:
                        actions.append(current_action)
                    current_action = {'task': line.replace('- ЗАДАЧА:', '').strip()}
                elif line.startswith('- ОТВЕТСТВЕННЫЙ:'):
                    current_action['assignee'] = line.replace('- ОТВЕТСТВЕННЫЙ:', '').strip()
                elif line.startswith('- СРОК:'):
                    current_action['deadline'] = line.replace('- СРОК:', '').strip()

            if current_action:
                actions.append(current_action)

            return actions

        except Exception as e:
            logger.error(f"Ошибка извлечения action items: {e}")
            return []
