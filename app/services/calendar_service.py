import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from app.services.email_service import EmailService
from app.core.utils import validate_email
import logging

logger = logging.getLogger(__name__)


class CalendarService:
    """Сервис для работы с календарными событиями"""

    def __init__(self, email_service: EmailService):
        self.email_service = email_service

    async def create_meeting(
            self,
            title: str,
            date_str: str,
            time_str: str,
            duration_minutes: int,
            description: str,
            attendees: List[str],
            organizer_email: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Создание встречи и отправка приглашений

        Args:
            title: Название встречи
            date_str: Дата в формате DD.MM.YYYY или YYYY-MM-DD
            time_str: Время в формате HH:MM
            duration_minutes: Продолжительность в минутах
            description: Описание встречи
            attendees: Список email участников
            organizer_email: Email организатора (опционально)

        Returns:
            Dict с результатом создания встречи
        """
        try:
            # Парсинг даты и времени
            start_datetime = self._parse_datetime(date_str, time_str)
            if not start_datetime:
                return {
                    'status': 'error',
                    'message': f'Некорректный формат даты/времени: {date_str} {time_str}'
                }

            end_datetime = start_datetime + timedelta(minutes=duration_minutes)

            # Валидация участников
            valid_attendees = []
            for email in attendees:
                if validate_email(email):
                    valid_attendees.append(email)
                else:
                    logger.warning(f"Некорректный email: {email}")

            if not valid_attendees:
                return {
                    'status': 'error',
                    'message': 'Нет валидных email адресов участников'
                }

            # Создание ICS контента
            ics_content = self._create_ics_content(
                title, start_datetime, end_datetime, description,
                valid_attendees, organizer_email
            )

            # Отправка приглашений
            duration_str = self._format_duration(duration_minutes)

            email_result = await self.email_service.send_meeting_invite(
                to_emails=valid_attendees,
                meeting_title=title,
                meeting_date=start_datetime.strftime('%d.%m.%Y'),
                meeting_time=start_datetime.strftime('%H:%M'),
                duration=duration_str,
                description=description,
                ics_content=ics_content
            )

            if email_result['status'] == 'success':
                return {
                    'status': 'success',
                    'message': 'Встреча создана и приглашения отправлены',
                    'meeting_info': {
                        'title': title,
                        'start_time': start_datetime.isoformat(),
                        'end_time': end_datetime.isoformat(),
                        'duration_minutes': duration_minutes,
                        'attendees': valid_attendees,
                        'description': description
                    },
                    'email_result': email_result
                }
            else:
                return {
                    'status': 'partial',
                    'message': 'Встреча создана, но ошибка отправки приглашений',
                    'email_error': email_result['message']
                }

        except Exception as e:
            logger.error(f"Ошибка создания встречи: {e}")
            return {
                'status': 'error',
                'message': f'Ошибка создания встречи: {str(e)}'
            }

    def _parse_datetime(self, date_str: str, time_str: str) -> Optional[datetime]:
        """Парсинг даты и времени в различных форматах"""
        try:
            # Обработка относительных дат
            date_str = date_str.lower().strip()
            today = datetime.now().date()

            if date_str in ['сегодня', 'today']:
                target_date = today
            elif date_str in ['завтра', 'tomorrow']:
                target_date = today + timedelta(days=1)
            elif date_str in ['послезавтра']:
                target_date = today + timedelta(days=2)
            elif 'через' in date_str:
                # "через N дней"
                import re
                match = re.search(r'через\s+(\d+)\s+день', date_str)
                if match:
                    days = int(match.group(1))
                    target_date = today + timedelta(days=days)
                else:
                    target_date = None
            else:
                # Парсинг конкретных дат
                target_date = self._parse_date_formats(date_str)

            if not target_date:
                return None

            # Парсинг времени
            time_str = time_str.strip()
            try:
                # Формат HH:MM
                hour, minute = map(int, time_str.split(':'))
                if 0 <= hour <= 23 and 0 <= minute <= 59:
                    return datetime.combine(target_date, datetime.min.time().replace(hour=hour, minute=minute))
            except (ValueError, IndexError):
                pass

            # Попробуем парсинг времени в других форматах
            try:
                # Только час
                hour = int(time_str)
                if 0 <= hour <= 23:
                    return datetime.combine(target_date, datetime.min.time().replace(hour=hour))
            except ValueError:
                pass

            return None

        except Exception as e:
            logger.error(f"Ошибка парсинга даты/времени {date_str} {time_str}: {e}")
            return None

    def _parse_date_formats(self, date_str: str) -> Optional[datetime.date]:
        """Парсинг различных форматов дат"""
        formats = [
            '%d.%m.%Y',  # 25.12.2024
            '%d.%m.%y',  # 25.12.24
            '%d/%m/%Y',  # 25/12/2024
            '%d-%m-%Y',  # 25-12-2024
            '%Y-%m-%d',  # 2024-12-25
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        return None

    def _create_ics_content(
            self,
            title: str,
            start_datetime: datetime,
            end_datetime: datetime,
            description: str,
            attendees: List[str],
            organizer_email: Optional[str] = None
    ) -> str:
        """Создание ICS файла для календарного события"""

        # Генерация уникального UID
        uid = f"{uuid.uuid4()}@bratishka-bot"

        # Форматирование времени для ICS (UTC)
        start_utc = start_datetime.strftime('%Y%m%dT%H%M%S')
        end_utc = end_datetime.strftime('%Y%m%dT%H%M%S')
        created_utc = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')

        # Подготовка участников
        attendees_lines = []
        for email in attendees:
            attendees_lines.append(f"ATTENDEE;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE:mailto:{email}")

        # Организатор
        organizer_line = f"ORGANIZER:mailto:{organizer_email or 'bratishka@company.com'}"

        # Экранирование специальных символов в описании
        description_escaped = description.replace('\n', '\\n').replace(',', '\\,').replace(';', '\\;')
        title_escaped = title.replace(',', '\\,').replace(';', '\\;')

        ics_content = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Bratishka AI Agent//Calendar Event//EN
CALSCALE:GREGORIAN
METHOD:REQUEST
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{created_utc}
DTSTART:{start_utc}
DTEND:{end_utc}
SUMMARY:{title_escaped}
DESCRIPTION:{description_escaped}
{organizer_line}
{chr(10).join(attendees_lines)}
STATUS:CONFIRMED
TRANSP:OPAQUE
SEQUENCE:0
CLASS:PUBLIC
END:VEVENT
END:VCALENDAR"""

        return ics_content

    def _format_duration(self, minutes: int) -> str:
        """Форматирование продолжительности"""
        if minutes < 60:
            return f"{minutes} мин"
        else:
            hours = minutes // 60
            remaining_minutes = minutes % 60
            if remaining_minutes == 0:
                return f"{hours} час" + ("а" if hours in [2, 3, 4] else "ов")
            else:
                return f"{hours} час {remaining_minutes} мин"

    async def extract_meeting_info_from_text(self, text: str, llm_service) -> Dict[str, Any]:
        """Извлечение информации о встрече из текста с помощью LLM"""
        try:
            current_date = datetime.now().strftime('%d.%m.%Y')

            prompt = f"""Извлеки из текста информацию о встрече. Сегодня {current_date}.

Текст: {text}

Верни информацию в строгом формате:
TITLE: [название встречи]
DATE: [дата в формате DD.MM.YYYY, если упомянуто "завтра", "сегодня" и т.д. - рассчитай от сегодняшней даты]
TIME: [время в формате HH:MM, если не указано - используй 14:00]
DURATION: [продолжительность в минутах, если не указано - используй 60]
DESCRIPTION: [краткое описание на основе контекста]

Если какая-то информация отсутствует, используй разумные значения по умолчанию."""

            result = await llm_service.generate(prompt, max_tokens=256)

            # Парсинг результата
            info = {}
            lines = result.split('\n')

            for line in lines:
                line = line.strip()
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip().upper()
                    value = value.strip()

                    if key == 'TITLE':
                        info['title'] = value
                    elif key == 'DATE':
                        info['date'] = value
                    elif key == 'TIME':
                        info['time'] = value
                    elif key == 'DURATION':
                        try:
                            info['duration_minutes'] = int(''.join(filter(str.isdigit, value)))
                        except:
                            info['duration_minutes'] = 60
                    elif key == 'DESCRIPTION':
                        info['description'] = value

            # Значения по умолчанию
            if 'title' not in info:
                info['title'] = 'Встреча'
            if 'date' not in info:
                info['date'] = (datetime.now() + timedelta(days=1)).strftime('%d.%m.%Y')
            if 'time' not in info:
                info['time'] = '14:00'
            if 'duration_minutes' not in info:
                info['duration_minutes'] = 60
            if 'description' not in info:
                info['description'] = 'Встреча по обсуждению рабочих вопросов'

            return {
                'status': 'success',
                'meeting_info': info
            }

        except Exception as e:
            logger.error(f"Ошибка извлечения информации о встрече: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }
