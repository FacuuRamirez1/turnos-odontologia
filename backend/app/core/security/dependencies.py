"""Guard RBAC C-03 (design D8, P8) — `require_role(*roles)` + identidad validada.

Matriz exigible en backend (KB `03 §2`; referencia de diseño — C-04+ declara
los roles de cada endpoint con este mismo guard):
  Recepcionista SÍ (6): ver agendas · cargar/editar disponibilidad · gestionar
  cancelaciones y reprogramaciones · bandeja de devoluciones · reportes y
  exportaciones CSV/PDF · fichas mínimas de pacientes.
  Recepcionista NO (4): administrar usuarios/roles · configuración de pagos
  (credenciales MP, webhooks) · borrar audit trail · comprobantes ARCA (v2).
La UI nunca es confiable: cada endpoint staff declara sus roles acá y el
`odontologo_id` viaja en claims, forzado en repositorio (P8, RN-AISLAMIENTO).
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TypeVar
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security.jwt import AuthError, decode_and_validate
from app.core.settings import get_settings
from app.infra.db.repository import BaseRepository, es_scopeada
from app.infra.redis.blacklist import TokenBlacklist, build_blacklist

T = TypeVar("T")

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Identity:
    """Identidad validada del portador: `sub/rol/odontologo_id?/jti`."""

    sub: str
    rol: str
    odontologo_id: str | None
    jti: str

    @property
    def odontologo_vinculado(self) -> bool:
        """Odontólogo con perfil: único que autoriza scope propio."""
        return self.rol == "odontologo" and self.odontologo_id is not None


_secret_override: str | None = None
_blacklist_override: TokenBlacklist | None = None


def configure_security(secret: str, blacklist: TokenBlacklist) -> None:
    """Fija secreto + blacklist (tests y arranque explícito; sino lazy de env)."""
    global _secret_override, _blacklist_override
    _secret_override = secret
    _blacklist_override = blacklist


def get_jwt_secret() -> str:
    """Secreto activo (override de tests o `JWT_SECRET` de env, P5)."""
    if _secret_override is not None:
        return _secret_override
    return get_settings().jwt_secret


def get_blacklist() -> TokenBlacklist:
    """Blacklist activa (override de tests o Redis/env lazy)."""
    global _blacklist_override
    if _blacklist_override is None:
        _blacklist_override = build_blacklist(get_settings().redis_url)
    return _blacklist_override


async def get_current_identity(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Identity:
    """Identidad del Bearer access vigente: 401 sin token, inválido o revocado."""
    _ = request
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "se requiere autenticación")
    try:
        claims = decode_and_validate(credentials.credentials, "access", get_jwt_secret())
    except AuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    jti = str(claims["jti"])
    if get_blacklist().is_listed(jti):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token revocado")
    odontologo_id = claims.get("odontologo_id")
    return Identity(
        sub=str(claims["sub"]),
        rol=str(claims["rol"]),
        odontologo_id=str(odontologo_id) if odontologo_id is not None else None,
        jti=jti,
    )


def require_role(*roles: str) -> Callable[[Identity], Awaitable[Identity]]:
    """Dependencia FastAPI: 401 sin identidad, 403 con rol no permitido (P8)."""

    async def guard(ident: Identity = Depends(get_current_identity)) -> Identity:
        if ident.rol not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "rol no autorizado")
        if ident.rol == "odontologo" and ident.odontologo_id is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "odontólogo sin perfil vinculado"
            )
        return ident

    return guard


def scoped_odontologo_id(ident: Identity) -> UUID:
    """`odontologo_id` de la identidad para repositorios; falla cerrado (P8)."""
    if ident.odontologo_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "sin scope de odontólogo")
    return UUID(ident.odontologo_id)


def scoped_repository(session: Session, model: type[T], ident: Identity) -> BaseRepository[T]:
    """Cablea identidad → repositorio: scope forzado por constructor (RN-AISLAMIENTO).

    Entidades scopeadas exigen el `odontologo_id` de la identidad (403 sin
    vínculo, nunca datos sin filtrar); no-scopeadas (`Paciente` en v1) leen
    global. C-04+ la usa en cada endpoint staff (P8).
    """
    if es_scopeada(model):
        return BaseRepository(session, model, odontologo_id=scoped_odontologo_id(ident))
    return BaseRepository(session, model)
