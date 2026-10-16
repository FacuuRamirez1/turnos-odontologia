"""003_turno_historial — tablas C-05 + constraints P6 (cero create_all).

- Extensión `btree_gist` (igual que 002; la provee la imagen PG).
- `turno`: `paciente_id/odontologo_id` FK RESTRICT, `inicio/fin` timestamptz,
  `estado` CHECK cerrado (7 estados), `canal` CHECK (web|recepcion|mail),
  `idempotency_key` UNIQUE (P4), `version` lock optimista default 1,
  `pago_id` UUID NULLABLE **sin FK** (seam C-07, design D6),
  `reprogramado_de_id` FK nullable → turno.id (trazabilidad F3).
- P6: `UNIQUE (odontologo_id, inicio)` (RN-DOBLE, `uq_turno_odonto_inicio`),
  `EXCLUDE USING gist` anti-solape por profesional sobre
  `tstzrange(inicio, fin)` (`ex_turno_no_solape`, RN-SOLAPE),
  `CHECK (fin > inicio)` (`ck_turno_fin_mayor_inicio`),
  `CHECK (inicio > now())` (`ck_turno_inicio_futuro`, RN-PASADO).
- `turno_historial`: append-only (`turno_id` FK RESTRICT, estados, actor
  CHECK cerrado + NOT NULL, fecha default now(), motivo) + trigger
  `BEFORE INSERT` que rechaza actor nulo (RN-ESTADOS, backstop DB).
- Índices (supabase: WHERE/JOIN/ORDER BY): `ix_turno_odonto_inicio`
  (agenda + resta ocupados), `ix_turno_estado_created` (job expiración),
  `ix_historial_turno_fecha` (auditoría por turno).
- Grants least-privilege: `turno` SELECT/INSERT/UPDATE (soft-delete es
  UPDATE), `turno_historial` SELECT/INSERT + `REVOKE UPDATE, DELETE`
  (P9 append-only, base preparada en C-02).
- Downgrade completo: trigger + tablas (extensión se conserva).

Revision ID: 003_turno_historial
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "003_turno_historial"
down_revision: str | None = "002_disponibilidad_bloqueo"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "app_turnos"

ESTADOS = "creado, confirmado, atendido, cancelado, reprogramado, no_show, devuelto"
ACTORES = "paciente, odontologo, recepcionista, admin, sistema"
CANALES = "web, recepcion, mail"


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.create_table(
        "turno",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("paciente_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("paciente.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("odontologo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("odontologo.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fin", sa.DateTime(timezone=True), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False, server_default=sa.text("'creado'")),
        sa.Column("canal", sa.String(20), nullable=False, server_default=sa.text("'web'")),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("pago_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reprogramado_de_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("turno.id", ondelete="RESTRICT"), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("fin > inicio", name="ck_turno_fin_mayor_inicio"),
        sa.CheckConstraint("inicio > now()", name="ck_turno_inicio_futuro"),
        sa.CheckConstraint(
            "estado IN ('creado', 'confirmado', 'atendido', 'cancelado', "
            "'reprogramado', 'no_show', 'devuelto')",
            name="ck_turno_estado_cerrado",
        ),
        sa.CheckConstraint(
            "canal IN ('web', 'recepcion', 'mail')",
            name="ck_turno_canal_cerrado",
        ),
        sa.CheckConstraint("version >= 1", name="ck_turno_version_positiva"),
        sa.UniqueConstraint("idempotency_key", name="uq_turno_idempotency_key"),
        sa.UniqueConstraint("odontologo_id", "inicio", name="uq_turno_odonto_inicio"),
        sa.ExcludeConstraint(
            ("odontologo_id", "="),
            (sa.text("tstzrange(inicio, fin)"), "&&"),
            name="ex_turno_no_solape",
            using="gist",
        ),
    )
    op.create_index(
        "ix_turno_odonto_inicio", "turno", ["odontologo_id", "inicio"],
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "ix_turno_estado_created", "turno", ["estado", "created_at"],
        postgresql_where=sa.text("is_active"),
    )
    op.create_table(
        "turno_historial",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("turno_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("turno.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("estado_anterior", sa.String(20), nullable=False),
        sa.Column("estado_nuevo", sa.String(20), nullable=False),
        sa.Column("actor_tipo", sa.String(20), nullable=False),
        sa.Column("actor_id", sa.String(255), nullable=False),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "actor_tipo IN ('paciente', 'odontologo', 'recepcionista', 'admin', 'sistema')",
            name="ck_historial_actor_cerrado",
        ),
    )
    op.create_index(
        "ix_historial_turno_fecha", "turno_historial", ["turno_id", "fecha"],
    )
    op.execute(
        sa.text(
            "CREATE OR REPLACE FUNCTION rechazar_historial_sin_actor() RETURNS trigger AS $$ "
            "BEGIN "
            "IF NEW.actor_tipo IS NULL OR NEW.actor_id IS NULL THEN "
            "RAISE EXCEPTION 'historial sin actor (RN-ESTADOS)'; "
            "END IF; "
            "RETURN NEW; "
            "END; $$ LANGUAGE plpgsql"
        )
    )
    op.execute(
        sa.text(
            "CREATE TRIGGER trg_historial_con_actor "
            "BEFORE INSERT ON turno_historial "
            "FOR EACH ROW EXECUTE FUNCTION rechazar_historial_sin_actor()"
        )
    )
    op.execute(sa.text("GRANT SELECT, INSERT, UPDATE ON turno TO app_turnos"))
    op.execute(sa.text("GRANT SELECT, INSERT ON turno_historial TO app_turnos"))
    op.execute(sa.text("REVOKE UPDATE, DELETE ON turno_historial FROM app_turnos"))


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_historial_con_actor ON turno_historial"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS rechazar_historial_sin_actor()"))
    op.execute(sa.text("REVOKE ALL ON turno_historial FROM app_turnos"))
    op.execute(sa.text("REVOKE ALL ON turno FROM app_turnos"))
    op.drop_index("ix_historial_turno_fecha", table_name="turno_historial")
    op.drop_table("turno_historial")
    op.drop_index("ix_turno_estado_created", table_name="turno")
    op.drop_index("ix_turno_odonto_inicio", table_name="turno")
    op.drop_table("turno")
    # btree_gist se conserva a propósito (la provee la imagen PG, como pgcrypto).
