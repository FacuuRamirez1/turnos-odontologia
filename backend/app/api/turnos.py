"""Trazabilidad staff de un turno C-08 task 7.1 (design D8, spec § trazabilidad).

`GET /api/turnos/{turno_id}/trazabilidad` enlaza turno, pago, devolución y
recibos, y lista los `evento_pago` y `turno_historial` ordenados con actor y
fecha. Mismo scope P8 que la bandeja: odontólogo solo sus turnos (ajeno →
403); recepcionista/admin los de todos. Staff JWT obligatorio (P12); la
respuesta lleva `marca = marca_pago_actual()` (P10/P15).
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.security.dependencies import Identity, require_role
from app.domain.pagos.service import marca_pago_actual
from app.infra.db.models import Comprobante, Devolucion, Turno, TurnoHistorial
from app.infra.db.models.pago import EventoPago, Pago
from app.infra.db.session import get_db

router = APIRouter(prefix="/turnos", tags=["turnos"])

STAFF = require_role("odontologo", "recepcionista", "admin")


class TurnoTrazabilidadOut(BaseModel):
    """Cabecera del turno — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    paciente_id: uuid.UUID
    odontologo_id: uuid.UUID
    inicio: datetime
    fin: datetime
    estado: str
    canal: str
    pago_id: uuid.UUID | None
    reprogramado_de_id: uuid.UUID | None


class PagoTrazabilidadOut(BaseModel):
    """Pago enlazado al turno — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    estado: str
    monto: float
    moneda: str
    proveedor: str


class DevolucionTrazabilidadOut(BaseModel):
    """Devolución enlazada al pago — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    estado: str
    monto: float
    porcentaje: int
    motivo: str | None
    mp_refund_id: str | None
    aprobada_at: datetime | None
    rechazada_at: datetime | None
    ejecutada_at: datetime | None


class ComprobanteTrazabilidadOut(BaseModel):
    """Recibo emitido (pago o devolución) — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    concepto: str
    numero: str
    monto: float
    moneda: str
    emitida_at: datetime | None
    simulado: bool


class EventoPagoTrazabilidadOut(BaseModel):
    """Evento de pago append-only con actor y fecha — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    tipo_evento: str
    actor: str
    fecha: datetime
    payload_json: dict[str, object]


