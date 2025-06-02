import asyncio
import logging
from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import async_session, db_manager
from app.services.auth_service import AuthService
from app.services.user_service import UserService, RegistrationService
from app.services.chat_service import ChatService
from app.services.message_service import MessageService
from app.services.summary_service import SummaryService
from app.services.email_service import EmailService
from app.services.calendar_service import CalendarService
from app.services.ldap_service import LDAPService
from app.core.llm_pool import llm_pool, OptimizedLLM
from app.core.utils import extract_time_period, is_bot_mentioned
from app.config import Config
from datetime import datetime
import sys

logger = logging.getLogger(__name__)


class BratishkaBot:
    """Оптимизированный Telegram бот Bratishka"""

    def __init__(self):
        self.app = None
        self.bot = None
        self._request_semaphore = asyncio.Semaphore(Config.MAX_CONCURRENT_REQUESTS)

        # Инициализация сервисов
        if Config.is_ldap_enabled():
            self.ldap_service = LDAPService()
            self.auth_service = AuthService(self.ldap_service)
        else:
            self.ldap_service = None
            self.auth_service = AuthService(None)

        self.user_service = UserService()
        self.registration_service = RegistrationService()
        self.chat_service = ChatService()
        self.message_service = MessageService()
        self.summary_service = SummaryService()

        # Email и календарь сервисы
        self.email_service = EmailService()
        self.calendar_service = CalendarService(self.email_service)

        # LLM
        self.llm = OptimizedLLM()

    async def initialize(self):
        """Инициализация бота"""
        logger.info("Инициализация Bratishka Bot...")

        # Валидация конфигурации
        config_errors = Config.validate()
        if config_errors:
            for error in config_errors:
                logger.error(error)
            raise ValueError("Ошибки конфигурации")

        # Инициализация базы данных
        await db_manager.init_pool()

        # Инициализация LLM пула
        await llm_pool.initialize()

        # Создание приложения
        self.app = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
        self.bot = self.app.bot

        # Регистрация обработчиков
        await self._register_handlers()

        logger.info("Bratishka Bot инициализирован")

    async def _register_handlers(self):
        """Регистрация обработчиков сообщений"""
        # Команды
        self.app.add_handler(CommandHandler("start", self.handle_start_command))
        self.app.add_handler(CommandHandler("help", self.handle_help_command))
        self.app.add_handler(CommandHandler("register", self.handle_register_command))
        self.app.add_handler(CommandHandler("status", self.handle_status_command))
        self.app.add_handler(CommandHandler("test_email", self.handle_test_email_command))

        # Обработчик всех сообщений
        self.app.add_handler(MessageHandler(filters.ALL, self.handle_message))

    async def handle_start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        await update.message.reply_text(
            f"🤖 Привет! Я {Config.BOT_NAME} - ваш корпоративный AI-помощник.\n\n"
            "💼 Мои возможности:\n"
            "📋 Создание протоколов встреч\n"
            "📅 Планирование событий\n"
            "📧 Отправка уведомлений\n"
            "🔍 Анализ переписки\n\n"
            f"Для работы упомяните меня: @{Config.TELEGRAM_BOT_USERNAME}"
        )

    async def handle_help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = f"""🤖 {Config.BOT_NAME} - Команды

📋 ПРОТОКОЛЫ:
• @{Config.BOT_NAME} подведи итог
• @{Config.BOT_NAME} что обсуждали за час?
• @{Config.BOT_NAME} основные решения

📅 ВСТРЕЧИ:
• @{Config.BOT_NAME} назначь встречу на завтра в 14:00
• @{Config.BOT_NAME} продолжим голосом в понедельник

📧 ОТПРАВКА:
• @{Config.BOT_NAME} отправь протокол всем
• @{Config.BOT_NAME} разошли итоги

⚙️ КОМАНДЫ:
• /start - информация о боте
• /help - эта справка
• /status - статус системы
• /test_email - тест email (только админы)"""

        await update.message.reply_text(help_text)

    async def handle_status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Статус системы"""
        async with async_session() as db:
            is_admin = await self.auth_service.is_admin(db, update.effective_user.id)

            if not is_admin:
                await update.message.reply_text("❌ Команда доступна только администраторам")
                return

            # Проверка состояния сервисов
            email_status = "✅ настроен" if self.email_service.is_configured else "❌ не настроен"
            ldap_status = "✅ включен" if Config.is_ldap_enabled() else "❌ отключен"

            status_text = f"""🔧 Статус системы {Config.BOT_NAME}

