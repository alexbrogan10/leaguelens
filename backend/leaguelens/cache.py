"""Response caches. The clients depend on the ``Cache`` protocol, not a backend."""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy.orm import Session, sessionmaker

from leaguelens.models import HttpCache


def utcnow() -> datetime:
    return datetime.now(UTC)


class Cache(Protocol):
    def get(self, key: str) -> str | None: ...

    def set(self, key: str, value: str, ttl: timedelta | None, source: str = "") -> None:
        """Store ``value``. ``ttl=None`` means never expire."""
        ...


class MemoryCache:
    def __init__(self) -> None:
        self._data: dict[str, tuple[str, datetime | None]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> str | None:
        with self._lock:
            hit = self._data.get(key)
            if hit is None:
                return None
            value, expires = hit
            if expires is not None and expires <= utcnow():
                del self._data[key]
                return None
            return value

    def set(self, key: str, value: str, ttl: timedelta | None, source: str = "") -> None:
        with self._lock:
            self._data[key] = (value, None if ttl is None else utcnow() + ttl)


class DbCache:
    """Persistent cache in the ``http_cache`` table, fronted by a small memory cache."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._sf = session_factory
        self._mem = MemoryCache()

    def get(self, key: str) -> str | None:
        hit = self._mem.get(key)
        if hit is not None:
            return hit
        with self._sf() as s:
            row = s.get(HttpCache, key)
            if row is None:
                return None
            expires = row.expires_at
            if expires is not None:
                if expires.tzinfo is None:  # SQLite drops tzinfo
                    expires = expires.replace(tzinfo=UTC)
                if expires <= utcnow():
                    return None
            ttl = None if expires is None else expires - utcnow()
            self._mem.set(key, row.body, ttl)
            return row.body

    def set(self, key: str, value: str, ttl: timedelta | None, source: str = "") -> None:
        now = utcnow()
        self._mem.set(key, value, ttl)
        with self._sf() as s:
            s.merge(
                HttpCache(
                    key=key,
                    source=source,
                    body=value,
                    fetched_at=now,
                    expires_at=None if ttl is None else now + ttl,
                )
            )
            s.commit()