class HistorialTrazabilidadOut(BaseModel):
    """Transición de estado append-only con actor y fecha — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    estado_anterior: str
    estado_nuevo: str
    actor_tipo: str
    actor_id: str
    fecha: datetime
    motivo: str | None


class TrazabilidadOut(BaseModel):
    """Cadena turno → pago → devolución → recibos + eventos (D8, P2)."""

    model_config = ConfigDict(extra="forbid")

    turno: TurnoTrazabilidadOut
    pago: PagoTrazabilidadOut | None
    devolucion: DevolucionTrazabilidadOut | None
    comprobantes: list[ComprobanteTrazabilidadOut]
    eventos_pago: list[EventoPagoTrazabilidadOut]
    historial: list[HistorialTrazabilidadOut]
    marca: str


def _uuid_opcional(valor: object) -> uuid.UUID | None:
    return uuid.UUID(str(valor)) if valor is not None else None


def _turno_out(turno: Turno) -> TurnoTrazabilidadOut:
    return TurnoTrazabilidadOut(
        id=uuid.UUID(str(turno.id)),
        paciente_id=uuid.UUID(str(turno.paciente_id)),
        odontologo_id=uuid.UUID(str(turno.odontologo_id)),
        inicio=turno.inicio,
        fin=turno.fin,
        estado=str(turno.estado),
        canal=str(turno.canal),
        pago_id=_uuid_opcional(turno.pago_id),
        reprogramado_de_id=_uuid_opcional(turno.reprogramado_de_id),
    )


def _pago_out(pago: Pago) -> PagoTrazabilidadOut:
    return PagoTrazabilidadOut(
        id=uuid.UUID(str(pago.id)),
        estado=str(pago.estado),
        monto=float(pago.monto),
        moneda=str(pago.moneda),
        proveedor=str(pago.proveedor),
    )


def _devolucion_out(devolucion: Devolucion) -> DevolucionTrazabilidadOut:
    return DevolucionTrazabilidadOut(
        id=uuid.UUID(str(devolucion.id)),
        estado=str(devolucion.estado),
        monto=float(devolucion.monto),
        porcentaje=int(devolucion.porcentaje),
        motivo=devolucion.motivo,
        mp_refund_id=devolucion.mp_refund_id,
        aprobada_at=devolucion.aprobada_at,
        rechazada_at=devolucion.rechazada_at,
        ejecutada_at=devolucion.ejecutada_at,
    )


def _comprobante_out(comprobante: Comprobante) -> ComprobanteTrazabilidadOut:
    return ComprobanteTrazabilidadOut(
        id=uuid.UUID(str(comprobante.id)),
        concepto=comprobante.concepto,
        numero=comprobante.numero,
        monto=float(comprobante.monto),
        moneda=comprobante.moneda,
        emitida_at=comprobante.emitida_at,
        simulado=bool(comprobante.simulado),
    )


def _evento_out(evento: EventoPago) -> EventoPagoTrazabilidadOut:
    payload = evento.payload_json if isinstance(evento.payload_json, dict) else {}
    return EventoPagoTrazabilidadOut(
        id=uuid.UUID(str(evento.id)),
        tipo_evento=str(evento.tipo_evento),
        actor=str(evento.actor),
        fecha=evento.created_at,
        payload_json=payload,
    )


def _historial_out(fila: TurnoHistorial) -> HistorialTrazabilidadOut:
    return HistorialTrazabilidadOut(
        id=uuid.UUID(str(fila.id)),
        estado_anterior=str(fila.estado_anterior),
        estado_nuevo=str(fila.estado_nuevo),
        actor_tipo=str(fila.actor_tipo),
        actor_id=str(fila.actor_id),
        fecha=fila.fecha,
        motivo=fila.motivo,
    )


@router.get("/{turno_id}/trazabilidad", response_model=TrazabilidadOut)
def trazabilidad_turno(
    turno_id: uuid.UUID,
    ident: Identity = Depends(STAFF),
    db: Session = Depends(get_db),
) -> TrazabilidadOut:
    """Trazabilidad completa bajo scope P8 (ajeno → 403, inexistente → 404)."""
    turno = (
        db.query(Turno)
        .filter(Turno.id == turno_id, Turno.is_active.is_(True))
        .first()
    )
    if turno is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "turno inexistente")
    if ident.rol == "odontologo" and (
        ident.odontologo_id is None
        or str(turno.odontologo_id) != str(ident.odontologo_id)
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "turno de otro profesional"
        )

    pago = (
        db.query(Pago)
        .filter(Pago.turno_id == turno.id, Pago.is_active.is_(True))
        .order_by(Pago.created_at, Pago.id)
        .first()
    )
    devolucion = (
        db.query(Devolucion)
        .filter(
            Devolucion.pago_id == pago.id,
            Devolucion.is_active.is_(True),
        )
        .first()
        if pago is not None
        else None
    )
    comprobantes = (
        db.query(Comprobante)
        .filter(Comprobante.turno_id == turno.id)
        .order_by(Comprobante.emitida_at, Comprobante.id)
        .all()
    )
    eventos = (
        db.query(EventoPago)
        .filter(EventoPago.pago_id == pago.id)
        .order_by(EventoPago.created_at, EventoPago.id)
        .all()
        if pago is not None
        else []
    )
    historial = (
        db.query(TurnoHistorial)
        .filter(TurnoHistorial.turno_id == turno.id)
        .order_by(TurnoHistorial.fecha, TurnoHistorial.id)
        .all()
    )

    return TrazabilidadOut(
        turno=_turno_out(turno),
        pago=_pago_out(pago) if pago is not None else None,
        devolucion=(
            _devolucion_out(devolucion) if devolucion is not None else None
        ),
        comprobantes=[_comprobante_out(c) for c in comprobantes],
        eventos_pago=[_evento_out(e) for e in eventos],
        historial=[_historial_out(h) for h in historial],
        marca=marca_pago_actual(),
    )