🤖 LLM: ✅ активен ({llm_pool.pool_size} экземпляров)
💾 База данных: ✅ подключена
📊 Кеш: ✅ активен
⚡ Ограничения: {Config.MAX_CONCURRENT_REQUESTS} запросов
📧 Email: {email_status}
📡 LDAP: {ldap_status}

📈 Метрики:
• Активных соединений: {len(llm_pool._pool._queue) if hasattr(llm_pool._pool, '_queue') else 'N/A'}
• Макс. параллельных запросов: {Config.MAX_CONCURRENT_REQUESTS}"""

            await update.message.reply_text(status_text)

    async def handle_test_email_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Тестирование email (только для админов)"""
        async with async_session() as db:
            is_admin = await self.auth_service.is_admin(db, update.effective_user.id)

            if not is_admin:
                await update.message.reply_text("❌ Команда доступна только администраторам")
                return

            if not self.email_service.is_configured:
                await update.message.reply_text("❌ Email не настроен. Проверьте переменные EMAIL_* в конфигурации")
                return

            await update.message.reply_text("🔄 Тестирую email соединение...")

            # Тест соединения
            test_result = await self.email_service.test_connection()

            if test_result['status'] == 'success':
                await update.message.reply_text("✅ Email соединение работает корректно")
            else:
                await update.message.reply_text(f"❌ Ошибка email: {test_result['message']}")

    async def handle_register_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /register"""
        telegram_id = update.effective_user.id

        async with async_session() as db:
            is_admin = await self.auth_service.is_admin(db, telegram_id)
            if not is_admin:
                await update.message.reply_text("❌ Нет прав для выполнения команды")
                return

            chat_id = update.effective_chat.id
            session = await self.registration_service.start_registration(db, telegram_id, chat_id)

            await update.message.reply_text(
                "🆕 Регистрация нового пользователя\n\n"
                f"{self.registration_service.STEP_PROMPTS['first_name']}"
            )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Основной обработчик с ограничением нагрузки"""
        async with self._request_semaphore:
            await self._process_message(update, context)

    async def _process_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка сообщения"""
        try:
            telegram_id = update.effective_user.id
            message_text = update.message.text or ""
            chat_id = update.effective_chat.id

            logger.debug(f"Получено сообщение от {telegram_id}: '{message_text[:50]}...'")

            async with async_session() as db:
                # Проверка регистрации
                registration_session = await self.registration_service.get_registration_session(db, telegram_id)
                if registration_session:
                    await self._handle_registration_process(update, db, telegram_id, message_text)
                    return

                # Аутентификация
                user, auth_message = await self.auth_service.check_access(db, telegram_id)
                logger.debug(f"Пользователь {telegram_id}: {'найден' if user else 'не найден'}")

                # Создание/обновление чата - ИСПРАВЛЕННАЯ ВЕРСИЯ
                chat_data = {
                    'type': update.effective_chat.type,
                    'title': getattr(update.effective_chat, 'title', None),
                    'description': getattr(update.effective_chat, 'description', None)
                }
                logger.debug(f"Обрабатывается чат: {chat_data}")

                chat = await self.chat_service.get_or_create_chat(db, chat_id, chat_data)

                # Добавление участника
                if user:
                    await self.chat_service.add_participant(db, chat.id, user.id)

                # Сохранение сообщения
                message_data = {
                    'telegram_message_id': update.message.message_id,
                    'chat_id': chat.id,
                    'user_id': user.id if user else None,
                    'content': message_text,
                    'message_type': 'text',
                    'is_bot_message': False,
                    'user_registered': user is not None
                }
                await self.message_service.save_message(db, message_data)

                # Обработка команд боту
                if self._is_bot_mentioned(message_text):
                    if user is None:
                        await update.message.reply_text(auth_message)
                        return

                    await self._process_bot_command(update, db, user, chat, message_text)

        except Exception as e:
            logger.error(f"Ошибка обработки сообщения: {e}")
            await update.message.reply_text("❌ Произошла ошибка при обработке")

    async def _handle_registration_process(self, update: Update, db: AsyncSession, telegram_id: int, message_text: str):
        """Обработка процесса регистрации"""
        if message_text.lower() in ['да', 'yes', 'подтверждаю']:
            result = await self.registration_service.confirm_registration(db, telegram_id)
        else:
            result = await self.registration_service.process_registration_step(db, telegram_id, message_text)

        status_emoji = {
            'error': '❌',
            'continue': '📝',
            'confirm': '✅',
            'success': '🎉'
        }

        emoji = status_emoji.get(result['status'], '📝')
        await update.message.reply_text(f"{emoji} {result['message']}")

    def _is_bot_mentioned(self, message_text: str) -> bool:
        """Проверка упоминания бота"""
        bot_names = [
            f"@{Config.BOT_NAME}",
            f"@{Config.TELEGRAM_BOT_USERNAME}",
            Config.BOT_NAME.lower()
        ]
        return is_bot_mentioned(message_text, bot_names)

    async def _process_bot_command(self, update: Update, db: AsyncSession, user, chat, message_text: str):
        """Обработка команд боту"""
        message_lower = message_text.lower()

        # Быстрая проверка активности чата
        recent_count = await self.message_service.get_recent_messages_count(db, chat.id, 1)
        if recent_count < 2:
            await update.message.reply_text("🤔 В чате слишком мало активности для анализа")
            return

        # Команды для создания протоколов
        if any(keyword in message_lower for keyword in
               ['подведи итог', 'протокол', 'договорились', 'обсуждали', 'итоги']):
            await self._handle_summary_request(update, db, chat, message_text)

        # Команды для создания встреч
        elif any(keyword in message_lower for keyword in
                 ['встреча', 'встречу', 'собрание', 'созвон', 'назначь', 'запланируй']):
            await self._handle_meeting_request(update, db, chat, user, message_text)

        # Команды для отправки протоколов
        elif any(keyword in message_lower for keyword in ['отправь', 'разошли']) and any(
                keyword in message_lower for keyword in ['протокол', 'итоги', 'сводку']):
            await self._handle_send_protocol_request(update, db, chat, message_text)

        # Общие вопросы
        else:
            await self._handle_general_question(update, message_text)

    async def _handle_summary_request(self, update: Update, db: AsyncSession, chat, message_text: str):
        """Обработка запроса на создание сводки"""
        hours_back = extract_time_period(message_text)

        await update.message.reply_text("📋 Анализирую переписку...")

        summary_result = await self.summary_service.create_chat_summary(
            db, chat.id, hours_back, include_reasoning=False
        )

        if summary_result['status'] == 'success':
            summary_text = f"📋 **ПРОТОКОЛ** за {summary_result['time_period']}\n\n"
            summary_text += summary_result['summary']
            summary_text += f"\n\n👥 Участников: {summary_result['participants_count']}"
            summary_text += f" | 💬 Сообщений: {summary_result['messages_count']}"

            await update.message.reply_text(summary_text, parse_mode='Markdown')
        else:
            await update.message.reply_text(f"❌ {summary_result['message']}")

    async def _handle_meeting_request(self, update: Update, db: AsyncSession, chat, user, message_text: str):
        """Обработка запроса на создание встречи"""
        await update.message.reply_text("📅 Планирую встречу...")

        try:
            # Извлечение информации о встрече из текста
            meeting_info_result = await self.calendar_service.extract_meeting_info_from_text(
                message_text, self.llm
            )

            if meeting_info_result['status'] != 'success':
                await update.message.reply_text("❌ Не удалось понять параметры встречи")
                return

            meeting_info = meeting_info_result['meeting_info']

            # Получение участников чата
            messages = await self.message_service.get_chat_messages(db, chat.id, 24)
            participants_emails = []

            # Собираем email участников из недавних сообщений
            participant_usernames = set()
            for msg in messages[-20:]:  # Последние 20 сообщений
                if not msg['is_bot_message'] and msg['username'] != 'Unknown':
                    participant_usernames.add(msg['username'])

            # Получаем email адреса участников из базы
            if participant_usernames:
                participants = await self.message_service.get_chat_participants_from_messages(db, chat.id, 24)
                participants_emails = [p.email for p in participants if p.email]

            if not participants_emails:
                # Показываем информацию о встрече без отправки
                response_text = f"""✅ **ВСТРЕЧА ЗАПЛАНИРОВАНА**

