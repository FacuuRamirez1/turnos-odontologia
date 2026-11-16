"""Modelos C-07 pagos — Pago (actualizable) + EventoPago (append-only, P9).

- `Pago`: entidad separada del turno (D13) con `turno_id` (FK a turno, columna
  solo de un lado: rompe la referencia circular), `odontologo_id`, `monto`,
  `moneda`, `proveedor`, `mp_payment_id` único, `mp_preference_id` nullable,
  `estado`, `idempotency_key` único (P4). Usa `AuditMixin` (estado cambia
  pendiente→aprobado/rechazado).
- `EventoPago`: append-only, sin `AuditMixin` (sin is_active/soft-delete),
  sin UPDATE/DELETE del rol app (REVOKE en migración 005, P9).
"""

import uuid
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base
from app.infra.db.mixins import AuditMixin

ESTADOS_PAGO = (
    "pendiente",
    "aprobado",
    "rechazado",
    "reembolsado_parcial",
    "reembolsado_total",
)

PROVEEDORES = ("simulado", "mercadopago")

TIPOS_EVENTO_PAGO = (
    "creado",
    "webhook_recibido",
    "aprobado",
    "rechazado",
    "devolucion_solicitada",
    "devolucion_aprobada",
    "devolucion_rechazada",
    "devolucion_ejecutada",
    "conciliado",
)


class Pago(AuditMixin, Base):
    """Pago de seña, separado del Turno (D13)."""

    __tablename__ = "pago"

    turno_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid,
        ForeignKey("turno.id", ondelete="RESTRICT"),
        nullable=False,
    )
    odontologo_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid,
        ForeignKey("odontologo.id", ondelete="RESTRICT"),
        nullable=False,
    )
    monto: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    moneda: Mapped[str] = mapped_column(String(3), nullable=False, default="ARS")
    proveedor: Mapped[str] = mapped_column(
        String(20), nullable=False, default="simulado"
    )
    mp_payment_id: Mapped[str] = mapped_column(String(100), nullable=False)
    mp_preference_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, default=None
    )
    estado: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pendiente"
    )
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "estado IN ('pendiente', 'aprobado', 'rechazado', "
            "'reembolsado_parcial', 'reembolsado_total')",
            name="ck_pago_estado_cerrado",
        ),
        CheckConstraint(
            "proveedor IN ('simulado', 'mercadopago')",
            name="ck_pago_proveedor_cerrado",
        ),
        CheckConstraint("monto >= 0", name="ck_pago_monto_no_negativo"),
        UniqueConstraint("mp_payment_id", name="uq_pago_mp_payment_id"),
        UniqueConstraint("idempotency_key", name="uq_pago_idempotency_key"),
    )


class EventoPago(Base):
    """Evento de pago append-only (sin AuditMixin: sin soft-delete, P9)."""

    __tablename__ = "evento_pago"

    id: Mapped[uuid.UUID] = mapped_column(
        SAUuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    pago_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid,
        ForeignKey("pago.id", ondelete="RESTRICT"),
        nullable=False,
    )
    tipo_evento: Mapped[str] = mapped_column(String(30), nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "actor IN ('paciente', 'odontologo', 'recepcionista', 'admin', 'sistema')",
            name="ck_evento_pago_actor_cerrado",
        ),
        CheckConstraint(
            "tipo_evento IN ('creado', 'webhook_recibido', 'aprobado', 'rechazado', "
            "'devolucion_solicitada', 'devolucion_aprobada', 'devolucion_rechazada', "
            "'devolucion_ejecutada', 'conciliado')",
            name="ck_evento_pago_tipo_cerrado",
        ),
    )
