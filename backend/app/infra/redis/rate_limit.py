"""Rate-limit de login C-03 (design D4) — fixed window 60 s por hash IP+email.

La llave hashea el email (sha256, 16 hex): nada de PII largo en keys
(redis-core: sin strings largos como keys) y case-insensitive por `lower()`.
"""

import hashlib
import logging
import time
from collections.abc import Callable

from app.infra.redis.client import RateLimitRedis, try_redis_client

logger = logging.getLogger("turnos-odontologia")

PREFIX = "auth:ratelimit:"
DISPONIBILIDAD_PREFIX = "disponibilidad:ratelimit:"
LIMIT = 5
WINDOW_SECONDS = 60
DISPONIBILIDAD_LIMIT = 30


def login_key(ip: str, email: str) -> str:
    """Llave `auth:ratelimit:<ip>:<sha16(email.lower())>` (P12 rate-limit)."""
    digest = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:16]
    return f"{PREFIX}{ip}:{digest}"


def disponibilidad_key(ip: str) -> str:
    """Llave `disponibilidad:ratelimit:<ip>` (D-RATE 30/min por IP, C-04)."""
    return f"{DISPONIBILIDAD_PREFIX}{ip}"


class LoginRateLimiter:
    """Ventana fija parametrizable: True = intento permitido y contado; False = 429.

    Login usa el default (5, 60s); `GET /disponibilidad` usa (30, 60s) por IP
    (D-RATE). Mismo fallback memoria si Redis cae (ya aceptado en C-03).
    """

    def __init__(
        self,
        client: RateLimitRedis | None = None,
        limit: int = LIMIT,
        window_seconds: int = WINDOW_SECONDS,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._memory: dict[str, tuple[int, float]] = {}

    def check_and_count(self, key: str) -> bool:
        if self._client is not None:
            count = self._client.incr(key)
            if count == 1:
                self._client.expire(key, self._window)
            return count <= self._limit
        now = self._clock()
        count, start = self._memory.get(key, (0, now))
        if now - start >= self._window:
            count, start = 0, now
        count += 1
        self._memory[key] = (count, start)
        return count <= self._limit


def build_rate_limiter(
    redis_url: str | None,
    limit: int = LIMIT,
    window_seconds: int = WINDOW_SECONDS,
    *,
    clock: Callable[[], float] = time.monotonic,
) -> LoginRateLimiter:
    """Fábrica con fallback: Redis o memoria (warning ya logueado en `client`)."""
    return LoginRateLimiter(
        client=try_redis_client(redis_url), limit=limit, window_seconds=window_seconds, clock=clock
    )
