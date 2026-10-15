"""Tests C-01 §4 — contrato .env.example completo y sin secretos (U2: 3 escenarios)."""

from pathlib import Path

REQUIRED_VARS = [
    "DATABASE_URL",
    "REDIS_URL",
    "JWT_SECRET",
    "MP_ACCESS_TOKEN",
    "MP_WEBHOOK_SECRET",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASS",
    "MAIL_FROM",
    "RECORDATORIO_VENTANA_HS",
    "RESERVA_TTL_MIN",
    "FRONTEND_URL",
    "WHATSAPP_ENABLED",
    "ARCA_ENABLED",
]

PINNED = {
    "RECORDATORIO_VENTANA_HS": "24",
    "RESERVA_TTL_MIN": "15",
    "WHATSAPP_ENABLED": "false",
    "ARCA_ENABLED": "false",
}


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


def _parse_env_example(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def test_env_example_documenta_todo_feliz() -> None:
    """Feliz: .env.example raiz documenta las 15 vars del contrato 08 §4."""
    values = _parse_env_example(_root() / ".env.example")
    missing = [var for var in REQUIRED_VARS if var not in values]
    assert missing == []


def test_defaults_pineados_borde() -> None:
    """Borde: defaults resueltos pineados (24/15/false/false)."""
    values = _parse_env_example(_root() / ".env.example")
    for key, expected in PINNED.items():
        assert values[key] == expected, f"{key}={values.get(key)} != {expected}"


def test_sin_secretos_reales_error() -> None:
    """Error de negocio P5/P11: nada real — placeholders ficticios, nada hardcodeado."""
    text = (_root() / ".env.example").read_text(encoding="utf-8")
    assert "cambiar-en-produccion" in text or "CHANGEME" in text
    for token in ("sk_live", "AKIA", "xoxb-", "ghp_"):
        assert token not in text
