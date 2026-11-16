"""Modelo C-08 `Comprobante` — recibo interno inmutable (D6, P9).

Sin `AuditMixin` (sin soft-delete): `GRANT SELECT, INSERT` y
`REVOKE UPDATE, DELETE` al rol app en la migración 006. `simulado` se fija al
emitir (`pago.proveedor == 'simulado'`) y no se recalcula (P15). El PDF se
regenera on-demand desde `payload_json` (snapshot), sin blobs.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base

TIPOS_COMPROBANTE = ("recibo_interno", "factura_arca")
CONCEPTOS_COMPROBANTE = ("pago", "devolucion")


_ULTIMO_LOCAL: list[int] = [0]


def _numero_siguiente(context: Any) -> str:
    """`RI-000001` correlativo: `nextval` en PostgreSQL; max+1 en SQLite (tests)."""
    conn = context.connection
    if conn.dialect.name == "postgresql":
        n = conn.execute(text("SELECT nextval('comprobante_numero_seq')")).scalar_one()
    else:
        # SQLite (solo tests): los defaults de un insertmany se evalúan antes de
        # insertar, por eso el contador local evita repetir el max de la tabla.
        en_db = conn.execute(
            text("SELECT COALESCE(MAX(CAST(SUBSTR(numero, 4) AS INTEGER)), 0) + 1 FROM comprobante")
        ).scalar_one()
        n = max(int(en_db), _ULTIMO_LOCAL[0] + 1)
        _ULTIMO_LOCAL[0] = n
    return f"RI-{int(n):06d}"


class Comprobante(Base):
    """Recibo de pago o de devolución; fila inmutable."""

    __tablename__ = "comprobante"

    id: Mapped[uuid.UUID] = mapped_column(SAUuid, primary_key=True, default=uuid.uuid4)
    pago_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid, ForeignKey("pago.id", ondelete="RESTRICT"), nullable=False
    )
    devolucion_id: Mapped[uuid.UUID | None] = mapped_column(
        SAUuid, ForeignKey("devolucion.id", ondelete="RESTRICT"), nullable=True, default=None
    )
    turno_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid, ForeignKey("turno.id", ondelete="RESTRICT"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(String(20), nullable=False, default="recibo_interno")
    concepto: Mapped[str] = mapped_column(String(20), nullable=False)
    numero: Mapped[str] = mapped_column(String(20), nullable=False, default=_numero_siguiente)
    monto: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    moneda: Mapped[str] = mapped_column(String(3), nullable=False, default="ARS")
    cae: Mapped[str | None] = mapped_column(String(20), nullable=True, default=None)
    emitida_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    simulado: Mapped[bool] = mapped_column(Boolean, nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)

    __table_args__ = (
        CheckConstraint(
            "tipo IN ('recibo_interno', 'factura_arca')", name="ck_comprobante_tipo_cerrado"
        ),
        CheckConstraint(
            "concepto IN ('pago', 'devolucion')", name="ck_comprobante_concepto_cerrado"
        ),
        CheckConstraint(
            "(concepto = 'devolucion') = (devolucion_id IS NOT NULL)",
            name="ck_comprobante_concepto_devolucion_id",
        ),
        CheckConstraint("monto >= 0", name="ck_comprobante_monto_no_negativo"),
        UniqueConstraint("numero", name="uq_comprobante_numero"),
        Index(
            "uq_comprobante_pago_concepto_pago",
            "pago_id",
            unique=True,
            postgresql_where=text("concepto = 'pago'"),
            sqlite_where=text("concepto = 'pago'"),
        ),
        Index(
            "uq_comprobante_devolucion",
            "devolucion_id",
            unique=True,
            postgresql_where=text("devolucion_id IS NOT NULL"),
            sqlite_where=text("devolucion_id IS NOT NULL"),
        ),
        Index("ix_comprobante_pago_id", "pago_id"),
        Index("ix_comprobante_turno_id", "turno_id"),
    )
