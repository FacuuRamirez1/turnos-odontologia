"""`RecordatorioMail` C-09 — outbox de mails transaccional (spec § outbox).

- PK UUID, `turno_id` FK RESTRICT a `turno.id`, `tipo` cerrado (3),
  `estado` cerrado (6), `intentos` acotado 0-3, hash de token único.
- `UNIQUE (turno_id, tipo)` = idempotencia de encolado (spec R1).
- `contexto_json` portable `JSON` en el modelo (SQLite en tests); la
  migración 004 usa `postgresql.JSONB` en PG — el contrato se aserta
  estáticamente en test_migration_004 (patrón C-05 con EXCLUDE).
- Index parcial `(estado, proximo_intento_at) WHERE is_active` para
  scheduler/reintentos; `turno_id` para trazabilidad.
"""

import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base
from app.infra.db.mixins import AuditMixin

TIPOS_RECORDATORIO = ("confirmacion", "recordatorio", "aviso_devolucion")
ESTADOS_RECORDATORIO = (
    "encolado",
    "enviado",
    "reintentando",
    "fallido",
    "confirmado_desde_mail",
    "cancelado_desde_mail",
)


class RecordatorioMail(AuditMixin, Base):
    __tablename__ = "recordatorio_mail"

    turno_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid,
        ForeignKey("turno.id", ondelete="RESTRICT"),
        nullable=False,
    )
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    destinatario: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    plantilla_version: Mapped[str] = mapped_column(String(20), nullable=False, default="v1")
    estado: Mapped[str] = mapped_column(String(30), nullable=False, default="encolado")
    intentos: Mapped[int] = mapped_column(nullable=False, default=0)
    ultimo_error: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    proximo_intento_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    enviado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    publicado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    token_accion_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, default=None, unique=True
    )
    token_expira_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    token_usado_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    contexto_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    __table_args__ = (
        CheckConstraint(
            "tipo IN ('confirmacion', 'recordatorio', 'aviso_devolucion')",
            name="ck_recordatorio_tipo_cerrado",
        ),
        CheckConstraint(
            "estado IN ('encolado', 'enviado', 'reintentando', 'fallido', "
            "'confirmado_desde_mail', 'cancelado_desde_mail')",
            name="ck_recordatorio_estado_cerrado",
        ),
        CheckConstraint(
            "intentos >= 0 AND intentos <= 3", name="ck_recordatorio_intentos_acotados"
        ),
        CheckConstraint(
            "token_accion_hash IS NULL OR token_expira_at IS NOT NULL",
            name="ck_recordatorio_token_hash_requiere_expira",
        ),
        UniqueConstraint("turno_id", "tipo", name="uq_recordatorio_turno_tipo"),
    )


Index("ix_recordatorio_estado_proximo", RecordatorioMail.estado,
      RecordatorioMail.proximo_intento_at,
      postgresql_where=sa.text("is_active"))
Index("ix_recordatorio_turno", RecordatorioMail.turno_id)
