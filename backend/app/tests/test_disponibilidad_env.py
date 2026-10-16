"""Tests C-04 §6.1 — contrato env ANTICIPACION_MIN_HS + TIMEZONE (P5).

- feliz: defaults presentes (24, zona Córdoba) en Settings y .env.example;
- negocio: override por env;
- borde: sin hardcode fuera de Settings/defaults (P5).
"""

from pathlib import Path

from app.core.settings import Settings


def _parse(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def test_defaults_settings_feliz() -> None:
    s = Settings()
    assert s.anticipacion_min_hs == 24
    assert s.timezone == "America/Argentina/Cordoba"


def test_env_example_documenta_nuevas_vars_feliz() -> None:
    raiz = Path(__file__).resolve().parents[3]
    for env in (raiz / ".env.example", raiz / "backend" / ".env.example"):
        values = _parse(env)
        assert values.get("ANTICIPACION_MIN_HS") == "24", str(env)
        assert "TIMEZONE" in values, str(env)


def test_override_por_env_negocio(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ANTICIPACION_MIN_HS", "48")
    monkeypatch.setenv("TIMEZONE", "America/Argentina/Mendoza")
    s = Settings()
    assert s.anticipacion_min_hs == 48
    assert s.timezone == "America/Argentina/Mendoza"
