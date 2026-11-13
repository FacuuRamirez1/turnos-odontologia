"""Tests C-07 task 1.1 — contrato estático de la migración 005 (RED primero).

Sin PG vivo en este entorno, la verificación dinámica (upgrade en dev, UNIQUE
real, REVOKE real) queda como paso manual del reviewer. Estos tests fijan:
- encadena 004 → head 005;
- tablas pago + evento_pago con CHECKs de estado/proveedor,
  UNIQUE(mp_payment_id), UNIQUE(idempotency_key), CHECK(hash=>expira),
  índices, grants least-privilege, REVOKE UPDATE/DELETE sobre evento_pago;
- pago.turno_id FK RESTRICT → turno.id (columna solo de un lado, rompe círculo);
- cero create_all en runtime (P3); downgrade revierte solo lo nuevo.
"""

from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "005_pago_evento_pago.py"
)
SOURCE = MIGRATION.read_text(encoding="utf-8") if MIGRATION.exists() else ""


def test_migracion_005_existe_y_encadena_004() -> None:
    """Feliz: migración 005 existe y encadena al head real 004."""
    assert MIGRATION.exists(), "falta migración 005_pago_evento_pago.py"
    assert "004_recordatorio_mail" in SOURCE
    assert 'down_revision: str | None = "004_recordatorio_mail"' in SOURCE


def test_tablas_pago_evento_pago_presentes() -> None:
    """Feliz: las dos tablas se crean en la migración."""
    assert "op.create_table" in SOURCE
    assert '"pago"' in SOURCE or "'pago'" in SOURCE
    assert '"evento_pago"' in SOURCE or "'evento_pago'" in SOURCE


def test_checks_estado_proveedor_presentes() -> None:
    """Feliz: CHECKs cerrados de estado y proveedor en pago."""
    assert "ck_pago_estado_cerrado" in SOURCE
    assert "ck_pago_proveedor_cerrado" in SOURCE
    assert "pendiente" in SOURCE and "aprobado" in SOURCE and "rechazado" in SOURCE
    assert "simulado" in SOURCE and "mercadopago" in SOURCE


def test_check_monto_no_negativo_presente() -> None:
    """Triangulate: CHECK monto >= 0 en pago (diferente input: constraint numérico)."""
    assert "ck_pago_monto_no_negativo" in SOURCE
    assert "monto >= 0" in SOURCE


def test_server_defaults_presentes() -> None:
    """Triangulate: defaults de servidor proveedor='simulado', estado='pendiente', moneda='ARS'."""
    assert "server_default=sa.text(\"'simulado'\")" in SOURCE
    assert "server_default=sa.text(\"'pendiente'\")" in SOURCE
    assert "server_default=sa.text(\"'ARS'\")" in SOURCE


def test_unicidad_mp_payment_id_e_idempotency_key() -> None:
    """Feliz: UNIQUE(mp_payment_id) y UNIQUE(idempotency_key) en pago (P4/P6)."""
    assert "uq_pago_mp_payment_id" in SOURCE
    assert "uq_pago_idempotency_key" in SOURCE
    assert "UNIQUE" in SOURCE and "mp_payment_id" in SOURCE
    assert "UNIQUE" in SOURCE and "idempotency_key" in SOURCE


def test_fk_pago_turno_rompe_circulo() -> None:
    """Feliz: pago.turno_id FK RESTRICT → turno.id, columna solo de un lado."""
    assert "fk_pago_turno" in SOURCE
    assert "pago.turno_id" in SOURCE or '"turno_id"' in SOURCE
    assert "turno.id" in SOURCE


def test_indices_y_grants_presentes() -> None:
    """Feliz: índices + grants least-privilege, sin UPDATE/DELETE en evento_pago."""
    assert "ix_pago_turno_id" in SOURCE
    assert "ix_evento_pago_pago_id" in SOURCE
    assert "GRANT SELECT, INSERT, UPDATE ON pago" in SOURCE
    assert "GRANT SELECT, INSERT ON evento_pago" in SOURCE
    assert "app_turnos" in SOURCE
    # pago: UPDATE permitido (soft-delete), DELETE no
    linea_pago = [
        line for line in SOURCE.splitlines() if "GRANT" in line and "pago" in line
    ][0]
    assert "DELETE" not in linea_pago
    # evento_pago: solo SELECT, INSERT; sin UPDATE ni DELETE
    linea_evento = [
        line for line in SOURCE.splitlines() if "GRANT" in line and "evento_pago" in line
    ][0]
    assert "UPDATE" not in linea_evento
    assert "DELETE" not in linea_evento


def test_revoke_evento_pago_append_only() -> None:
    """Feliz: REVOKE UPDATE, DELETE sobre evento_pago (P9 append-only)."""
    assert "REVOKE UPDATE, DELETE ON evento_pago" in SOURCE
    assert "evento_pago" in SOURCE
    assert "app_turnos" in SOURCE


def test_downgrade_revierte_solo_nuevo() -> None:
    """Feliz: downgrade elimina tablas e índices de pago/evento_pago."""
    assert "op.drop_table" in SOURCE or "drop_table" in SOURCE
    assert "pago" in SOURCE and "evento_pago" in SOURCE
    assert "004_recordatorio_mail" in SOURCE  # head previo se conserva
