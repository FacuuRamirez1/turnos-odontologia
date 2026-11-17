"""Consultas de reportes C-12 (solo lectura, sin escrituras en append-only).

El `odontologo_id` llega YA resuelto por el router (P8): para un odontólogo es
el de su identidad, para recepción/admin el filtro opcional. Períodos
inclusivos en UTC (`desde <= fecha <= hasta`).

Cortes de fecha: turnos por `inicio`; pagos por `created_at` del pago;
devoluciones por `ejecutada_at` (momento de la ejecución); auditoría por
`fecha` / `created_at` del evento.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import cast

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.infra.db.models import Devolucion, Pago, Turno, TurnoHistorial
from app.infra.db.models.pago import EventoPago

ESTADOS_TURNO = (
    "creado",
    "confirmado",
    "cancelado",
    "reprogramado",
    "atendido",
    "no_show",
    "devuelto",
)
MAX_DIAS_PERIODO = 366


class PeriodoInvalido(ValueError):
    """`desde > hasta` o rango mayor al máximo permitido."""


def validar_periodo(desde: datetime, hasta: datetime) -> None:
    if desde > hasta:
        raise PeriodoInvalido("desde debe ser anterior o igual a hasta")
    if (hasta - desde).days > MAX_DIAS_PERIODO:
        raise PeriodoInvalido(f"el período no puede superar {MAX_DIAS_PERIODO} días")


@dataclass(frozen=True)
class FilaCaja:
    concepto: str  # "pago" | "devolucion"
    fecha: datetime
    monto: Decimal
    turno_id: uuid.UUID
    pago_id: uuid.UUID
    devolucion_id: uuid.UUID | None
    odontologo_id: uuid.UUID


@dataclass
class ResumenCaja:
    total_aprobado: Decimal = Decimal("0")
    total_devuelto: Decimal = Decimal("0")
    filas: list[FilaCaja] = field(default_factory=list)

    @property
    def neto(self) -> Decimal:
        return self.total_aprobado - self.total_devuelto


@dataclass(frozen=True)
class FilaAuditoria:
    origen: str  # "turno_historial" | "evento_pago"
    fecha: datetime
    referencia_id: uuid.UUID
    actor: str
    detalle: str


def _turnos_query(
    desde: datetime, hasta: datetime, odontologo_id: uuid.UUID | None
) -> Select[tuple[Turno]]:
    consulta = select(Turno).where(
        Turno.inicio >= desde, Turno.inicio <= hasta, Turno.is_active.is_(True)
    )
    if odontologo_id is not None:
        consulta = consulta.where(Turno.odontologo_id == odontologo_id)
    return consulta


def listar_turnos(
    session: Session,
    desde: datetime,
    hasta: datetime,
    odontologo_id: uuid.UUID | None = None,
) -> list[Turno]:
    validar_periodo(desde, hasta)
    consulta = _turnos_query(desde, hasta, odontologo_id).order_by(Turno.inicio)
    return list(session.scalars(consulta))


def conteo_por_estado(
    session: Session,
    desde: datetime,
    hasta: datetime,
    odontologo_id: uuid.UUID | None = None,
) -> dict[str, int]:
    """Conteo de turnos por estado cerrado (7 claves, ceros por defecto)."""
    resultado = {estado: 0 for estado in ESTADOS_TURNO}
    for turno in listar_turnos(session, desde, hasta, odontologo_id):
        if turno.estado in resultado:
            resultado[turno.estado] += 1
    return resultado


def resumen_caja(
    session: Session,
    desde: datetime,
    hasta: datetime,
    odontologo_id: uuid.UUID | None = None,
) -> ResumenCaja:
    """Pagos `aprobado` y devoluciones `ejecutada`; el total es la suma del detalle."""
    validar_periodo(desde, hasta)
    resumen = ResumenCaja()

    pagos = select(Pago).where(
        Pago.estado.in_(("aprobado", "reembolsado_parcial", "reembolsado_total")),
        Pago.created_at >= desde,
        Pago.created_at <= hasta,
    )
    if odontologo_id is not None:
        pagos = pagos.where(Pago.odontologo_id == odontologo_id)
    for pago in session.scalars(pagos.order_by(Pago.created_at)):
        resumen.total_aprobado += pago.monto
        resumen.filas.append(
            FilaCaja("pago", pago.created_at, pago.monto, pago.turno_id,
                     pago.id, None, pago.odontologo_id)
        )

    devoluciones = (
        select(Devolucion, Pago.odontologo_id)
        .join(Pago, Pago.id == Devolucion.pago_id)
        .where(
            Devolucion.estado == "ejecutada",
            Devolucion.ejecutada_at >= desde,
            Devolucion.ejecutada_at <= hasta,
        )
    )
    if odontologo_id is not None:
        devoluciones = devoluciones.where(Pago.odontologo_id == odontologo_id)
    for dev, od_id in session.execute(devoluciones.order_by(Devolucion.ejecutada_at)):
        resumen.total_devuelto += dev.monto
        resumen.filas.append(
            FilaCaja("devolucion", dev.ejecutada_at or desde, dev.monto, dev.turno_id,
                     dev.pago_id, dev.id, od_id)
        )
    return resumen


def filas_auditoria(
    session: Session,
    desde: datetime,
    hasta: datetime,
    odontologo_id: uuid.UUID | None = None,
) -> list[FilaAuditoria]:
    """Unión de `turno_historial` y `evento_pago` (sin payload crudo)."""
    validar_periodo(desde, hasta)
    filas: list[FilaAuditoria] = []

    historial = (
        select(TurnoHistorial, Turno.odontologo_id)
        .join(Turno, Turno.id == TurnoHistorial.turno_id)
        .where(TurnoHistorial.fecha >= desde, TurnoHistorial.fecha <= hasta)
    )
    if odontologo_id is not None:
        historial = historial.where(Turno.odontologo_id == odontologo_id)
    for h, _od in session.execute(historial):
        filas.append(
            FilaAuditoria(
                "turno_historial", h.fecha, h.turno_id,
                f"{h.actor_tipo}:{h.actor_id}",
                f"{h.estado_anterior}->{h.estado_nuevo}",
            )
        )

    eventos = (
        select(EventoPago)
        .join(Pago, Pago.id == EventoPago.pago_id)
        .where(EventoPago.created_at >= desde, EventoPago.created_at <= hasta)
    )
    if odontologo_id is not None:
        eventos = eventos.where(Pago.odontologo_id == odontologo_id)
    for ev in session.scalars(eventos):
        filas.append(
            FilaAuditoria("evento_pago", cast(datetime, ev.created_at), ev.pago_id,
                          ev.actor, ev.tipo_evento)
        )
    return sorted(filas, key=lambda f: f.fecha)
