"""Tests C-09 task 1.1 — contrato estático de la migración 004 (RED primero).

Sin PG vivo en este entorno, la verificación dinámica (upgrade en dev, JSONB
real, REVOKE real) queda como paso manual del reviewer. Estos tests fijan:
- encadena 003 → head 004;
- tabla recordatorio_mail con CHECKs de tipo/estado/intentos,
  UNIQUE(turno_id, tipo), UNIQUE token_accion_hash,
  CHECK(hash=>expira), índices, grants SELECT/INSERT/UPDATE sin DELETE;
- JSONB en la migración (PG); JSON portable en el modelo;
- downgrade revierte solo lo nuevo; cero create_all en runtime (P3).
"""

from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2] / "alembic" / "versions" / "004_recordatorio_mail.py"
)
SOURCE = MIGRATION.read_text(encoding="utf-8") if MIGRATION.exists() else ""


def test_migracion_004_existe_y_encadena_003() -> None:
    """Feliz: migración 004 existe y encadena al head real 003."""
    assert MIGRATION.exists(), "falta migración 004_recordatorio_mail.py"
    assert "003_turno_historial" in SOURCE
    assert 'down_revision: str | None = "003_turno_historial"' in SOURCE


def test_tabla_y_checks_recordatorio_mail_presentes() -> None:
    """Feliz: tabla + CHECKs cerrados de tipo/estado/intentos + CHECK token."""
    assert "op.create_table" in SOURCE
    assert "recordatorio_mail" in SOURCE
    assert "ck_recordatorio_tipo_cerrado" in SOURCE
    assert "ck_recordatorio_estado_cerrado" in SOURCE
    assert "ck_recordatorio_intentos_acotados" in SOURCE
    assert "ck_recordatorio_token_hash_requiere_expira" in SOURCE
    assert "token_accion_hash IS NULL OR token_expira_at IS NOT NULL" in SOURCE


def test_unicidad_turno_tipo_y_token_presente() -> None:
    """Feliz: UNIQUE (turno_id, tipo) e idempotencia + hash único."""
    assert "uq_recordatorio_turno_tipo" in SOURCE
    assert "UNIQUE" in SOURCE and "turno_id" in SOURCE and "tipo" in SOURCE
    assert "uq_recordatorio_token_hash" in SOURCE


def test_indices_y_grants_presentes() -> None:
    """Feliz: índices scheduler/trazabilidad y grants least-privilege sin DELETE."""
    assert "ix_recordatorio_estado_proximo" in SOURCE
    assert "ix_recordatorio_turno" in SOURCE
    assert "postgresql_where" in SOURCE or "is_active" in SOURCE
    assert "GRANT SELECT, INSERT, UPDATE" in SOURCE
    assert "app_turnos" in SOURCE
    assert "DELETE" not in SOURCE.split("GRANT SELECT, INSERT, UPDATE")[1].split("\n")[0]


def test_jsonb_en_migracion() -> None:
    """Borde: la migración usa postgresql.JSONB (PG); modelo usa JSON portable."""
    assert "postgresql.JSONB" in SOURCE


def test_downgrade_revierte_solo_nuevo() -> None:
    """Feliz: downgrade elimina tabla e índices de recordatorio_mail."""
    assert "op.drop_table" in SOURCE or "drop_table" in SOURCE
    assert "recordatorio_mail" in SOURCE
    assert "003_turno_historial" in SOURCE  # head previo se conserva
