"""Agenda del día staff C-05 (C1, P8, spec § agenda).

- `GET /api/agenda?fecha&odontologo_id`: odontólogo solo la propia
  (query distinto al vínculo → 403); recepcionista/admin cualquiera.
  Lectura vía `BaseRepository` scoped (constructor exige `odontologo_id`,
  fail-closed) + filtro del día en la zona clínica.
- `POST /api/agenda/{id}/atendido|no-show`: `confirmado→atendido/no_show`
  con `require_role()` + scope propio + `transition()` (mismo commit).
- Schemas Pydantic v2 `extra='forbid'` (P2).
"""

import uuid
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.api.reservas import _transicion_http  # noqa: F401 (seam compartido C-05)
from app.core.security.dependencies import Identity, require_role
from app.core.settings import get_settings
from app.domain.disponibilidad.motor import resolver_zona
from app.infra.db.models import Turno
from app.infra.db.repository import BaseRepository
from app.infra.db.session import get_db

router = APIRouter(prefix="/agenda", tags=["agenda"])

STAFF = require_role("odontologo", "recepcionista", "admin")


class TurnoAgendaOut(BaseModel):
    """Fila de agenda — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    paciente_id: uuid.UUID
    odontologo_id: uuid.UUID
    inicio: datetime
    fin: datetime
    estado: str
    canal: str


def _out(fila: Turno) -> TurnoAgendaOut:
    return TurnoAgendaOut(
        id=uuid.UUID(str(fila.id)),
        paciente_id=uuid.UUID(str(fila.paciente_id)),
        odontologo_id=uuid.UUID(str(fila.odontologo_id)),
        inicio=fila.inicio, fin=fila.fin,
        estado=str(fila.estado), canal=str(fila.canal),
    )


def _scope_para(ident: Identity, pedido: uuid.UUID) -> uuid.UUID:
    """`odontologo_id` efectivo: propio si es odontólogo, el pedido si no (P8)."""
    if ident.rol == "odontologo":
        if ident.odontologo_id is None or str(pedido) != str(ident.odontologo_id):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "turno de otro profesional")
        return uuid.UUID(str(ident.odontologo_id))
    return pedido


@router.get("", response_model=list[TurnoAgendaOut])
def agenda_del_dia(
    fecha: date = Query(),
    odontologo_id: uuid.UUID = Query(),
    ident: Identity = Depends(STAFF),
    db: Session = Depends(get_db),
) -> list[TurnoAgendaOut]:
    """Turnos del día del profesional (aislada por scope, C1/RN-AISLAMIENTO)."""
    scope = _scope_para(ident, odontologo_id)
    zona = resolver_zona(get_settings().timezone)
    inicio_dia = datetime(fecha.year, fecha.month, fecha.day, tzinfo=zona)
    fin_dia = inicio_dia + timedelta(days=1)
    repo = BaseRepository(db, Turno, odontologo_id=scope)
    filas = [
        t for t in repo.list()
        if inicio_dia <= (t.inicio if t.inicio.tzinfo else t.inicio.replace(tzinfo=zona)) < fin_dia
    ]
    filas.sort(key=lambda t: t.inicio)
    return [_out(t) for t in filas]


def _mutar(
    db: Session, ident: Identity, turno_id: uuid.UUID, destino: str,
) -> TurnoAgendaOut:
    turno = db.query(Turno).filter(
        Turno.id == turno_id, Turno.is_active.is_(True)).first()
    if turno is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "turno inexistente")
    _scope_para(ident, uuid.UUID(str(turno.odontologo_id)))
    fila = _transicion_http(db, turno, destino, ident.rol, ident.sub, motivo=None)
    return _out(fila)


@router.post("/{turno_id}/atendido", response_model=TurnoAgendaOut)
def marcar_atendido(
    turno_id: uuid.UUID,
    ident: Identity = Depends(STAFF),
    db: Session = Depends(get_db),
) -> TurnoAgendaOut:
    """`confirmado→atendido` staff (actor+fecha en historial)."""
    return _mutar(db, ident, turno_id, "atendido")


@router.post("/{turno_id}/no-show", response_model=TurnoAgendaOut)
def marcar_no_show(
    turno_id: uuid.UUID,
    ident: Identity = Depends(STAFF),
    db: Session = Depends(get_db),
) -> TurnoAgendaOut:
    """`confirmado→no_show` staff (guarda: solo posterior a `fin`, →422 si no)."""
    return _mutar(db, ident, turno_id, "no_show")
