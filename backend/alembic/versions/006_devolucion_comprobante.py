"""006_devolucion_comprobante — tablas C-08 (down_revision = 005_pago_evento_pago).

- `devolucion`: una por pago (UNIQUE pago_id, P4/P6), idempotency_key UNIQUE,
  mp_refund_id UNIQUE, CHECK porcentaje IN (100, 60) y monto > 0 (la cotización
  0 % NO crea fila, decisión humana), CHECK estado cerrado, CHECK de
  coherencia actor/fecha por estado, CHECK ejecutada => mp_refund_id.
  Triggers: transición de estado (pendiente→aprobada|rechazada,
  aprobada→ejecutada) y `monto <= pago.monto` (doble barrera app + DB).
- `comprobante`: inmutable (SELECT/INSERT, REVOKE UPDATE/DELETE, P9), número
  correlativo desde `comprobante_numero_seq`, UNIQUE parciales por pago
  (concepto 'pago') y por devolución, `cae` nullable (ARCA apagado, P13).
- `evento_pago`: se reemplaza `ck_evento_pago_tipo_cerrado` agregando
  `devolucion_rechazada`. El downgrade restaura el CHECK original y aborta
  si existen eventos `devolucion_rechazada` (no se pierde audit trail).
- Cero `create_all` en runtime (P3): solo Alembic.

Revision ID: 006_devolucion_comprobante
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "006_devolucion_comprobante"
down_revision: str | None = "005_pago_evento_pago"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "app_turnos"

TIPOS_EVENTO_ANTES = (
    "'creado', 'webhook_recibido', 'aprobado', 'rechazado', "
    "'devolucion_solicitada', 'devolucion_aprobada', 'devolucion_ejecutada', 'conciliado'"
)
TIPOS_EVENTO_DESPUES = (
    "'creado', 'webhook_recibido', 'aprobado', 'rechazado', "
    "'devolucion_solicitada', 'devolucion_aprobada', 'devolucion_rechazada', "
    "'devolucion_ejecutada', 'conciliado'"
)


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def _uuid_fk(nombre: str, destino: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(
        nombre,
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey(destino, ondelete="RESTRICT"),
        nullable=nullable,
    )


def upgrade() -> None:
    op.create_table(
        "devolucion",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        _uuid_fk("pago_id", "pago.id"),
        _uuid_fk("turno_id", "turno.id"),
        sa.Column("monto", sa.Numeric(10, 2), nullable=False),
        sa.Column("porcentaje", sa.SmallInteger(), nullable=False),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column("estado", sa.String(20), nullable=False, server_default=sa.text("'pendiente'")),
        sa.Column("idempotency_key", sa.String(80), nullable=False),
        sa.Column("mp_refund_id", sa.String(100), nullable=True),
        _uuid_fk("aprobada_por", "usuario.id", nullable=True),
        sa.Column("aprobada_at", sa.DateTime(timezone=True), nullable=True),
        _uuid_fk("rechazada_por", "usuario.id", nullable=True),
        sa.Column("rechazada_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("motivo_rechazo", sa.Text(), nullable=True),
        _uuid_fk("ejecutada_por", "usuario.id", nullable=True),
        sa.Column("ejecutada_at", sa.DateTime(timezone=True), nullable=True),
        *_audit_columns(),
        sa.CheckConstraint("porcentaje IN (100, 60)", name="ck_devolucion_porcentaje_cerrado"),
        sa.CheckConstraint("monto > 0", name="ck_devolucion_monto_positivo"),
        sa.CheckConstraint(
            "estado IN ('pendiente', 'aprobada', 'rechazada', 'ejecutada')",
            name="ck_devolucion_estado_cerrado",
        ),
        sa.CheckConstraint(
            "estado <> 'ejecutada' OR mp_refund_id IS NOT NULL",
            name="ck_devolucion_ejecutada_con_refund",
        ),
        sa.CheckConstraint(
            "estado NOT IN ('aprobada', 'ejecutada') "
            "OR (aprobada_por IS NOT NULL AND aprobada_at IS NOT NULL)",
            name="ck_devolucion_aprobada_con_actor",
        ),
        sa.CheckConstraint(
            "estado <> 'rechazada' OR (rechazada_por IS NOT NULL "
            "AND rechazada_at IS NOT NULL AND motivo_rechazo IS NOT NULL)",
            name="ck_devolucion_rechazada_con_actor",
        ),
        sa.CheckConstraint(
            "estado <> 'ejecutada' OR (ejecutada_por IS NOT NULL AND ejecutada_at IS NOT NULL)",
            name="ck_devolucion_ejecutada_con_actor",
        ),
        sa.UniqueConstraint("pago_id", name="uq_devolucion_pago"),
        sa.UniqueConstraint("idempotency_key", name="uq_devolucion_idempotency_key"),
        sa.UniqueConstraint("mp_refund_id", name="uq_devolucion_mp_refund_id"),
    )
    op.create_index("ix_devolucion_estado", "devolucion", ["estado"], postgresql_where=sa.text("is_active"))
    op.create_index("ix_devolucion_turno_id", "devolucion", ["turno_id"])

    op.execute(
        sa.text(
            "CREATE OR REPLACE FUNCTION devolucion_guard_transicion() RETURNS trigger AS $$ "
            "BEGIN "
            "IF NEW.estado <> OLD.estado AND NOT ("
            "(OLD.estado = 'pendiente' AND NEW.estado IN ('aprobada', 'rechazada')) "
            "OR (OLD.estado = 'aprobada' AND NEW.estado = 'ejecutada')) THEN "
            "RAISE EXCEPTION 'transicion de devolucion invalida: % -> %', OLD.estado, NEW.estado; "
            "END IF; "
            "RETURN NEW; "
            "END; $$ LANGUAGE plpgsql"
        )
    )
    op.execute(
        sa.text(
            "CREATE TRIGGER trg_devolucion_guard_transicion "
            "BEFORE UPDATE ON devolucion "
            "FOR EACH ROW EXECUTE FUNCTION devolucion_guard_transicion()"
        )
    )
    op.execute(
        sa.text(
            "CREATE OR REPLACE FUNCTION devolucion_guard_monto() RETURNS trigger AS $$ "
            "DECLARE monto_pago NUMERIC(10, 2); "
            "BEGIN "
            "SELECT monto INTO monto_pago FROM pago WHERE id = NEW.pago_id; "
            "IF monto_pago IS NULL OR NEW.monto > monto_pago THEN "
            "RAISE EXCEPTION 'monto de devolucion % excede el pago %', NEW.monto, monto_pago; "
            "END IF; "
            "RETURN NEW; "
            "END; $$ LANGUAGE plpgsql"
        )
    )
    op.execute(
        sa.text(
            "CREATE TRIGGER trg_devolucion_guard_monto "
            "BEFORE INSERT ON devolucion "
            "FOR EACH ROW EXECUTE FUNCTION devolucion_guard_monto()"
        )
    )

    op.execute(sa.text("CREATE SEQUENCE comprobante_numero_seq"))
    op.create_table(
        "comprobante",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        _uuid_fk("pago_id", "pago.id"),
        _uuid_fk("devolucion_id", "devolucion.id", nullable=True),
        _uuid_fk("turno_id", "turno.id"),
        sa.Column("tipo", sa.String(20), nullable=False, server_default=sa.text("'recibo_interno'")),
        sa.Column("concepto", sa.String(20), nullable=False),
        sa.Column(
            "numero",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'RI-' || lpad(nextval('comprobante_numero_seq')::text, 6, '0')"),
        ),
        sa.Column("monto", sa.Numeric(10, 2), nullable=False),
        sa.Column("moneda", sa.String(3), nullable=False, server_default=sa.text("'ARS'")),
        sa.Column("cae", sa.String(20), nullable=True),
        sa.Column("emitida_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("simulado", sa.Boolean(), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.CheckConstraint(
            "tipo IN ('recibo_interno', 'factura_arca')", name="ck_comprobante_tipo_cerrado"
        ),
        sa.CheckConstraint(
            "concepto IN ('pago', 'devolucion')", name="ck_comprobante_concepto_cerrado"
        ),
        sa.CheckConstraint(
            "(concepto = 'devolucion') = (devolucion_id IS NOT NULL)",
            name="ck_comprobante_concepto_devolucion_id",
        ),
        sa.CheckConstraint("monto >= 0", name="ck_comprobante_monto_no_negativo"),
        sa.UniqueConstraint("numero", name="uq_comprobante_numero"),
    )
    op.create_index(
        "uq_comprobante_pago_concepto_pago",
        "comprobante",
        ["pago_id"],
        unique=True,
        postgresql_where=sa.text("concepto = 'pago'"),
    )
    op.create_index(
        "uq_comprobante_devolucion",
        "comprobante",
        ["devolucion_id"],
        unique=True,
        postgresql_where=sa.text("devolucion_id IS NOT NULL"),
    )
    op.create_index("ix_comprobante_pago_id", "comprobante", ["pago_id"])
    op.create_index("ix_comprobante_turno_id", "comprobante", ["turno_id"])

    op.drop_constraint("ck_evento_pago_tipo_cerrado", "evento_pago", type_="check")
    op.create_check_constraint(
        "ck_evento_pago_tipo_cerrado",
        "evento_pago",
        f"tipo_evento IN ({TIPOS_EVENTO_DESPUES})",
    )

    op.execute(sa.text(f"GRANT SELECT, INSERT, UPDATE ON devolucion TO {APP_ROLE}"))
    op.execute(sa.text(f"GRANT SELECT, INSERT ON comprobante TO {APP_ROLE}"))
    op.execute(sa.text(f"REVOKE UPDATE, DELETE ON comprobante FROM {APP_ROLE}"))
    op.execute(sa.text(f"GRANT USAGE ON SEQUENCE comprobante_numero_seq TO {APP_ROLE}"))


def downgrade() -> None:
    bind = op.get_bind()
    rechazados = bind.execute(
        sa.text("SELECT count(*) FROM evento_pago WHERE tipo_evento = 'devolucion_rechazada'")
    ).scalar_one()
    if rechazados:
        raise RuntimeError(
            "downgrade 006 abortado: existen eventos 'devolucion_rechazada' en evento_pago "
            "(se perdería audit trail, P9)"
        )

    op.drop_constraint("ck_evento_pago_tipo_cerrado", "evento_pago", type_="check")
    op.create_check_constraint(
        "ck_evento_pago_tipo_cerrado",
        "evento_pago",
        f"tipo_evento IN ({TIPOS_EVENTO_ANTES})",
    )

    op.execute(sa.text(f"REVOKE ALL ON SEQUENCE comprobante_numero_seq FROM {APP_ROLE}"))
    op.execute(sa.text(f"REVOKE ALL ON comprobante FROM {APP_ROLE}"))
    op.drop_index("ix_comprobante_turno_id", table_name="comprobante")
    op.drop_index("ix_comprobante_pago_id", table_name="comprobante")
    op.drop_index("uq_comprobante_devolucion", table_name="comprobante")
    op.drop_index("uq_comprobante_pago_concepto_pago", table_name="comprobante")
    op.drop_table("comprobante")
    op.execute(sa.text("DROP SEQUENCE comprobante_numero_seq"))

    op.execute(sa.text(f"REVOKE ALL ON devolucion FROM {APP_ROLE}"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_devolucion_guard_monto ON devolucion"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS devolucion_guard_monto()"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_devolucion_guard_transicion ON devolucion"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS devolucion_guard_transicion()"))
    op.drop_index("ix_devolucion_turno_id", table_name="devolucion")
    op.drop_index("ix_devolucion_estado", table_name="devolucion")
    op.drop_table("devolucion")
