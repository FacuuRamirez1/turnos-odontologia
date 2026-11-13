"""005_pago_evento_pago — tablas C-07 pagos (down_revision = 004_recordatorio_mail).

- `pago`: entidad separada del turno (D13) con `turno_id` FK RESTRICT → `turno.id`
  (columna solo de un lado: rompe la referencia circular turno↔pago),
  `odontologo_id` FK RESTRICT → `odontologo.id`, `monto`, `moneda='ARS'`,
  `proveedor` (simulado|mercadopago), `mp_payment_id` UNIQUE
  (sintético `sim_pay_<uuid>` si simulado), `mp_preference_id` nullable,
  `estado` (pendiente|aprobado|rechazado|reembolsado_parcial|reembolsado_total),
  `idempotency_key` UNIQUE (P4), audit columns.
- `evento_pago`: append-only (sin AuditMixin, sin UPDATE/DELETE del rol app,
  P9): `pago_id` FK RESTRICT → `pago.id`, `tipo_evento`,
  `payload_json` JSONB, `actor`, `created_at`.
- Índices: `ix_pago_turno_id`, `ix_pago_estado`, `ix_evento_pago_pago_id`,
  `ix_evento_pago_tipo`.
- Grants least-privilege: SELECT/INSERT/UPDATE a `pago`, SELECT/INSERT a
  `evento_pago`; `REVOKE UPDATE, DELETE ON evento_pago` (P9 append-only).
- Downgrade completo. Cero `create_all` en runtime (P3).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "005_pago_evento_pago"
down_revision: str | None = "004_recordatorio_mail"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "app_turnos"

PROVEEDORES = "simulado, mercadopago"
ESTADOS_PAGO = (
    "pendiente, aprobado, rechazado, reembolsado_parcial, reembolsado_total"
)
TIPOS_EVENTO_PAGO = (
    "creado, webhook_recibido, aprobado, rechazado, "
    "devolucion_solicitada, devolucion_aprobada, devolucion_ejecutada, conciliado"
)


def _audit_columns() -> list[sa.Column]:
    return [
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "pago",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("turno_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("odontologo_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("monto", sa.Numeric(10, 2), nullable=False),
        sa.Column("moneda", sa.String(3), nullable=False, server_default=sa.text("'ARS'")),
        sa.Column("proveedor", sa.String(20), nullable=False, server_default=sa.text("'simulado'")),
        sa.Column("mp_payment_id", sa.String(100), nullable=False),
        sa.Column("mp_preference_id", sa.String(100), nullable=True),
        sa.Column("estado", sa.String(30), nullable=False, server_default=sa.text("'pendiente'")),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["turno_id"], ["turno.id"], ondelete="RESTRICT", name="fk_pago_turno"),
        sa.ForeignKeyConstraint(["odontologo_id"], ["odontologo.id"], ondelete="RESTRICT", name="fk_pago_odontologo"),
        sa.CheckConstraint(
            "estado IN ('pendiente', 'aprobado', 'rechazado', 'reembolsado_parcial', 'reembolsado_total')",
            name="ck_pago_estado_cerrado",
        ),
        sa.CheckConstraint(
            "proveedor IN ('simulado', 'mercadopago')",
            name="ck_pago_proveedor_cerrado",
        ),
        sa.CheckConstraint("monto >= 0", name="ck_pago_monto_no_negativo"),
        sa.UniqueConstraint("mp_payment_id", name="uq_pago_mp_payment_id"),
        sa.UniqueConstraint("idempotency_key", name="uq_pago_idempotency_key"),
    )
    op.create_index(
        "ix_pago_turno_id", "pago", ["turno_id"], postgresql_where=sa.text("is_active")
    )
    op.create_index(
        "ix_pago_estado", "pago", ["estado"], postgresql_where=sa.text("is_active")
    )
    op.create_table(
        "evento_pago",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("pago_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("pago.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("tipo_evento", sa.String(30), nullable=False),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "actor IN ('paciente', 'odontologo', 'recepcionista', 'admin', 'sistema')",
            name="ck_evento_pago_actor_cerrado",
        ),
        sa.CheckConstraint(
            "tipo_evento IN ('creado', 'webhook_recibido', 'aprobado', 'rechazado', "
            "'devolucion_solicitada', 'devolucion_aprobada', 'devolucion_ejecutada', 'conciliado')",
            name="ck_evento_pago_tipo_cerrado",
        ),
    )
    op.create_index("ix_evento_pago_pago_id", "evento_pago", ["pago_id"])
    op.create_index("ix_evento_pago_tipo", "evento_pago", ["tipo_evento"])
    op.execute(sa.text(f"GRANT SELECT, INSERT, UPDATE ON pago TO {APP_ROLE}"))
    op.execute(sa.text(f"GRANT SELECT, INSERT ON evento_pago TO {APP_ROLE}"))
    op.execute(sa.text(f"REVOKE UPDATE, DELETE ON evento_pago FROM {APP_ROLE}"))


def downgrade() -> None:
    op.execute(sa.text(f"REVOKE ALL ON evento_pago FROM {APP_ROLE}"))
    op.execute(sa.text(f"REVOKE ALL ON pago FROM {APP_ROLE}"))
    op.drop_index("ix_evento_pago_tipo", table_name="evento_pago")
    op.drop_index("ix_evento_pago_pago_id", table_name="evento_pago")
    op.drop_table("evento_pago")
    op.drop_index("ix_pago_estado", table_name="pago")
    op.drop_index("ix_pago_turno_id", table_name="pago")
    op.drop_table("pago")
