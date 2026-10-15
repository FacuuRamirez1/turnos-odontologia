"""`Paciente` C-02 — identidad por DNI + consentimiento bloqueante (RN-CONSENTIMIENTO).

- `dni` UNIQUE (habilita reconocimiento A2 por DNI, solo ficticios P11).
- `consentimiento_datos` NOT NULL + `consentimiento_fecha` nullable con CHECK
  bloqueante: la fila SOLO existe con flag true Y timestamp (`IS TRUE AND ...`).
- Soft-delete vía `AuditMixin` + índice parcial `WHERE is_active`.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base
from app.infra.db.mixins import AuditMixin


class Paciente(AuditMixin, Base):
    __tablename__ = "paciente"

    dni: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    apellido: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    telefono: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    consentimiento_datos: Mapped[bool] = mapped_column(nullable=False)
    consentimiento_fecha: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    __table_args__ = (
        CheckConstraint(
            "consentimiento_datos IS TRUE AND consentimiento_fecha IS NOT NULL",
            name="ck_paciente_consentimiento_bloqueante",
        ),
    )


Index("ix_paciente_activos", Paciente.created_at, postgresql_where=text("is_active"))
