"""Cliente Redis compartido C-03 — `None` si inaccesible (design D4, fallback).

Protocolos por rol (documentan el duck-type usado): los dobles de tests los
heredan y mypy los verifica; `try_redis_client` retorna `Any` porque los
tipos `redis-py` mezclan sobrecargas sync/async (`Awaitable[Any] | Any`) y
ningún protocolo preciso los acepta.
"""

import logging
from typing import Any, Protocol

from redis import Redis

logger = logging.getLogger("turnos-odontologia")


class BlacklistRedis(Protocol):
    """Comandos usados por `TokenBlacklist` (ver redis-core)."""

    def exists(self, key: str) -> int: ...
    def setex(self, key: str, ttl: int, value: str) -> bool: ...
    def set(
        self, key: str, value: str, ex: int | None = None, nx: bool = False
    ) -> bool | None: ...


class RateLimitRedis(Protocol):
    """Comandos usados por `LoginRateLimiter`."""

    def incr(self, key: str) -> int: ...
    def expire(self, key: str, ttl: int) -> bool: ...


class ActionRedis(Protocol):
    """Comandos usados por `ActionTokenStore`."""

    def exists(self, key: str) -> int: ...
    def set(
        self, key: str, value: str, ex: int | None = None, nx: bool = False
    ) -> bool | None: ...


def try_redis_client(redis_url: str | None) -> Any:
    """Conecta con ping; ante cualquier fallo loguea warning y retorna None."""
    if not redis_url:
        return None
    try:
        client: Redis = Redis.from_url(
            redis_url, socket_connect_timeout=2, socket_timeout=2
        )
        client.ping()
        return client
    except Exception as exc:
        logger.warning("Redis inaccesible (%s): se usa fallback en memoria", exc)
        return None
