"""`Bloqueo` C-04 — pausas/feriados/bloqueos por profesional (spec § bloqueos).

- `odontologo_id` NOT NULL (D-BLOQ): feriados = N filas, nunca fila global —
  preserva el fail-closed de `BaseRepository` (P8).
- `desde/hasta`: timestamptz con CHECK `hasta > desde` (P6).
- `motivo`: CHECK cerrado `pausa|feriado|bloqueo|vacaciones` (P6).
- `created_by`: UUID del actor staff (nullable en seed/tests).
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base
from app.infra.db.mixins import AuditMixin

MOTIVOS_VALIDOS = ("pausa", "feriado", "bloqueo", "vacaciones")


class Bloqueo(AuditMixin, Base):
    __tablename__ = "bloqueo"

    odontologo_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid,
        ForeignKey("odontologo.id", ondelete="RESTRICT"),
        nullable=False,
    )
    desde: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    hasta: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    motivo: Mapped[str] = mapped_column(String(20), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(SAUuid, nullable=True, default=None)

    __table_args__ = (
        CheckConstraint("hasta > desde", name="ck_bloqueo_rango_orden"),
        CheckConstraint(
            "motivo IN ('pausa', 'feriado', 'bloqueo', 'vacaciones')",
            name="ck_bloqueo_motivo_cerrado",
        ),
    )


Index(
    "ix_bloqueo_od_desde",
    Bloqueo.odontologo_id,
    Bloqueo.desde,
    postgresql_where=text("is_active"),
)
