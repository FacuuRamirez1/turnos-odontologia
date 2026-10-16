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

router = APIRouter(tags=["mis-turnos"])


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
