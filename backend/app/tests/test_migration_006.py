"""Tests C-08 task 1.2 — contrato de la migración 006 (RED primero).

Sin PG vivo en este entorno (Docker no arranca), el contrato se fija sobre el
fuente de la migración y, además, se ejecuta de punta a punta con el módulo
cargado por Alembic (cadena de revisiones real, sin DB):
- head único `006_devolucion_comprobante` encadenado a `005_pago_evento_pago`;
- downgrade restaura el CHECK original de `evento_pago` y aborta si existen
  eventos `devolucion_rechazada` (no perder audit trail, P9);
- cero `create_all` en runtime (P3).
"""

import importlib.util
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).resolve().parents[2]
MIGRATION = BACKEND / "alembic" / "versions" / "006_devolucion_comprobante.py"
SOURCE = MIGRATION.read_text(encoding="utf-8") if MIGRATION.exists() else ""


def _script() -> ScriptDirectory:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_head_unico_es_007_y_encadena_006() -> None:
    """Feliz: `alembic current` tras upgrade = 007 (único head) sobre 006."""
    script = _script()
    assert script.get_heads() == ["007_paciente_campos_cifrados"]
    rev = script.get_revision("007_paciente_campos_cifrados")
    assert rev is not None
    assert rev.down_revision == "006_devolucion_comprobante"


def test_downgrade_restaura_check_original_de_evento_pago() -> None:
    """Feliz: el downgrade recrea el CHECK con los 8 tipos de C-07 (sin el nuevo)."""
    spec = importlib.util.spec_from_file_location("mig006", MIGRATION)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    antes = [t.strip().strip("'") for t in mod.TIPOS_EVENTO_ANTES.split(",")]
    despues = [t.strip().strip("'") for t in mod.TIPOS_EVENTO_DESPUES.split(",")]
    assert len(antes) == 8 and "devolucion_rechazada" not in antes
    assert despues == sorted(despues, key=despues.index) and len(despues) == 9
    assert set(despues) - set(antes) == {"devolucion_rechazada"}
    down = SOURCE.split("def downgrade", 1)[1]
    assert "create_check_constraint" in down and "TIPOS_EVENTO_ANTES" in down
    assert "TIPOS_EVENTO_DESPUES" not in down


def test_downgrade_aborta_si_hay_eventos_devolucion_rechazada() -> None:
    """Error de negocio: no se pierde el audit trail al bajar la versión."""
    down = SOURCE.split("def downgrade", 1)[1]
    assert "SELECT count(*) FROM evento_pago WHERE tipo_evento = 'devolucion_rechazada'" in down
    assert "RuntimeError" in down
    # el guard corre ANTES de tocar el CHECK o dropear tablas
    assert down.index("RuntimeError") < down.index("drop_constraint")
    assert down.index("RuntimeError") < down.index("drop_table")


def test_upgrade_agrega_devolucion_rechazada_al_check() -> None:
    """Borde: el CHECK nuevo acepta devolucion_rechazada y conserva los 8 tipos previos."""
    up = SOURCE.split("def upgrade", 1)[1].split("def downgrade", 1)[0]
    assert "drop_constraint" in up and "ck_evento_pago_tipo_cerrado" in up
    assert "devolucion_rechazada" in up
    for tipo in ("creado", "webhook_recibido", "aprobado", "rechazado",
                 "devolucion_solicitada", "devolucion_aprobada",
                 "devolucion_ejecutada", "conciliado"):
        assert tipo in SOURCE


def test_sin_create_all_en_runtime_p3() -> None:
    """P3: la migración usa solo operaciones Alembic."""
    assert ".create_all(" not in SOURCE
    assert "op.create_table" in SOURCE


def test_tablas_devolucion_comprobante_con_checks_de_dominio() -> None:
    """D3/D6: CHECK porcentaje IN (100,60), monto > 0, UNIQUE totales y parciales."""
    assert '"devolucion"' in SOURCE and '"comprobante"' in SOURCE
    assert "porcentaje IN (100, 60)" in SOURCE
    assert "monto > 0" in SOURCE
    for nombre in ("uq_devolucion_pago", "uq_devolucion_idempotency_key",
                   "uq_devolucion_mp_refund_id",
                   "ck_devolucion_ejecutada_con_refund"):
        assert nombre in SOURCE
    # unicidad parcial de comprobantes (D6)
    assert "uq_comprobante_pago_concepto_pago" in SOURCE
    assert "uq_comprobante_devolucion" in SOURCE
    assert "postgresql_where" in SOURCE
    assert "comprobante_numero_seq" in SOURCE


def test_triggers_transicion_y_monto_presentes() -> None:
    """D3: trigger de transición de estado y de monto <= pago.monto."""
    assert "devolucion_guard_transicion" in SOURCE
    assert "devolucion_guard_monto" in SOURCE
    assert "BEFORE UPDATE" in SOURCE and "BEFORE INSERT" in SOURCE
    # downgrade los elimina
    down = SOURCE.split("def downgrade", 1)[1]
    assert "DROP TRIGGER" in down and "DROP FUNCTION" in down


def test_grants_least_privilege_y_revoke_comprobante_p9() -> None:
    """P9: comprobante inmutable; devolucion sin DELETE."""
    assert "GRANT SELECT, INSERT, UPDATE ON devolucion" in SOURCE
    assert "GRANT SELECT, INSERT ON comprobante" in SOURCE
    assert "REVOKE UPDATE, DELETE ON comprobante" in SOURCE
    grants = [ln for ln in SOURCE.splitlines() if "GRANT" in ln and "comprobante" in ln]
    assert grants and all("UPDATE" not in ln.split("GRANT")[1] for ln in grants
                          if "REVOKE" not in ln)
