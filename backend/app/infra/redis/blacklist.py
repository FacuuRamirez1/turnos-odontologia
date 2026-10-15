"""Blacklist de `jti` C-03 (design D4) — keys `auth:blacklist:<jti>`.

Redis con `SET NX EX` para el check-and-set atómico de rotación (refresh);
fallback dict en memoria con la misma interfaz + reloj inyectable (tests).
"""

import logging
import time
from collections.abc import Callable

from app.infra.redis.client import BlacklistRedis, try_redis_client

logger = logging.getLogger("turnos-odontologia")

PREFIX = "auth:blacklist:"


class TokenBlacklist:
    """Revocación por `jti` con TTL = remanente del token (expira sola)."""

    def __init__(
        self,
        client: BlacklistRedis | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._clock = clock
        self._memory: dict[str, float] = {}

    @staticmethod
    def _key(jti: str) -> str:
        return f"{PREFIX}{jti}"

    def add(self, jti: str, ttl_seconds: int) -> None:
        """Lista `jti` hasta dentro de `ttl_seconds` (idempotente)."""
        if self._client is not None:
            self._client.setex(self._key(jti), ttl_seconds, "1")
            return
        self._memory[jti] = self._clock() + ttl_seconds

    def is_listed(self, jti: str) -> bool:
        """True si `jti` está revocado y vigente (expirados se purgan)."""
        if self._client is not None:
            return bool(self._client.exists(self._key(jti)))
        expiry = self._memory.get(jti)
        if expiry is None:
            return False
        if self._clock() >= expiry:
            del self._memory[jti]
            return False
        return True

    def claim(self, jti: str, ttl_seconds: int) -> bool:
        """Check-and-set atómico: True si lo reclama, False si ya estaba listado."""
        if self._client is not None:
            return self._client.set(self._key(jti), "1", ex=ttl_seconds, nx=True) is True
        if self.is_listed(jti):
            return False
        self._memory[jti] = self._clock() + ttl_seconds
        return True


def build_blacklist(
    redis_url: str | None,
    *,
    clock: Callable[[], float] = time.monotonic,
) -> TokenBlacklist:
    """Fábrica con fallback: Redis o memoria (warning ya logueado en `client`)."""
    return TokenBlacklist(client=try_redis_client(redis_url), clock=clock)