📋 Тема: {meeting_info['title']}
📅 Дата: {meeting_info['date']}
⏰ Время: {meeting_info['time']}
⏱ Продолжительность: {meeting_info['duration_minutes']} мин

📝 Описание: {meeting_info['description']}

⚠️ Email адреса участников не найдены. Для автоматической отправки приглашений убедитесь, что у участников указаны email в профилях."""

                await update.message.reply_text(response_text, parse_mode='Markdown')
                return

            # Создание встречи с отправкой приглашений
            create_result = await self.calendar_service.create_meeting(
                title=meeting_info['title'],
                date_str=meeting_info['date'],
                time_str=meeting_info['time'],
                duration_minutes=meeting_info['duration_minutes'],
                description=meeting_info['description'],
                attendees=participants_emails,
                organizer_email=user.email
            )

            if create_result['status'] == 'success':
                response_text = f"""✅ **ВСТРЕЧА СОЗДАНА И ПРИГЛАШЕНИЯ ОТПРАВЛЕНЫ**

📋 Тема: {meeting_info['title']}
📅 Дата: {meeting_info['date']}
⏰ Время: {meeting_info['time']}
⏱ Продолжительность: {meeting_info['duration_minutes']} мин
👥 Приглашены: {len(participants_emails)} участников

📧 Календарные приглашения отправлены на:
{', '.join(participants_emails)}"""

                await update.message.reply_text(response_text, parse_mode='Markdown')
            else:
                await update.message.reply_text(f"❌ {create_result['message']}")

        except Exception as e:
            logger.error(f"Ошибка планирования встречи: {e}")
            await update.message.reply_text("❌ Ошибка при планировании встречи")

    async def _handle_send_protocol_request(self, update: Update, db: AsyncSession, chat, message_text: str):
        """Обработка запроса на отправку протокола"""
        hours_back = extract_time_period(message_text)

        await update.message.reply_text("📧 Создаю и отправляю протокол...")

        # Создание сводки
        summary_result = await self.summary_service.create_chat_summary(db, chat.id, hours_back)

        if summary_result['status'] != 'success':
            await update.message.reply_text(f"❌ {summary_result['message']}")
            return

        # Получение участников с email
        participants = await self.message_service.get_chat_participants_from_messages(db, chat.id, hours_back)
        participants_with_email = [p for p in participants if p.email]

        if not participants_with_email:
            await update.message.reply_text("❌ У участников не указаны email адреса")
            return

        if not self.email_service.is_configured:
            await update.message.reply_text("❌ Email не настроен. Обратитесь к администратору")
            return

        # Отправка email
        try:
            emails_list = [p.email for p in participants_with_email]
            participants_names = [f"@{p.telegram_username}" if p.telegram_username else f"{p.first_name} {p.last_name}"
                                  for p in participants_with_email]

            email_result = await self.email_service.send_protocol_email(
                to_emails=emails_list,
                chat_title=chat.title or f"Чат {chat.telegram_chat_id}",
                protocol_text=summary_result['summary'],
                participants=participants_names,
                time_period=summary_result['time_period']
            )

            if email_result['status'] == 'success':
                await update.message.reply_text(
                    f"✅ **ПРОТОКОЛ ОТПРАВЛЕН**\n\n"
                    f"📧 Получатели ({len(emails_list)}):\n{', '.join(emails_list)}\n\n"
                    f"📋 Период: {summary_result['time_period']}\n"
                    f"💬 Сообщений: {summary_result['messages_count']}"
                )
            else:
                await update.message.reply_text(f"❌ Ошибка отправки: {email_result['message']}")

        except Exception as e:
            logger.error(f"Ошибка отправки протокола: {e}")
            await update.message.reply_text("❌ Ошибка при отправке протокола")

    async def _handle_general_question(self, update: Update, message_text: str):
        """Обработка общих вопросов"""
        try:
            system_prompt = f"""Ты - корпоративный AI-помощник {Config.BOT_NAME}. 
Отвечай кратко и по делу на вопросы о работе, планировании и организации.
Сегодня: {datetime.now().strftime('%d.%m.%Y %H:%M')}"""

            full_prompt = f"{system_prompt}\n\nВопрос: {message_text}"

            response = await self.llm.generate(full_prompt, max_tokens=256)
            await update.message.reply_text(response)

        except Exception as e:
            logger.error(f"Ошибка обработки общего вопроса: {e}")
            await update.message.reply_text("❌ Ошибка при обработке вопроса")

    async def start_polling(self):
        """Запуск бота"""
        logger.info("Запуск Bratishka Bot...")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling()

        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Остановка бота...")
        finally:
            await self.stop()

    async def stop(self):
        """Остановка бота"""
        logger.info("Завершение работы Bratishka Bot...")

        if self.app:
            try:
                # Проверяем что updater запущен перед остановкой
                if self.app.updater.running:
                    await self.app.updater.stop()
                await self.app.stop()
                await self.app.shutdown()
            except RuntimeError as e:
                # Игнорируем ошибки остановки не запущенного updater
                if "not running" not in str(e).lower():
                    raise

        await llm_pool.shutdown()
        await db_manager.close_pool()

        logger.info("Bratishka Bot остановлен")
