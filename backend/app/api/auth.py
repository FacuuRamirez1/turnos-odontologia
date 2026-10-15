"""Router auth C-03 — login/refresh/logout/me (proposal + spec § auth-jwt-rbac).

- `POST /api/auth/login`: email (case-insensitive) + password → access en
  cuerpo + refresh en cookie HttpOnly; rate-limit 5/60 s por IP+email (P12).
- `POST /api/auth/refresh`: rotación atómica (check-and-set `jti`); reuso → 401.
- `POST /api/auth/logout`: blacklist de access + refresh vigentes.
- `GET /api/auth/me`: identidad del portador.
401 genérico sin distinguir causa (spec § login); schemas P2 `extra='forbid'`.
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import dependencies
from app.core.security.dependencies import Identity, get_current_identity
from app.core.security.jwt import (
    AuthError,
    ExpiredAuthError,
    create_access_token,
    create_refresh_token,
    decode_and_validate,
)
from app.core.security.passwords import dummy_verify, verify_password
from app.core.settings import get_settings
from app.infra.db.models import Usuario
from app.infra.db.session import get_db
from app.infra.redis.rate_limit import LoginRateLimiter, build_rate_limiter, login_key

logger = logging.getLogger("turnos-odontologia")

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
CREDENCIALES_INVALIDAS = "credenciales inválidas"


class LoginRequest(BaseModel):
    """Credenciales de staff — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=256)


class LoginResponse(BaseModel):
    """Par de tokens: access en cuerpo, refresh solo en cookie (nunca body)."""

    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    """Identidad del portador — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

    sub: str
    rol: str
    email: str
    odontologo_id: str | None = None


class OkResponse(BaseModel):
    """Ack genérico — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

    ok: bool


_rate_limiter: LoginRateLimiter | None = None


def get_rate_limiter() -> LoginRateLimiter:
    """Rate-limit activo (lazy de env; `reset_rate_limiter` lo renueva en tests)."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = build_rate_limiter(get_settings().redis_url)
    return _rate_limiter


def reset_rate_limiter() -> None:
    """Renueva el limitador en memoria (seam solo para tests)."""
    global _rate_limiter
    _rate_limiter = LoginRateLimiter(client=None)


def _token_pair(user: Usuario) -> tuple[str, str]:
    settings = get_settings()
    secret = dependencies.get_jwt_secret()
    odontologo_id = str(user.odontologo_id) if user.odontologo_id is not None else None
    access = create_access_token(
        sub=str(user.id),
        rol=user.rol,
        secret=secret,
        odontologo_id=odontologo_id,
        access_min=settings.jwt_access_min,
    )
    refresh = create_refresh_token(
        sub=str(user.id),
        rol=user.rol,
        secret=secret,
        odontologo_id=odontologo_id,
        refresh_dias=settings.jwt_refresh_dias,
    )
    return access, refresh


def _set_refresh_cookie(response: Response, refresh: str) -> None:
    settings = get_settings()
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/api/auth",
        max_age=settings.jwt_refresh_dias * 86400,
    )


def _buscar_por_email(db: Session, email: str) -> Usuario | None:
    return (
        db.query(Usuario).filter(func.lower(Usuario.email) == email.strip().lower()).first()
    )


def _buscar_por_sub(db: Session, sub: str) -> Usuario | None:
    try:
        uid = UUID(sub)
    except ValueError:
        return None
    return db.query(Usuario).filter(Usuario.id == uid).first()


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> LoginResponse:
    """Emite access + refresh; 401 genérico; 429 sobre 5 intentos/60 s (P12)."""
    ip = request.client.host if request.client is not None else "desconocida"
    if not get_rate_limiter().check_and_count(login_key(ip, body.email)):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "demasiados intentos, probá en un minuto"
        )
    user = _buscar_por_email(db, body.email)
    if user is None:
        dummy_verify()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, CREDENCIALES_INVALIDAS)
    if not user.is_active or not user.activo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, CREDENCIALES_INVALIDAS)
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, CREDENCIALES_INVALIDAS)
    access, refresh = _token_pair(user)
    _set_refresh_cookie(response, refresh)
    return LoginResponse(access_token=access)


@router.post("/refresh", response_model=LoginResponse)
def refresh(
    request: Request, response: Response, db: Session = Depends(get_db)
) -> LoginResponse:
    """Rotación: invalida el refresh presentado y emite un par nuevo."""
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "se requiere refresh")
    try:
        claims = decode_and_validate(raw, "refresh", dependencies.get_jwt_secret())
    except ExpiredAuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh expirado") from exc
    except AuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    settings = get_settings()
    if not dependencies.get_blacklist().claim(
        str(claims["jti"]), settings.jwt_refresh_dias * 86400
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "refresh ya usado")
    user = _buscar_por_sub(db, str(claims["sub"]))
    if user is None or not user.is_active or not user.activo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, CREDENCIALES_INVALIDAS)
    access, new_refresh = _token_pair(user)
    _set_refresh_cookie(response, new_refresh)
    return LoginResponse(access_token=access)


@router.post("/logout", response_model=OkResponse)
def logout(
    request: Request, response: Response, ident: Identity = Depends(get_current_identity)
) -> OkResponse:
    """Invalida access (blacklist `jti`) y refresh vigente; exige autenticación."""
    settings = get_settings()
    dependencies.get_blacklist().add(ident.jti, settings.jwt_access_min * 60)
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        try:
            claims = decode_and_validate(raw, "refresh", dependencies.get_jwt_secret())
        except AuthError:
            claims = None
        if claims is not None:
            dependencies.get_blacklist().add(
                str(claims["jti"]), settings.jwt_refresh_dias * 86400
            )
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth")
    return OkResponse(ok=True)


@router.get("/me", response_model=MeResponse)
def me(
    ident: Identity = Depends(get_current_identity), db: Session = Depends(get_db)
) -> MeResponse:
    """Identidad del portador (sub, rol, email, odontologo_id?)."""
    user = _buscar_por_sub(db, ident.sub)
    if user is None or not user.is_active or not user.activo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, CREDENCIALES_INVALIDAS)
    return MeResponse(
        sub=ident.sub,
        rol=ident.rol,
        email=user.email,
        odontologo_id=str(user.odontologo_id) if user.odontologo_id is not None else None,
    )
