import asyncio
import hashlib
import time
from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class CacheEntry:
    value: Any
    timestamp: float
    ttl: float


class SimpleCache:
    """Простой in-memory кеш с TTL"""

    def __init__(self, default_ttl: float = 3600):
        self._cache: Dict[str, CacheEntry] = {}
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """Получение значения из кеша"""
        async with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None

            if time.time() - entry.timestamp > entry.ttl:
                del self._cache[key]
                return None

            return entry.value

    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Установка значения в кеш"""
        async with self._lock:
            self._cache[key] = CacheEntry(
                value=value,
                timestamp=time.time(),
                ttl=ttl or self._default_ttl
            )

    async def delete(self, key: str) -> None:
        """Удаление значения из кеша"""
        async with self._lock:
            self._cache.pop(key, None)

    async def clear(self) -> None:
        """Очистка всего кеша"""
        async with self._lock:
            self._cache.clear()

    def _cleanup_expired(self) -> None:
        """Очистка истекших записей"""
        current_time = time.time()
        expired_keys = [
            key for key, entry in self._cache.items()
            if current_time - entry.timestamp > entry.ttl
        ]
        for key in expired_keys:
            del self._cache[key]


def make_cache_key(*args, **kwargs) -> str:
    """Создание ключа кеша из аргументов"""
    key_data = str(args) + str(sorted(kwargs.items()))
    return hashlib.md5(key_data.encode()).hexdigest()


# Глобальные экземпляры кеша
message_cache = SimpleCache(300)  # 5 минут
context_cache = SimpleCache(3600)  # 1 час
user_cache = SimpleCache(1800)  # 30 минут
