from typing import Optional, Dict
from ldap3 import Server, Connection, ALL, SUBTREE
from app.config import Config
import logging

logger = logging.getLogger(__name__)


class LDAPService:
    """Сервис для работы с LDAP"""

    def __init__(self):
        self.server = Server(Config.LDAP_SERVER, get_info=ALL)

    async def find_user_by_telegram_id(self, telegram_id: int) -> Optional[Dict]:
        """Поиск пользователя в LDAP по telegram_id"""
        try:
            with Connection(
                    self.server,
                    user=Config.LDAP_BIND_DN,
                    password=Config.LDAP_BIND_PASSWORD,
                    auto_bind=True
            ) as conn:

                search_filter = Config.LDAP_USER_SEARCH_FILTER.format(telegram_id=telegram_id)

                conn.search(
                    search_base=Config.LDAP_USER_SEARCH_BASE,
                    search_filter=search_filter,
                    search_scope=SUBTREE,
                    attributes=[
                        'givenName', 'sn', 'mail', 'telephoneNumber',
                        'sAMAccountName', 'telegramId', 'telegramUsername'
                    ]
                )

                if conn.entries:
                    entry = conn.entries[0]
                    return {
                        'givenName': str(entry.givenName) if entry.givenName else '',
                        'sn': str(entry.sn) if entry.sn else '',
                        'mail': str(entry.mail) if entry.mail else '',
                        'telephoneNumber': str(entry.telephoneNumber) if entry.telephoneNumber else '',
                        'sAMAccountName': str(entry.sAMAccountName) if entry.sAMAccountName else '',
                        'telegramId': str(entry.telegramId) if entry.telegramId else '',
                        'telegramUsername': str(entry.telegramUsername) if entry.telegramUsername else ''
                    }

                return None

        except Exception as e:
            logger.error(f"Ошибка поиска пользователя в LDAP {telegram_id}: {e}")
            return None
