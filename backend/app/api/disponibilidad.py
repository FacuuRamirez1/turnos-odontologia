"""Router staff C-04 — CRUD disponibilidad/bloqueos con RBAC por scope (P8, D-SCOPE).

- `require_role("odontologo","recepcionista","admin")` en cada endpoint.
- Odontólogo: `odontologo_id` forzado del claim; body con otro id → 403.
- Recepcionista/admin: `odontologo_id` explícito validado (query/body);
  ausente → 422, nunca lectura global (P8).
- Schemas Pydantic `extra='forbid'` (P2); `IntegrityError` → 422 sin cambios.
- Lecturas vía `BaseRepository` scopeado (fail-closed); id ajeno → 404.
"""

import uuid
from datetime import date, datetime, time
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security.dependencies import Identity, require_role, scoped_odontologo_id
from app.infra.db.models import Bloqueo, Disponibilidad, Odontologo
from app.infra.db.repository import BaseRepository
from app.infra.db.session import get_db

router = APIRouter(prefix="/staff", tags=["disponibilidad"])
STAFF = require_role("odontologo", "recepcionista", "admin")
U422 = status.HTTP_422_UNPROCESSABLE_ENTITY


def _target_od(ident: Identity, body_od: uuid.UUID | None) -> uuid.UUID:
    if ident.rol == "odontologo":
        propio = scoped_odontologo_id(ident)
        if body_od is not None and body_od != propio:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "no podés operar agenda ajena")
        return propio
    if body_od is None:
        raise HTTPException(U422, "odontologo_id es requerido")
    return body_od


def _repo(session: Session, model: type, od: uuid.UUID) -> BaseRepository[Any]:
    return BaseRepository(session, model, odontologo_id=od)


def _odontologo_activo(session: Session, od: uuid.UUID) -> bool:
    fila = session.query(Odontologo).filter(Odontologo.id == od).first()
    return fila is not None and bool(fila.is_active and fila.activo)


class DisponibilidadCreate(BaseModel):
    """Alta de franja semanal — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

    odontologo_id: uuid.UUID | None = None
    dia_semana: int = Field(ge=0, le=6)
    hora_inicio: time
    hora_fin: time
    duracion_min: int = Field(gt=0)
    tope_dia: int = Field(gt=0)
    vigente_desde: date | None = None
    vigente_hasta: date | None = None

    @model_validator(mode="after")
    def _orden(self) -> "DisponibilidadCreate":
        if self.hora_fin <= self.hora_inicio:
            raise ValueError("hora_fin debe ser posterior a hora_inicio")
        if (
            self.vigente_desde is not None
            and self.vigente_hasta is not None
            and self.vigente_desde > self.vigente_hasta
        ):
            raise ValueError("vigente_desde no puede ser posterior a vigente_hasta")
        return self


class DisponibilidadOut(BaseModel):
    """Fila persistida — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    odontologo_id: uuid.UUID
    dia_semana: int
    hora_inicio: time
    hora_fin: time
    duracion_min: int
    tope_dia: int
    vigente_desde: date | None = None
    vigente_hasta: date | None = None


class DisponibilidadUpdate(BaseModel):
    """Edición parcial (sin cambio de profesional) — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

    dia_semana: int | None = Field(default=None, ge=0, le=6)
    hora_inicio: time | None = None
    hora_fin: time | None = None
    duracion_min: int | None = Field(default=None, gt=0)
    tope_dia: int | None = Field(default=None, gt=0)
    vigente_desde: date | None = None
    vigente_hasta: date | None = None


class BloqueoCreate(BaseModel):
    """Alta de bloqueo — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

    odontologo_id: uuid.UUID | None = None
    desde: datetime
    hasta: datetime
    motivo: Literal["pausa", "feriado", "bloqueo", "vacaciones"]

    @model_validator(mode="after")
    def _orden(self) -> "BloqueoCreate":
        if self.hasta <= self.desde:
            raise ValueError("hasta debe ser posterior a desde")
        return self


