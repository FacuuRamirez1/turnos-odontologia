"""007_paciente_campos_cifrados — C-13 task 1.2.

Agrega columnas cifradas con pgcrypto para DNI, email y telefono de paciente.
Los datos sensibles se almacenan cifrados en reposo (P6, 08 §7); la capa de
aplicacion descifra solo en lecturas autorizadas. La clave se provee por env
var ENC_KEY (P5: nunca hardcodeada).

Cero create_all en runtime (P3): solo Alembic.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "007_paciente_campos_cifrados"
down_revision: str | None = "006_devolucion_comprobante"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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


def upgrade() -> None:
    # pgcrypto ya esta disponible desde 001; asegurar extension en DB destino.
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # Columnas cifradas: se almacenan como bytea (pgcrypto encrypt devuelve bytea).
    op.add_column(
        "paciente",
        sa.Column(
            "dni_cifrado",
            postgresql.BYTEA(),
            nullable=True,
            comment="DNI cifrado con pgcrypto (clave ENC_KEY)",
        ),
    )
    op.add_column(
        "paciente",
        sa.Column(
            "email_cifrado",
            postgresql.BYTEA(),
            nullable=True,
            comment="Email cifrado con pgcrypto (clave ENC_KEY)",
        ),
    )
    op.add_column(
        "paciente",
        sa.Column(
            "telefono_cifrado",
            postgresql.BYTEA(),
            nullable=True,
            comment="Telefono cifrado con pgcrypto (clave ENC_KEY)",
        ),
    )

    # Poblar columnas cifradas desde los campos plano existentes.
    # Se usa pgp_sym_encrypt con la clave de sesion ENC_KEY.
    op.execute(
        sa.text(
            "UPDATE paciente SET dni_cifrado = "
            "pgp_sym_encrypt(dni::text, current_setting('app.enc_key', true)) "
            "WHERE dni IS NOT NULL AND dni_cifrado IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE paciente SET email_cifrado = "
            "pgp_sym_encrypt(email::text, current_setting('app.enc_key', true)) "
            "WHERE email IS NOT NULL AND email_cifrado IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE paciente SET telefono_cifrado = "
            "pgp_sym_encrypt(telefono::text, current_setting('app.enc_key', true)) "
            "WHERE telefono IS NOT NULL AND telefono_cifrado IS NULL"
        )
    )


def downgrade() -> None:
    op.drop_column("paciente", "dni_cifrado")
    op.drop_column("paciente", "email_cifrado")
    op.drop_column("paciente", "telefono_cifrado")
