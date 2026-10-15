"""Tokens de acción por mail C-03 (design D6) — JWT `type='action'`, un uso.

El consumo se registra como hash sha256 en `auth:action_consumed:<sha256>`
(Redis o memoria, misma interfaz); nunca el token crudo. Base para C-09
(confirmar/cancelar y `mis-turnos` desde el mail, P12).
"""

import hashlib
import logging
import time
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from app.core.security.jwt import AuthError, decode_and_validate
from app.core.security.jwt import create_action_token as _issue
from app.core.settings import get_settings
from app.infra.redis.client import ActionRedis, try_redis_client

logger = logging.getLogger("turnos-odontologia")

PREFIX = "auth:action_consumed:"


class ActionTokenStore:
    """Set de hashes consumidos con TTL (single-use); reloj inyectable."""

    def __init__(
        self,
        client: ActionRedis | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client
        self._clock = clock
        self._memory: dict[str, float] = {}

    @staticmethod
    def token_hash(token: str) -> str:
        """sha256 hex del token (lo único que se persiste, nunca raw)."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @classmethod
    def _key(cls, token: str) -> str:
        return f"{PREFIX}{cls.token_hash(token)}"

    def is_consumed(self, token: str) -> bool:
        """True si el hash ya fue consumido y vigente."""
        if self._client is not None:
            return bool(self._client.exists(self._key(token)))
        expiry = self._memory.get(self.token_hash(token))
        if expiry is None:
            return False
        if self._clock() >= expiry:
            del self._memory[self.token_hash(token)]
            return False
        return True

    def consume(self, token: str, ttl_seconds: int) -> bool:
        """Marca el hash como usado; False si ya estaba (reuso → rechazar)."""
        if self._client is not None:
            return self._client.set(self._key(token), "1", ex=ttl_seconds, nx=True) is True
        if self.is_consumed(token):
            return False
        self._memory[self.token_hash(token)] = self._clock() + ttl_seconds
        return True

    def debug_keys(self) -> list[str]:
        """Solo tests: hashes persistidos (verifica que nunca hay raw)."""
        if self._client is not None:
            return ["<redis>"]
        return [f"{PREFIX}{h}" for h in self._memory]


def build_action_store(
    redis_url: str | None,
    *,
    clock: Callable[[], float] = time.monotonic,
) -> ActionTokenStore:
    """Fábrica con fallback: Redis o memoria (warning ya logueado en `client`)."""
    return ActionTokenStore(client=try_redis_client(redis_url), clock=clock)


def issue_action_token(
    destino: str,
    proposito: str,
    *,
    secret: str | None = None,
    action_min: int | None = None,
    ttl_override: timedelta | None = None,
) -> str:
    """Emite mail-action JWT separado (TTL `JWT_ACTION_MIN`; seam `ttl_override`)."""
    settings = get_settings()
    return _issue(
        sub=destino,
        secret=secret or settings.jwt_secret,
        proposito=proposito,
        action_min=action_min or settings.jwt_action_min,
        ttl_override=ttl_override,
    )


def validate_action_token(
    token: str, store: ActionTokenStore, *, secret: str | None = None
) -> dict[str, Any]:
    """Valida un uso: `type='action'`, vigente y no consumido (sino AuthError).

    Expirado → `ExpiredAuthError` explícito (C-09 lo mapea a mensaje al paciente).
    """
    settings = get_settings()
    claims = decode_and_validate(token, "action", secret or settings.jwt_secret)
    if not store.consume(token, settings.jwt_action_min * 60):
        raise AuthError("token de acción ya usado")
    return claims
