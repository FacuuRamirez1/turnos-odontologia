"""`Usuario` C-02 — identidad staff con roles cerrados (spec § staff user identity).

- `email` único case-insensitive: índice funcional sobre `lower(email)` (P6)
  + normalización en escritura (strip + lower).
- `password_hash`: solo hash ≥ 60 chars (CHECK); nunca plaintext (C-03 hashea).
- `rol`: CHECK cerrado `odontologo | recepcionista | admin`.
- `odontologo_id`: UUID nullable SIN FK — el vínculo canónico es
  `Odontologo.user_id → usuario.id` (FK única); el reverso como FK crearía
  dependencia circular. C-03 valida `rol='odontologo' ⇒ vinculado`.
"""

import uuid

from sqlalchemy import CheckConstraint, Index, String, func, text
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.infra.db.base import Base
from app.infra.db.mixins import AuditMixin

ROLES_VALIDOS = ("odontologo", "recepcionista", "admin")


class Usuario(AuditMixin, Base):
    __tablename__ = "usuario"

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rol: Mapped[str] = mapped_column(String(20), nullable=False)
    odontologo_id: Mapped[uuid.UUID | None] = mapped_column(
        SAUuid, nullable=True, default=None
    )
    activo: Mapped[bool] = mapped_column(default=True, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "rol IN ('odontologo', 'recepcionista', 'admin')",
            name="ck_usuario_rol_cerrado",
        ),
        CheckConstraint(
            "length(password_hash) >= 60",
            name="ck_usuario_hash_minimo",
        ),
    )

    @validates("email")
    def _normalizar_email(self, _key: str, value: str) -> str:
        return value.strip().lower()


# Unicidad case-insensitive (mitiga Riesgo email de design): `Admin@x` ≡ `admin@x`.
Index("uq_usuario_email_lower", func.lower(Usuario.email), unique=True)
# Lecturas estándar de activos (índice parcial; en SQLite el `where` se ignora).
Index("ix_usuario_activos", Usuario.created_at, postgresql_where=text("is_active"))
