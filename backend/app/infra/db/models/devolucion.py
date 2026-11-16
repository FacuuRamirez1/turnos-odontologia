"""Modelo C-08 `Devolucion` — una por pago, ciclo cerrado de estados (D3).

Doble barrera (P6): CHECK/UNIQUE aquí y en la migración 006 + triggers de
PostgreSQL (transición de estado y `monto <= pago.monto`) que solo existen en
la migración. La cotización 0 % NO crea fila (CHECK `porcentaje IN (100, 60)`,
`monto > 0`). El rastro inmutable vive en `evento_pago` (append-only, P9).
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base
from app.infra.db.mixins import AuditMixin

ESTADOS_DEVOLUCION = ("pendiente", "aprobada", "rechazada", "ejecutada")
PORCENTAJES_DEVOLUCION = (100, 60)


def _usuario_fk() -> Mapped[uuid.UUID | None]:
    return mapped_column(
        SAUuid, ForeignKey("usuario.id", ondelete="RESTRICT"), nullable=True, default=None
    )


def _fecha_opcional() -> Mapped[datetime | None]:
    return mapped_column(DateTime(timezone=True), nullable=True, default=None)


class Devolucion(AuditMixin, Base):
    """Devolución de seña de un pago aprobado (cancelación confirmado→cancelado)."""

    __tablename__ = "devolucion"

    pago_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid, ForeignKey("pago.id", ondelete="RESTRICT"), nullable=False
    )
    turno_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid, ForeignKey("turno.id", ondelete="RESTRICT"), nullable=False
    )
    monto: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    porcentaje: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="pendiente")
    idempotency_key: Mapped[str] = mapped_column(String(80), nullable=False)
    mp_refund_id: Mapped[str | None] = mapped_column(String(100), nullable=True, default=None)
    aprobada_por: Mapped[uuid.UUID | None] = _usuario_fk()
    aprobada_at: Mapped[datetime | None] = _fecha_opcional()
    rechazada_por: Mapped[uuid.UUID | None] = _usuario_fk()
    rechazada_at: Mapped[datetime | None] = _fecha_opcional()
    motivo_rechazo: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    ejecutada_por: Mapped[uuid.UUID | None] = _usuario_fk()
    ejecutada_at: Mapped[datetime | None] = _fecha_opcional()

    __table_args__ = (
        CheckConstraint("porcentaje IN (100, 60)", name="ck_devolucion_porcentaje_cerrado"),
        CheckConstraint("monto > 0", name="ck_devolucion_monto_positivo"),
        CheckConstraint(
            "estado IN ('pendiente', 'aprobada', 'rechazada', 'ejecutada')",
            name="ck_devolucion_estado_cerrado",
        ),
        CheckConstraint(
            "estado <> 'ejecutada' OR mp_refund_id IS NOT NULL",
            name="ck_devolucion_ejecutada_con_refund",
        ),
        CheckConstraint(
            "estado NOT IN ('aprobada', 'ejecutada') "
            "OR (aprobada_por IS NOT NULL AND aprobada_at IS NOT NULL)",
            name="ck_devolucion_aprobada_con_actor",
        ),
        CheckConstraint(
            "estado <> 'rechazada' OR (rechazada_por IS NOT NULL "
            "AND rechazada_at IS NOT NULL AND motivo_rechazo IS NOT NULL)",
            name="ck_devolucion_rechazada_con_actor",
        ),
        CheckConstraint(
            "estado <> 'ejecutada' OR (ejecutada_por IS NOT NULL AND ejecutada_at IS NOT NULL)",
            name="ck_devolucion_ejecutada_con_actor",
        ),
        UniqueConstraint("pago_id", name="uq_devolucion_pago"),
        UniqueConstraint("idempotency_key", name="uq_devolucion_idempotency_key"),
        UniqueConstraint("mp_refund_id", name="uq_devolucion_mp_refund_id"),
        Index("ix_devolucion_turno_id", "turno_id"),
        Index("ix_devolucion_estado", "estado", postgresql_where=text("is_active")),
    )
