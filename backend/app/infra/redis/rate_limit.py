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
LIMIT = 5
WINDOW_SECONDS = 60


def login_key(ip: str, email: str) -> str:
    """Llave `auth:ratelimit:<ip>:<sha16(email.lower())>` (P12 rate-limit)."""
    digest = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:16]
    return f"{PREFIX}{ip}:{digest}"


class LoginRateLimiter:
    """Ventana fija: True = intento permitido y contado; False = 429."""

    def __init__(
        self,
        client: RateLimitRedis | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._clock = clock
        self._memory: dict[str, tuple[int, float]] = {}

    def check_and_count(self, key: str) -> bool:
        if self._client is not None:
            count = self._client.incr(key)
            if count == 1:
                self._client.expire(key, WINDOW_SECONDS)
            return count <= LIMIT
        now = self._clock()
        count, start = self._memory.get(key, (0, now))
        if now - start >= WINDOW_SECONDS:
            count, start = 0, now
        count += 1
        self._memory[key] = (count, start)
        return count <= LIMIT


def build_rate_limiter(
    redis_url: str | None,
    *,
    clock: Callable[[], float] = time.monotonic,
) -> LoginRateLimiter:
    """Fábrica con fallback: Redis o memoria (warning ya logueado en `client`)."""
    return LoginRateLimiter(client=try_redis_client(redis_url), clock=clock)
