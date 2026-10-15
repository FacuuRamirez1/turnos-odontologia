"""001_core_v2off — persistencia fundacional C-02 (P3: solo Alembic, cero create_all).

Secciones:
  A. CORE v1: `usuario`, `odontologo`, `paciente` + constraints P6 + rol least-privilege.
  B. V2-OFF (P13): `lista_espera`, `notificacion_whatsapp` — SOLO DDL, sin escrituras en v1.
  C. Previsión P6 de C-05 (documentada, NO implementada): UNIQUE (odontologo_id,
     inicio) + EXCLUDE USING gist + CHECK (inicio > now()) viven en C-05 sobre
     `turno`; aquí no se crea ningún stub de turno/pago/mail.

Revision ID: 001_core_v2off
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001_core_v2off"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "app_turnos"


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


# ============================================================================
# A. CORE v1
# ============================================================================


def _create_usuario() -> None:
    op.create_table(
        "usuario",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("rol", sa.String(20), nullable=False),
        # Sin FK: el vínculo canónico es odontologo.user_id → usuario.id (evita ciclo).
        sa.Column("odontologo_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_audit_columns(),
        sa.CheckConstraint(
            "rol IN ('odontologo', 'recepcionista', 'admin')",
            name="ck_usuario_rol_cerrado",
        ),
        sa.CheckConstraint(
            "length(password_hash) >= 60",
            name="ck_usuario_hash_minimo",
        ),
    )
    op.create_index(
        "uq_usuario_email_lower", "usuario", [sa.text("lower(email)")], unique=True
    )
    op.create_index(
        "ix_usuario_activos",
        "usuario",
        ["created_at"],
        postgresql_where=sa.text("is_active"),
    )


def _create_odontologo() -> None:
    op.create_table(
        "odontologo",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("usuario.id", ondelete="RESTRICT"),
            unique=True,
            nullable=False,
        ),
        sa.Column("monto_turno", sa.Numeric(10, 2), nullable=False),
        sa.Column("monto_senia", sa.Numeric(10, 2), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        *_audit_columns(),
        sa.CheckConstraint("monto_turno >= 0", name="ck_odontologo_turno_no_negativo"),
        sa.CheckConstraint("monto_senia >= 0", name="ck_odontologo_senia_no_negativa"),
    )
    op.create_index(
        "ix_odontologo_activos",
        "odontologo",
        ["created_at"],
        postgresql_where=sa.text("is_active"),
    )


def _create_paciente() -> None:
    op.create_table(
        "paciente",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("dni", sa.String(20), unique=True, nullable=False),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("apellido", sa.String(120), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("telefono", sa.String(50), nullable=True),
        sa.Column("consentimiento_datos", sa.Boolean(), nullable=False),
        sa.Column("consentimiento_fecha", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        # RN-CONSENTIMIENTO bloqueante (P6/P11): sin flag true + fecha no hay fila.
        sa.CheckConstraint(
            "consentimiento_datos IS TRUE AND consentimiento_fecha IS NOT NULL",
            name="ck_paciente_consentimiento_bloqueante",
        ),
    )
    op.create_index(
        "ix_paciente_activos",
        "paciente",
        ["created_at"],
        postgresql_where=sa.text("is_active"),
    )


# ============================================================================
# B. V2-OFF (P13) — solo DDL, sin repositorio de escritura ni seed en v1
# ============================================================================


def _create_v2_off() -> None:
    op.create_table(
        "lista_espera",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("nombre", sa.String(120), nullable=False),
        sa.Column("contacto", sa.String(255), nullable=False),
        sa.Column("odontologo_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("nota", sa.Text(), nullable=True),
        *_audit_columns(),
    )
    op.create_index(
        "ix_lista_espera_activos",
        "lista_espera",
        ["created_at"],
        postgresql_where=sa.text("is_active"),
    )
    op.create_table(
        "notificacion_whatsapp",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("destino", sa.String(50), nullable=False),
        sa.Column("mensaje", sa.String(1000), nullable=False),
        sa.Column(
            "estado",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pendiente'"),
        ),
        *_audit_columns(),
        sa.CheckConstraint(
            "estado IN ('pendiente', 'enviada', 'fallida')",
            name="ck_whatsapp_estado_cerrado",
        ),
    )
    op.create_index(
        "ix_whatsapp_activos",
        "notificacion_whatsapp",
        ["created_at"],
        postgresql_where=sa.text("is_active"),
    )


# ============================================================================
# Rol least-privilege + previsión append-only (P9)
# ============================================================================


def _create_app_role() -> None:
    op.execute(
        sa.text(
            "DO $$ BEGIN "
            "IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_turnos') THEN "
            "CREATE ROLE app_turnos NOLOGIN; "
            "END IF; END $$;"
        )
    )
    op.execute(sa.text("GRANT USAGE ON SCHEMA public TO app_turnos"))
    # Core: SELECT + INSERT + UPDATE (el soft-delete es un UPDATE). Sin DELETE:
    # ningún borrado físico sale de la app, ni hoy ni cuando lleguen las
    # tablas append-only (C-05 `turno_historial`, C-07 `evento_pago`), sobre las
    # que C-05/C-07 harán efectivos estos cortafuegos:
    #   REVOKE UPDATE, DELETE ON turno_historial FROM app_turnos;
    #   REVOKE UPDATE, DELETE ON evento_pago FROM app_turnos;
    # (No se revocan aquí: las tablas aún no existen — ver design D-aislamiento.)
    for tabla in ("usuario", "odontologo", "paciente", "lista_espera", "notificacion_whatsapp"):
        op.execute(
            sa.text(f"GRANT SELECT, INSERT, UPDATE ON {tabla} TO {APP_ROLE}")
        )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    _create_usuario()
    _create_odontologo()
    _create_paciente()
    _create_v2_off()
    _create_app_role()


def downgrade() -> None:
    op.execute(sa.text(f"REVOKE ALL ON SCHEMA public FROM {APP_ROLE}"))
    for tabla in ("notificacion_whatsapp", "lista_espera", "paciente", "odontologo", "usuario"):
        op.execute(sa.text(f"REVOKE ALL ON {tabla} FROM {APP_ROLE}"))
        op.drop_table(tabla)
    op.execute(sa.text(f"DROP ROLE IF EXISTS {APP_ROLE}"))
    # pgcrypto se conserva a propósito: la provee init-pgcrypto.sql de C-01.
