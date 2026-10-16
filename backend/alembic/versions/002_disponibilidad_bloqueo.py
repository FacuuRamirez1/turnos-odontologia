"""002_disponibilidad_bloqueo — tablas C-04 + constraints P6 (cero create_all).

- Extensión `btree_gist` (misma imagen PG que ya provee pgcrypto).
- Función IMMUTABLE `minutos(TIME) -> INT` para el rango de exclusión.
- `disponibilidad`: CHECKs portables + EXCLUDE no-solape por
  (odontologo_id, dia_semana) sobre int4range de minutos (D-OVERLAP:
  vigencia filtra, no participa en la exclusión — v1 documentado).
- `bloqueo`: CHECK rango + motivo cerrado + FK RESTRICT.
- Índices `ix_disponibilidad_od_dia` / `ix_bloqueo_od_desde` (supabase:
  WHERE/JOIN/ORDER BY).
- GRANTs least-privilege al rol app_turnos (SELECT/INSERT/UPDATE, sin DELETE).
- Downgrade completo: tablas + función (extensión se conserva, como pgcrypto).

Revision ID: 002_disponibilidad_bloqueo
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "002_disponibilidad_bloqueo"
down_revision: str | None = "001_core_v2off"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "app_turnos"


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        sa.text(
            "CREATE OR REPLACE FUNCTION minutos(t TIME) RETURNS INT "
            "AS $$ SELECT (EXTRACT(HOUR FROM t)::INT * 60 "
            "+ EXTRACT(MINUTE FROM t)::INT) $$ LANGUAGE sql IMMUTABLE"
        )
    )
    op.create_table(
        "disponibilidad",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("odontologo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("odontologo.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("dia_semana", sa.Integer(), nullable=False),
        sa.Column("hora_inicio", sa.Time(), nullable=False),
        sa.Column("hora_fin", sa.Time(), nullable=False),
        sa.Column("duracion_min", sa.Integer(), nullable=False),
        sa.Column("tope_dia", sa.Integer(), nullable=False),
        sa.Column("vigente_desde", sa.Date(), nullable=True),
        sa.Column("vigente_hasta", sa.Date(), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("dia_semana >= 0 AND dia_semana <= 6", name="ck_disponibilidad_dia_rango"),
        sa.CheckConstraint("hora_fin > hora_inicio", name="ck_disponibilidad_horas_orden"),
        sa.CheckConstraint("duracion_min > 0", name="ck_disponibilidad_duracion_positiva"),
        sa.CheckConstraint("tope_dia > 0", name="ck_disponibilidad_tope_positivo"),
        sa.CheckConstraint(
            "vigente_desde IS NULL OR vigente_hasta IS NULL OR vigente_desde <= vigente_hasta",
            name="ck_disponibilidad_vigencia_orden",
        ),
        sa.ExcludeConstraint(
            ("odontologo_id", "="),
            ("dia_semana", "="),
            (
                sa.text("int4range(minutos(hora_inicio), minutos(hora_fin))"),
                "&&",
            ),
            name="ex_disponibilidad_no_solape",
            using="gist",
        ),
    )
    op.create_index(
        "ix_disponibilidad_od_dia", "disponibilidad", ["odontologo_id", "dia_semana"],
        postgresql_where=sa.text("is_active"),
    )
    op.create_table(
        "bloqueo",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("odontologo_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("odontologo.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("desde", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hasta", sa.DateTime(timezone=True), nullable=False),
        sa.Column("motivo", sa.String(20), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("hasta > desde", name="ck_bloqueo_rango_orden"),
        sa.CheckConstraint(
            "motivo IN ('pausa', 'feriado', 'bloqueo', 'vacaciones')",
            name="ck_bloqueo_motivo_cerrado",
        ),
    )
    op.create_index(
        "ix_bloqueo_od_desde", "bloqueo", ["odontologo_id", "desde"],
        postgresql_where=sa.text("is_active"),
    )
    for tabla in ("disponibilidad", "bloqueo"):
        op.execute(sa.text(f"GRANT SELECT, INSERT, UPDATE ON {tabla} TO {APP_ROLE}"))


def downgrade() -> None:
    for tabla in ("bloqueo", "disponibilidad"):
        op.execute(sa.text(f"REVOKE ALL ON {tabla} FROM {APP_ROLE}"))
        op.drop_table(tabla)
    op.execute(sa.text("DROP FUNCTION IF EXISTS minutos(TIME)"))
    # btree_gist se conserva a propósito (la provee la imagen PG, como pgcrypto).