class BloqueoOut(BaseModel):
    """Bloqueo persistido — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    odontologo_id: uuid.UUID
    desde: datetime
    hasta: datetime
    motivo: str


def _out_dispo(f: Disponibilidad) -> DisponibilidadOut:
    return DisponibilidadOut(
        id=uuid.UUID(str(f.id)),
        odontologo_id=uuid.UUID(str(f.odontologo_id)),
        dia_semana=f.dia_semana,
        hora_inicio=f.hora_inicio,
        hora_fin=f.hora_fin,
        duracion_min=f.duracion_min,
        tope_dia=f.tope_dia,
        vigente_desde=f.vigente_desde,
        vigente_hasta=f.vigente_hasta,
    )


def _out_bloqueo(f: Bloqueo) -> BloqueoOut:
    return BloqueoOut(
        id=uuid.UUID(str(f.id)),
        odontologo_id=uuid.UUID(str(f.odontologo_id)),
        desde=f.desde,
        hasta=f.hasta,
        motivo=f.motivo,
    )


@router.post("/disponibilidad", response_model=DisponibilidadOut, status_code=201)
def crear_disponibilidad(
    body: DisponibilidadCreate,
    ident: Identity = Depends(STAFF),
    db: Session = Depends(get_db),
) -> DisponibilidadOut:
    """Crea franja propia (odontólogo) o de cualquier profesional (recepción)."""
    od = _target_od(ident, body.odontologo_id)
    if not _odontologo_activo(db, od):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "odontólogo desconocido")
    fila = Disponibilidad(
        odontologo_id=od,
        dia_semana=body.dia_semana,
        hora_inicio=body.hora_inicio,
        hora_fin=body.hora_fin,
        duracion_min=body.duracion_min,
        tope_dia=body.tope_dia,
        vigente_desde=body.vigente_desde,
        vigente_hasta=body.vigente_hasta,
    )
    db.add(fila)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(U422, "franja inválida o solapada") from exc
    db.refresh(fila)
    return _out_dispo(fila)


@router.get("/disponibilidad", response_model=list[DisponibilidadOut])
def listar_disponibilidad(
    odontologo_id: uuid.UUID | None = Query(default=None),
    ident: Identity = Depends(STAFF),
    db: Session = Depends(get_db),
) -> list[DisponibilidadOut]:
    """Lista scopeada: odontólogo solo lo propio; recepción pasa id explícito."""
    od = _target_od(ident, odontologo_id)
    return [_out_dispo(f) for f in _repo(db, Disponibilidad, od).list()]


@router.get("/disponibilidad/{fila_id}", response_model=DisponibilidadOut)
def ver_disponibilidad(
    fila_id: uuid.UUID,
    ident: Identity = Depends(STAFF),
    db: Session = Depends(get_db),
) -> DisponibilidadOut:
    """Detalle scopeado: id ajeno → 404 (nunca fuga, P8)."""
    if ident.rol == "odontologo":
        od = _target_od(ident, None)
    else:
        od = _target_od(ident, _repo_scope_body(db, ident, fila_id))
    fila = _repo(db, Disponibilidad, od).get(fila_id)
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "disponibilidad inexistente")
    return _out_dispo(fila)


def _repo_scope_body(db: Session, ident: Identity, fila_id: uuid.UUID) -> uuid.UUID | None:
    """Recepción: resuelve el scope desde la fila (sin filtro global previo)."""
    _ = ident
    fila = db.query(Disponibilidad).filter(Disponibilidad.id == fila_id).first()
    if fila is None:
        return uuid.uuid4()  # scope válido pero inexistente → 404 abajo
    return uuid.UUID(str(fila.odontologo_id))


@router.put("/disponibilidad/{fila_id}", response_model=DisponibilidadOut)
def editar_disponibilidad(
    fila_id: uuid.UUID,
    body: DisponibilidadUpdate,
    ident: Identity = Depends(STAFF),
    db: Session = Depends(get_db),
) -> DisponibilidadOut:
    """Edita franja scopeada (sin cambio de profesional)."""
    if ident.rol == "odontologo":
        od = scoped_odontologo_id(ident)
    else:
        resuelto = _repo_scope_body(db, ident, fila_id)
        if resuelto is None:
            raise HTTPException(U422, "odontologo_id es requerido")
        od = resuelto
    repo: BaseRepository[Disponibilidad] = _repo(db, Disponibilidad, od)
    fila = repo.get(fila_id)
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "disponibilidad inexistente")
    datos = body.model_dump(exclude_unset=True)
    for campo, valor in datos.items():
        setattr(fila, campo, valor)
    if fila.hora_fin <= fila.hora_inicio:
        raise HTTPException(U422, "hora_fin debe ser posterior")
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(U422, "franja inválida o solapada") from exc
    db.refresh(fila)
    return _out_dispo(fila)


@router.delete("/disponibilidad/{fila_id}", status_code=204)
def borrar_disponibilidad(
    fila_id: uuid.UUID,
    ident: Identity = Depends(STAFF),
    db: Session = Depends(get_db),
) -> None:
    """Borrado lógico scopeado (conserva la fila, P9)."""
    if ident.rol == "odontologo":
        od = scoped_odontologo_id(ident)
    else:
        resuelto = _repo_scope_body(db, ident, fila_id)
        if resuelto is None:
            raise HTTPException(U422, "odontologo_id es requerido")
        od = resuelto
    repo: BaseRepository[Disponibilidad] = _repo(db, Disponibilidad, od)
    fila = repo.get(fila_id)
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "disponibilidad inexistente")
    fila.soft_delete()
    db.commit()
    return None


@router.post("/bloqueos", response_model=BloqueoOut, status_code=201)
def crear_bloqueo(
    body: BloqueoCreate,
    ident: Identity = Depends(STAFF),
    db: Session = Depends(get_db),
) -> BloqueoOut:
    """Carga pausa/feriado/bloqueo/vacaciones con el mismo scope que disponibilidad."""
    od = _target_od(ident, body.odontologo_id)
    if not _odontologo_activo(db, od):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "odontólogo desconocido")
    fila = Bloqueo(odontologo_id=od, desde=body.desde, hasta=body.hasta, motivo=body.motivo)
    db.add(fila)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "bloqueo inválido") from exc
    db.refresh(fila)
    return _out_bloqueo(fila)


@router.get("/bloqueos", response_model=list[BloqueoOut])
def listar_bloqueos(
    odontologo_id: uuid.UUID | None = Query(default=None),
    ident: Identity = Depends(STAFF),
    db: Session = Depends(get_db),
) -> list[BloqueoOut]:
    """Lista scopeada de bloqueos (misma regla D-SCOPE)."""
    od = _target_od(ident, odontologo_id)
    return [_out_bloqueo(f) for f in _repo(db, Bloqueo, od).list()]


@router.delete("/bloqueos/{fila_id}", status_code=204)
def borrar_bloqueo(
    fila_id: uuid.UUID,
    ident: Identity = Depends(STAFF),
    db: Session = Depends(get_db),
) -> None:
    """Elimina bloqueo scopeado (borrado lógico)."""
    if ident.rol == "odontologo":
        od = scoped_odontologo_id(ident)
    else:
        fila_prev = db.query(Bloqueo).filter(Bloqueo.id == fila_id).first()
        if fila_prev is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "bloqueo inexistente")
        od = uuid.UUID(str(fila_prev.odontologo_id))
    repo: BaseRepository[Bloqueo] = _repo(db, Bloqueo, od)
    fila = repo.get(fila_id)
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "bloqueo inexistente")
    fila.soft_delete()
    db.commit()
    return None
