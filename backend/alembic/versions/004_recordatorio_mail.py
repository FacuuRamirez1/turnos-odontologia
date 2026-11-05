"""004_recordatorio_mail — outbox de mails C-09 (down_revision = 003_turno_historial).

- `recordatorio_mail`: turno_id FK RESTRICT, tipo/estado CHECK cerrados,
  intentos 0-3 CHECK, token_accion_hash UNIQUE + CHECK(hash=>expira),
  contexto_json JSONB, UNIQUE(turno_id, tipo), índices
  (estado, proximo_intento_at) WHERE is_active y turno_id.
- Grants least-privilege: SELECT/INSERT/UPDATE a app_turnos, sin DELETE.
- Downgrade completo: revoca grants, quita índices, elimina tabla.
- Cero create_all en runtime (P3): solo Alembic.

Revision ID: 004_recordatorio_mail
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "004_recordatorio_mail"
down_revision: str | None = "003_turno_historial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "app_turnos"

TIPOS = "confirmacion, recordatorio, aviso_devolucion"
ESTADOS = "encolado, enviado, reintentando, fallido, confirmado_desde_mail, cancelado_desde_mail"


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "recordatorio_mail",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("turno_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("turno.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("destinatario", sa.String(255), nullable=False, server_default=sa.text("''")),
        sa.Column("plantilla_version", sa.String(20), nullable=False, server_default=sa.text("'v1'")),
        sa.Column("estado", sa.String(30), nullable=False, server_default=sa.text("'encolado'")),
        sa.Column("intentos", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("ultimo_error", sa.Text(), nullable=True),
        sa.Column("proximo_intento_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enviado_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("publicado_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_accion_hash", sa.String(64), nullable=True),
        sa.Column("token_expira_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_usado_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contexto_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        *_audit_columns(),
        sa.CheckConstraint(
            "tipo IN ('confirmacion', 'recordatorio', 'aviso_devolucion')",
            name="ck_recordatorio_tipo_cerrado",
        ),
        sa.CheckConstraint(
            "estado IN ('encolado', 'enviado', 'reintentando', 'fallido', "
            "'confirmado_desde_mail', 'cancelado_desde_mail')",
            name="ck_recordatorio_estado_cerrado",
        ),
        sa.CheckConstraint("intentos >= 0 AND intentos <= 3", name="ck_recordatorio_intentos_acotados"),
        sa.CheckConstraint(
            "token_accion_hash IS NULL OR token_expira_at IS NOT NULL",
            name="ck_recordatorio_token_hash_requiere_expira",
        ),
        sa.ForeignKeyConstraint(["turno_id"], ["turno.id"], ondelete="RESTRICT", name="fk_recordatorio_turno"),
        sa.UniqueConstraint("turno_id", "tipo", name="uq_recordatorio_turno_tipo"),
        sa.UniqueConstraint("token_accion_hash", name="uq_recordatorio_token_hash"),
    )
    op.create_index(
        "ix_recordatorio_estado_proximo",
        "recordatorio_mail",
        ["estado", "proximo_intento_at"],
        postgresql_where=sa.text("is_active"),
    )
    op.create_index("ix_recordatorio_turno", "recordatorio_mail", ["turno_id"])
    op.execute(sa.text(f"GRANT SELECT, INSERT, UPDATE ON recordatorio_mail TO {APP_ROLE}"))


def downgrade() -> None:
    op.execute(sa.text(f"REVOKE ALL ON recordatorio_mail FROM {APP_ROLE}"))
    op.drop_index("ix_recordatorio_turno", table_name="recordatorio_mail")
    op.drop_index("ix_recordatorio_estado_proximo", table_name="recordatorio_mail")
    op.drop_table("recordatorio_mail")
