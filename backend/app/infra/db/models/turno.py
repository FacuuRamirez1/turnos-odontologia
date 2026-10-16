"""`Turno` + `TurnoHistorial` C-05 — reserva con máquina de estados (spec § reserva).

- `Turno`: `paciente_id/odontologo_id` FK RESTRICT, `inicio/fin` timestamptz,
  `estado` CHECK cerrado (7), `canal` CHECK (web|recepcion|mail),
  `idempotency_key` UNIQUE (P4), `version` lock optimista (default 1),
  `pago_id` UUID nullable **sin FK** (seam C-07, design D6),
  `reprogramado_de_id` FK nullable → turno.id (trazabilidad F3).
- P6 portable en modelo: UNIQUE (odontologo_id, inicio) (RN-DOBLE),
  CHECK fin>inicio; el EXCLUDE anti-solape + CHECK inicio>now() viven en
  la migración 003 (PG, btree_gist; SQLite no los soporta — se asertan
  estáticamente en test_migration_003). La app valida solape/pasado antes
  del INSERT y traduce IntegrityError → 409/422 (design D3).
- `TurnoHistorial`: append-only con actor NOT NULL + CHECK cerrado
  (backstop portable del trigger PG 003, RN-ESTADOS/P9).
- `Turno` es scopeada (`odontologo_id`): `BaseRepository` exige scope
  en constructor (P8 fail-closed, sin código extra).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base
from app.infra.db.mixins import AuditMixin

ESTADOS_TURNOS = (
    "creado",
    "confirmado",
    "atendido",
    "cancelado",
    "reprogramado",
    "no_show",
    "devuelto",
)

ACTORES_HISTORIAL = (
    "paciente",
    "odontologo",
    "recepcionista",
    "admin",
    "sistema",
)

CANALES_TURNO = ("web", "recepcion", "mail")


class Turno(AuditMixin, Base):
    __tablename__ = "turno"

    paciente_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid,
        ForeignKey("paciente.id", ondelete="RESTRICT"),
        nullable=False,
    )
    odontologo_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid,
        ForeignKey("odontologo.id", ondelete="RESTRICT"),
        nullable=False,
    )
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fin: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="creado")
    canal: Mapped[str] = mapped_column(String(20), nullable=False, default="web")
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    pago_id: Mapped[uuid.UUID | None] = mapped_column(SAUuid, nullable=True, default=None)
    reprogramado_de_id: Mapped[uuid.UUID | None] = mapped_column(
        SAUuid,
        ForeignKey("turno.id", ondelete="RESTRICT"),
        nullable=True,
        default=None,
    )

    __table_args__ = (
        CheckConstraint("fin > inicio", name="ck_turno_fin_mayor_inicio"),
        CheckConstraint(
            "estado IN ('creado', 'confirmado', 'atendido', 'cancelado', "
            "'reprogramado', 'no_show', 'devuelto')",
            name="ck_turno_estado_cerrado",
        ),
        CheckConstraint(
            "canal IN ('web', 'recepcion', 'mail')",
            name="ck_turno_canal_cerrado",
        ),
        CheckConstraint("version >= 1", name="ck_turno_version_positiva"),
        UniqueConstraint("odontologo_id", "inicio", name="uq_turno_odonto_inicio"),
    )


class TurnoHistorial(Base):
    """Append-only: sin `AuditMixin` (sin soft-delete) + sin UPDATE/DELETE
    del rol app (REVOKE en migración 003, P9)."""

    __tablename__ = "turno_historial"

    id: Mapped[uuid.UUID] = mapped_column(
        SAUuid,
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )
    turno_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid,
        ForeignKey("turno.id", ondelete="RESTRICT"),
        nullable=False,
    )
    estado_anterior: Mapped[str] = mapped_column(String(20), nullable=False)
    estado_nuevo: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    __table_args__ = (
        CheckConstraint(
            "actor_tipo IN ('paciente', 'odontologo', 'recepcionista', 'admin', 'sistema')",
            name="ck_historial_actor_cerrado",
        ),
    )


Index("ix_turno_odonto_inicio", Turno.odontologo_id, Turno.inicio)
Index("ix_turno_estado_created", Turno.estado, Turno.created_at)
Index("ix_historial_turno_fecha", TurnoHistorial.turno_id, TurnoHistorial.fecha)
