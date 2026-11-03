"""线程安全的进程内 TTL 缓存，键命名规范：业务:实体:标识:版本。"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any


@dataclass
class _Entry:
    value: Any
    expires_at: float


class TTLCache:
    def __init__(self, maxsize: int = 2048) -> None:
        self._data: OrderedDict[str, _Entry] = OrderedDict()
        self._lock = threading.RLock()
        self.maxsize = maxsize
        self.hits = 0
        self.misses = 0

    def get(self, key: str, default: Any = None) -> Any:
        now = time.monotonic()
        with self._lock:
            entry = self._data.get(key)
            if not entry:
                self.misses += 1
                return default
            if entry.expires_at <= now:
                self._data.pop(key, None)
                self.misses += 1
                return default
            self._data.move_to_end(key)
            self.hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: int = 60) -> None:
        if ttl <= 0:
            return
        with self._lock:
            self._data[key] = _Entry(value=value, expires_at=time.monotonic() + ttl)
            self._data.move_to_end(key)
            while len(self._data) > self.maxsize:
                self._data.popitem(last=False)

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def delete_prefix(self, prefix: str) -> int:
        with self._lock:
            keys = [key for key in self._data if key.startswith(prefix)]
            for key in keys:
                self._data.pop(key, None)
            return len(keys)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def stats(self) -> dict:
        with self._lock:
            total = self.hits + self.misses
            return {
                "size": len(self._data),
                "hits": self.hits,
                "misses": self.misses,
                "hitRate": round(self.hits / total, 3) if total else 0,
                "maxsize": self.maxsize,
            }


cache = TTLCache()


def cached(key: str, ttl: int, loader):
    value = cache.get(key)
    if value is not None:
        return value
    value = loader()
    cache.set(key, value, ttl)
    return value
