"""Self-service C-05 — GET /api/mis-turnos (03 §3.5, P12, spec § mis-turnos).

Solo mail-action JWT propio (C-03, 1 uso, vida corta): `sub` = DNI del
paciente. DNI solo → 401 sin exponer nada; token ajeno → 403. El token se
consume al responder (single-use, P12).
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.pacientes import get_paciente_action_store
from app.core.security.dependencies import get_jwt_secret
from app.core.security.jwt import AuthError, decode_and_validate
from app.core.settings import get_settings
from app.domain.pacientes.service import normalizar_dni, validar_formato_dni
from app.infra.db.models import Paciente, Turno
from app.infra.db.session import get_db
from app.infra.redis.rate_limit import LoginRateLimiter, build_rate_limiter

router = APIRouter(tags=["mis-turnos"])

MIS_TURNOS_PREFIX = "mis_turnos:ratelimit:"
MIS_TURNOS_LIMIT = 30
MIS_TURNOS_WINDOW = 60
_mis_turnos_limiter: LoginRateLimiter | None = None


def get_mis_turnos_limiter() -> LoginRateLimiter:
    global _mis_turnos_limiter
    if _mis_turnos_limiter is None:
        _mis_turnos_limiter = build_rate_limiter(
            get_settings().redis_url,
            limit=MIS_TURNOS_LIMIT,
            window_seconds=MIS_TURNOS_WINDOW,
        )
    return _mis_turnos_limiter


def reset_mis_turnos_limiter(
    limit: int = MIS_TURNOS_LIMIT, window_seconds: int = MIS_TURNOS_WINDOW,
) -> None:
    global _mis_turnos_limiter
    _mis_turnos_limiter = LoginRateLimiter(
        client=None, limit=limit, window_seconds=window_seconds
    )


class MisTurnoOut(BaseModel):
    """Turno propio acotado — P2 `extra='forbid'`, sin datos de terceros."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    odontologo_id: uuid.UUID
    inicio: datetime
    fin: datetime
    estado: str


@router.get("/mis-turnos", response_model=list[MisTurnoOut])
def mis_turnos(
    request: Request,
    dni: str = Query(min_length=1, max_length=20),
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[MisTurnoOut]:
    """Turnos del paciente del token (nunca DNI solo, P12)."""
    ip = request.client.host if request.client is not None else "desconocida"
    if not get_mis_turnos_limiter().check_and_count(f"{MIS_TURNOS_PREFIX}{ip}"):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "demasiadas consultas mis-turnos"
        )
    _ = request
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "se requiere token")
    try:
        claims = decode_and_validate(token, "action", get_jwt_secret())
    except AuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    try:
        normalizado = normalizar_dni(dni)
        validar_formato_dni(normalizado)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    if str(claims.get("sub")) != normalizado:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "token no autoriza esta consulta")
    paciente = (
        db.query(Paciente)
        .filter(Paciente.dni == normalizado, Paciente.is_active.is_(True))
        .first()
    )
    if paciente is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "paciente inexistente")
    filas = (
        db.query(Turno)
        .filter(Turno.paciente_id == paciente.id, Turno.is_active.is_(True))
        .order_by(Turno.inicio.asc())
        .all()
    )
    get_paciente_action_store().consume(token, get_settings().jwt_action_min * 60)
    return [
        MisTurnoOut(id=uuid.UUID(str(f.id)), odontologo_id=uuid.UUID(str(f.odontologo_id)),
                    inicio=f.inicio, fin=f.fin, estado=str(f.estado))
        for f in filas
    ]
