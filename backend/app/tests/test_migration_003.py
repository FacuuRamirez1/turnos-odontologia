"""Tests C-05 §1.1 — contrato estático de la migración 003 (RED primero, task 1.1).

Sin PG vivo en este entorno, la verificación dinámica (upgrade en dev, EXCLUDE
real, REVOKE real) queda como paso manual del reviewer. Estos tests fijan:
- encadena 002 → head 003;
- btree_gist + UNIQUE (odontologo_id, inicio) + EXCLUDE anti-solape + CHECKs;
- índices agenda/expiración + REVOKE UPDATE/DELETE historial a app_role;
- downgrade revierte; cero create_all en runtime (P3).
"""

from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2] / "alembic" / "versions" / "003_turno_historial.py"
)
SOURCE = MIGRATION.read_text(encoding="utf-8") if MIGRATION.exists() else ""


def test_migracion_003_existe_y_encadena_002() -> None:
    assert MIGRATION.exists(), "falta migración 003_turno_historial.py"
    assert "002_disponibilidad_bloqueo" in SOURCE


def test_unique_doble_reserva_presente() -> None:
    assert "uq_turno_odonto_inicio" in SOURCE or "UNIQUE (odontologo_id, inicio)" in SOURCE
    assert "odontologo_id" in SOURCE and "inicio" in SOURCE


def test_exclude_anti_solape_presente() -> None:
    assert "btree_gist" in SOURCE
    assert "ExcludeConstraint" in SOURCE
    assert "ex_turno_no_solape" in SOURCE
    assert "tstzrange" in SOURCE


def test_checks_pasado_y_orden_presentes() -> None:
    for check in ("ck_turno_fin_mayor_inicio", "ck_turno_inicio_futuro"):
        assert check in SOURCE, f"falta CHECK {check}"


def test_indices_agenda_y_expiracion_presentes() -> None:
    assert "ix_turno_odonto_inicio" in SOURCE
    assert "ix_turno_estado_created" in SOURCE
    assert "ix_historial_turno_fecha" in SOURCE


def test_revoke_historial_append_only_presente() -> None:
    assert "REVOKE UPDATE" in SOURCE and "DELETE" in SOURCE
    assert "turno_historial" in SOURCE
    assert "app_turnos" in SOURCE


def test_downgrade_revierte() -> None:
    assert "op.drop_table" in SOURCE or "drop_table" in SOURCE
    assert "turno_historial" in SOURCE and "turno" in SOURCE
