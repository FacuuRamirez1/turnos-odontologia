"""`AuditMixin` C-02 — identidad UUID + timestamps + soft-delete (RN-AUDIT).

Tipos right-sized (supabase-postgres-best-practices): PK `UUID` con default
Python (`uuid4`, portable a SQLite en tests) y backstop `gen_random_uuid()`
vía pgcrypto en Postgres; timestamps `timestamptz`.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, func, text
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.orm import Mapped, mapped_column


class AuditMixin:
    """Mezcla auditoría: borrado lógico, nunca físico (P9)."""

    id: Mapped[uuid.UUID] = mapped_column(
        SAUuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    def soft_delete(self, when: datetime | None = None) -> None:
        """Borrado lógico: marca inactivo + timestamp, conserva la fila."""

        self.is_active = False
        self.deleted_at = when or datetime.now(UTC)
