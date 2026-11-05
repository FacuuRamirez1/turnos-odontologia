"""Tests C-01 §4 — contrato de settings y flags v2 apagados (U2: 3 escenarios)."""

import os

import pytest

from app.core.settings import Settings


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "DATABASE_URL",
        "REDIS_URL",
        "JWT_SECRET",
        "RECORDATORIO_VENTANA_HS",
        "RESERVA_TTL_MIN",
        "WHATSAPP_ENABLED",
        "ARCA_ENABLED",
        "MAIL_ACTION_TTL_MIN",
        "MAIL_RATE_LIMIT",
        "API_PUBLIC_URL",
        "WORKER_SCHEDULER_TICK_S",
    ):
        monkeypatch.delenv(var, raising=False)


def test_flags_v2_apagados_por_defecto() -> None:
    """Feliz: P13 — WHATSAPP_ENABLED y ARCA_ENABLED son false por defecto."""
    settings = Settings()
    assert settings.whatsapp_enabled is False
    assert settings.arca_enabled is False


def test_defaults_resueltos_pineados() -> None:
    """Feliz: RECORDATORIO_VENTANA_HS=24, RESERVA_TTL_MIN=15."""
    settings = Settings()
    assert settings.recordatorio_ventana_hs == 24
    assert settings.reserva_ttl_min == 15


def test_settings_mails_c09_defaults() -> None:
    """Feliz: nuevos settings C-09 con defaults del design."""
    settings = Settings()
    assert settings.mail_action_ttl_min == 2880
    assert settings.mail_rate_limit == 30
    assert settings.api_public_url == "http://localhost:8000"
    assert settings.worker_scheduler_tick_s == 60


def test_env_override_mails_c09_borde() -> None:
    """Borde: env vars pisan defaults de C-09."""
    os.environ["MAIL_ACTION_TTL_MIN"] = "60"
    os.environ["MAIL_RATE_LIMIT"] = "5"
    os.environ["API_PUBLIC_URL"] = "https://clinica.example.ar"
    os.environ["WORKER_SCHEDULER_TICK_S"] = "30"
    settings = Settings()
    assert settings.mail_action_ttl_min == 60
    assert settings.mail_rate_limit == 5
    assert settings.api_public_url == "https://clinica.example.ar"
    assert settings.worker_scheduler_tick_s == 30


def test_env_override_borde() -> None:
    """Borde/error: env vars pisan defaults y secrets nunca hardcodeados en repo."""
    os.environ["JWT_SECRET"] = "secreto-de-test-ficticio"
    os.environ["WHATSAPP_ENABLED"] = "false"
    settings = Settings()
    assert settings.jwt_secret == "secreto-de-test-ficticio"
    assert settings.whatsapp_enabled is False
