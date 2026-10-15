"""Tests C-02 §3.2 + §3.4 — rol least-privilege y previsión P6 (estáticos).

Sin credenciales PG vivas en este entorno, la verificación dinámica
(`UPDATE`/`DELETE` denegados, upgrade/downgrade en dev) queda como paso
manual del reviewer CRÍTICO. Estos tests fijan el contrato estático de 001:
- rol `app_turnos` creado sin `DELETE` en ningún GRANT (P9, RN-AUDIT);
- `REVOKE UPDATE, DELETE` sobre `turno_historial`/`evento_pago` documentados
  para efectivizarse en C-05/C-07;
- previsión P6 de C-05 documentada y ningún stub de turno/pago/mail en 001.
"""

import re
from pathlib import Path

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "001_core_v2off.py"
)
SOURCE = MIGRATION.read_text(encoding="utf-8")


def test_rol_app_creado_sin_delete_en_grants() -> None:
    """3.2: el rol existe y ningún GRANT le da DELETE (P9 fail-closed)."""
    assert "CREATE ROLE app_turnos" in SOURCE
    grants = re.findall(
        r"GRANT\s+([^;\"']+?)\s+ON\s+(\S+)\s+TO\s+(?:app_turnos|\{APP_ROLE\})", SOURCE
    )
    assert grants, "001 debe otorgar GRANTs al rol app_turnos"
    for privilegios, objeto in grants:
        if objeto == "SCHEMA":
            continue
        assert "DELETE" not in privilegios.upper(), f"DELETE otorgado en {objeto}"
        assert "ALL" not in privilegios.upper(), f"GRANT ALL en {objeto}"
    # Los GRANTs de tablas se generan por loop: verificar el cuerpo del loop.
    assert "GRANT SELECT, INSERT, UPDATE ON {tabla} TO {APP_ROLE}" in SOURCE


def test_revokes_append_only_documentados_para_c05_c07() -> None:
    """3.2: los REVOKE sobre tablas append-only futuras están previstos."""
    assert "REVOKE UPDATE, DELETE ON turno_historial FROM app_turnos" in SOURCE
    assert "REVOKE UPDATE, DELETE ON evento_pago FROM app_turnos" in SOURCE


def test_prevision_p6_c05_documentada_sin_stubs() -> None:
    """3.4: P6 de C-05 documentado; cero `create_table` de turno/pago/mail."""
    assert "UNIQUE (odontologo_id" in SOURCE
    assert "EXCLUDE USING gist" in SOURCE
    assert "CHECK (inicio > now())" in SOURCE
    creadas = re.findall(r'op\.create_table\(\s*"([^"]+)"', SOURCE)
    assert set(creadas) == {
        "usuario",
        "odontologo",
        "paciente",
        "lista_espera",
        "notificacion_whatsapp",
    }, f"tablas inesperadas en 001: {sorted(set(creadas))}"
