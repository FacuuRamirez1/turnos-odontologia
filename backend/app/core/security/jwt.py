"""JWT core C-03 (design D1+D3) — HS256, claims `sub/rol/jti/type`, leeway 30 s.

Choke point único: `decode_and_validate(expected_type=...)` rechaza reuso
cruzado (access como mail-token, refresh como access). `JWT_SECRET` llega
siempre por parámetro (solo env en callers, P5 — este módulo no lee env).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import jwt as pyjwt

LEEWAY_SECONDS = 30
ALGORITHM = "HS256"


class AuthError(Exception):
    """Token inválido, vencido o de tipo inesperado (callers → 401)."""


class ExpiredAuthError(AuthError):
    """Expirado con error explícito (lo distingue `action_tokens` para C-09)."""


def _issue(
    sub: str,
    rol: str,
    token_type: str,
    secret: str,
    lifetime: timedelta,
    odontologo_id: str | None = None,
    ttl_override: timedelta | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": sub,
        "rol": rol,
        "type": token_type,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + (ttl_override if ttl_override is not None else lifetime),
    }
    if odontologo_id is not None:
        payload["odontologo_id"] = odontologo_id
    if extra:
        payload.update(extra)
    return pyjwt.encode(payload, secret, algorithm=ALGORITHM)


def create_access_token(
    sub: str,
    rol: str,
    secret: str,
    odontologo_id: str | None = None,
    access_min: int = 15,
    ttl_override: timedelta | None = None,
) -> str:
    """Access corto (default 15 min). `ttl_override` es seam solo para tests."""
    return _issue(
        sub, rol, "access", secret, timedelta(minutes=access_min), odontologo_id, ttl_override
    )


def create_refresh_token(
    sub: str,
    rol: str,
    secret: str,
    odontologo_id: str | None = None,
    refresh_dias: int = 7,
    ttl_override: timedelta | None = None,
) -> str:
    """Refresh largo (default 7 días), transportado en cookie HttpOnly."""
    return _issue(
        sub, rol, "refresh", secret, timedelta(days=refresh_dias), odontologo_id, ttl_override
    )


def create_action_token(
    sub: str,
    secret: str,
    proposito: str,
    action_min: int = 15,
    ttl_override: timedelta | None = None,
) -> str:
    """Mail-action JWT separado (type='action', default 15 min, un solo uso)."""
    return _issue(
        sub, "paciente", "action", secret, timedelta(minutes=action_min), None,
        ttl_override, {"proposito": proposito},
    )


def decode_and_validate(token: str, expected_type: str, secret: str) -> dict[str, Any]:
    """Decodifica HS256 exigiendo claims y `type`; cualquier desvío → AuthError."""
    try:
        claims = cast(
            "dict[str, Any]",
            pyjwt.decode(
                token,
                secret,
                algorithms=[ALGORITHM],
                leeway=LEEWAY_SECONDS,
                options={"require": ["sub", "type", "jti", "exp"]},
            ),
        )
    except pyjwt.ExpiredSignatureError as exc:
        raise ExpiredAuthError("token expirado") from exc
    except pyjwt.PyJWTError as exc:
        raise AuthError(f"token inválido: {exc}") from exc
    if claims.get("type") != expected_type:
        raise AuthError(f"tipo de token inesperado: se esperaba '{expected_type}'")
    return claims
