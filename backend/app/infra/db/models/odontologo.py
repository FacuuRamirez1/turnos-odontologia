"""`Odontologo` C-02 — perfil profesional con montos propios (spec § odontologo profile).

- `user_id`: FK única → `usuario.id` con `ON DELETE RESTRICT` explícito (P6):
  un staff con perfil no se borra en cascada por accidente.
- `monto_turno` / `monto_senia`: `NUMERIC(10,2)` no negativos (CHECK).
"""

import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, text
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base
from app.infra.db.mixins import AuditMixin


class Odontologo(AuditMixin, Base):
    __tablename__ = "odontologo"

    user_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid,
        ForeignKey("usuario.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    monto_turno: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    monto_senia: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    activo: Mapped[bool] = mapped_column(default=True, nullable=False)

    __table_args__ = (
        CheckConstraint("monto_turno >= 0", name="ck_odontologo_turno_no_negativo"),
        CheckConstraint("monto_senia >= 0", name="ck_odontologo_senia_no_negativa"),
    )


Index("ix_odontologo_activos", Odontologo.created_at, postgresql_where=text("is_active"))
