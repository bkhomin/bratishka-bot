import logging
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional, Dict, Any

import aiosmtplib

from app.config import Config

logger = logging.getLogger(__name__)


class EmailService:
    """Сервис для отправки email уведомлений"""

    def __init__(self):
        self.smtp_config = {
            'hostname': Config.EMAIL_HOST,
            'port': Config.EMAIL_PORT,
            'username': Config.EMAIL_USER,
            'password': Config.EMAIL_PASSWORD,
            'use_tls': True,
            'start_tls': True if Config.EMAIL_PORT in [587, 25] else False
        }
        self._validate_config()

    def _validate_config(self) -> None:
        """Валидация конфигурации email"""
        required_fields = ['hostname', 'username', 'password']
        missing_fields = [field for field in required_fields
                          if not getattr(Config, f'EMAIL_{field.upper()}', None)]

        if missing_fields:
            logger.warning(f"Email конфигурация неполная. Отсутствуют: {missing_fields}")

    @property
    def is_configured(self) -> bool:
        """Проверка корректности конфигурации"""
        return bool(Config.EMAIL_HOST and Config.EMAIL_USER and Config.EMAIL_PASSWORD)

    async def send_email(
            self,
            to_emails: List[str],
            subject: str,
            body: str,
            html_body: Optional[str] = None,
            attachments: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Отправка email

        Args:
            to_emails: Список получателей
            subject: Тема письма
            body: Текст письма
            html_body: HTML версия письма (опционально)
            attachments: Список вложений в формате [{'data': bytes, 'filename': str, 'content_type': str}]

        Returns:
            Dict с результатом отправки
        """
        if not self.is_configured:
            return {
                'status': 'error',
                'message': 'Email не настроен. Проверьте конфигурацию EMAIL_* переменных'
            }

        if not to_emails:
            return {
                'status': 'error',
                'message': 'Не указаны получатели'
            }

        try:
            # Создание сообщения
            msg = MIMEMultipart('alternative')
            msg['From'] = Config.EMAIL_USER
            msg['To'] = ', '.join(to_emails)
            msg['Subject'] = subject

            # Добавление текстовой части
            text_part = MIMEText(body, 'plain', 'utf-8')
            msg.attach(text_part)

            # Добавление HTML части если есть
            if html_body:
                html_part = MIMEText(html_body, 'html', 'utf-8')
                msg.attach(html_part)

            # Добавление вложений
            if attachments:
                for attachment in attachments:
                    await self._add_attachment(msg, attachment)

            # Отправка
            await self._send_message(msg, to_emails)

            logger.info(f"Email отправлен успешно на {len(to_emails)} адресов")
            return {
                'status': 'success',
                'message': f'Email отправлен на {len(to_emails)} адресов',
                'recipients': to_emails
            }

        except Exception as e:
            logger.error(f"Ошибка отправки email: {e}")
            return {
                'status': 'error',
                'message': f'Ошибка отправки: {str(e)}'
            }

    async def send_protocol_email(
            self,
            to_emails: List[str],
            chat_title: str,
            protocol_text: str,
            participants: List[str],
            time_period: str
    ) -> Dict[str, Any]:
        """Отправка протокола встречи"""
        subject = f"Протокол встречи: {chat_title}"

        # Текстовая версия
        body = f"""Протокол встречи в чате "{chat_title}"
Период: {time_period}
Участники: {', '.join(participants)}

{protocol_text}

---
Сообщение отправлено автоматически ботом Bratishka"""

        # HTML версия
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 20px; }}
                .header {{ background: #f4f4f4; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                .content {{ background: white; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
                .participants {{ margin: 10px 0; padding: 10px; background: #f9f9f9; border-radius: 3px; }}
                .footer {{ margin-top: 20px; font-size: 12px; color: #666; }}
                pre {{ white-space: pre-wrap; word-wrap: break-word; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>📋 Протокол встречи: {chat_title}</h2>
                <p><strong>Период:</strong> {time_period}</p>
            </div>

            <div class="participants">
                <strong>👥 Участники:</strong> {', '.join(participants)}
            </div>

            <div class="content">
                <pre>{protocol_text}</pre>
            </div>

            <div class="footer">
                <p>Сообщение отправлено автоматически ботом Bratishka</p>
            </div>
        </body>
        </html>
        """

        return await self.send_email(to_emails, subject, body, html_body)

    async def send_meeting_invite(
            self,
            to_emails: List[str],
            meeting_title: str,
            meeting_date: str,
            meeting_time: str,
            duration: str,
            description: str,
            ics_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """Отправка приглашения на встречу"""
        subject = f"Приглашение на встречу: {meeting_title}"

        body = f"""Вы приглашены на встречу:

📅 Дата: {meeting_date}
⏰ Время: {meeting_time}
⏱ Продолжительность: {duration}
📋 Тема: {meeting_title}

Описание:
{description}

---
Сообщение отправлено автоматически ботом Bratishka"""

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 20px; }}
                .invite {{ background: #e8f4fd; padding: 20px; border-radius: 10px; border-left: 5px solid #2196F3; }}
                .details {{ margin: 15px 0; }}
                .detail-item {{ margin: 8px 0; padding: 8px; background: white; border-radius: 5px; }}
                .description {{ margin-top: 15px; padding: 15px; background: #f9f9f9; border-radius: 5px; }}
            </style>
        </head>
        <body>
            <div class="invite">
                <h2>📅 Приглашение на встречу</h2>

                <div class="details">
                    <div class="detail-item"><strong>📋 Тема:</strong> {meeting_title}</div>
                    <div class="detail-item"><strong>📅 Дата:</strong> {meeting_date}</div>
                    <div class="detail-item"><strong>⏰ Время:</strong> {meeting_time}</div>
                    <div class="detail-item"><strong>⏱ Продолжительность:</strong> {duration}</div>
                </div>

                <div class="description">
                    <strong>Описание:</strong><br>
                    {description.replace(chr(10), '<br>')}
                </div>
            </div>

            <p style="margin-top: 20px; font-size: 12px; color: #666;">
                Сообщение отправлено автоматически ботом Bratishka
            </p>
        </body>
        </html>
        """

        attachments = []
        if ics_content:
            attachments.append({
                'data': ics_content.encode('utf-8'),
                'filename': 'meeting.ics',
                'content_type': 'text/calendar'
            })

        return await self.send_email(to_emails, subject, body, html_body, attachments)

    async def _add_attachment(self, msg: MIMEMultipart, attachment: Dict[str, Any]) -> None:
        """Добавление вложения к сообщению"""
        try:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment['data'])
            encoders.encode_base64(part)

            part.add_header(
                'Content-Disposition',
                f'attachment; filename= {attachment["filename"]}'
            )

            if 'content_type' in attachment:
                part.set_type(attachment['content_type'])

            msg.attach(part)

        except Exception as e:
            logger.error(f"Ошибка добавления вложения {attachment.get('filename', 'unknown')}: {e}")

    async def _send_message(self, msg: MIMEMultipart, to_emails: List[str]) -> None:
        """Отправка сообщения через SMTP"""
        try:
            # Создание SMTP соединения
            smtp = aiosmtplib.SMTP(**self.smtp_config)

            # Подключение и аутентификация
            await smtp.connect()

            if self.smtp_config['start_tls']:
                await smtp.starttls()

            await smtp.login(self.smtp_config['username'], self.smtp_config['password'])

            # Отправка сообщения
            await smtp.send_message(msg, recipients=to_emails)

            # Закрытие соединения
            await smtp.quit()

        except Exception as e:
            logger.error(f"Ошибка SMTP отправки: {e}")
            raise

    async def test_connection(self) -> Dict[str, Any]:
        """Тестирование SMTP соединения"""
        if not self.is_configured:
            return {
                'status': 'error',
                'message': 'Email не настроен'
            }

        try:
            smtp = aiosmtplib.SMTP(**self.smtp_config)
            await smtp.connect()

            if self.smtp_config['start_tls']:
                await smtp.starttls()

            await smtp.login(self.smtp_config['username'], self.smtp_config['password'])
            await smtp.quit()

            return {
                'status': 'success',
                'message': 'SMTP соединение успешно'
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': f'Ошибка SMTP соединения: {str(e)}'
            }
    