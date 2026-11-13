"""Tests C-01 §4 — contrato de settings y flags v2 apagados (U2: 3 escenarios)."""

import pytest

from app.core.settings import Settings


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "DATABASE_URL",
        "REDIS_URL",
        "JWT_SECRET",
        "ENVIRONMENT",
        "RECORDATORIO_VENTANA_HS",
        "RESERVA_TTL_MIN",
        "WHATSAPP_ENABLED",
        "ARCA_ENABLED",
        "MAIL_ACTION_TTL_MIN",
        "MAIL_RATE_LIMIT",
        "API_PUBLIC_URL",
        "WORKER_SCHEDULER_TICK_S",
        "PAGO_MODO",
        "MP_ACCESS_TOKEN",
        "MP_PUBLIC_KEY",
        "MP_WEBHOOK_SECRET",
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


def test_env_override_mails_c09_borde(monkeypatch: pytest.MonkeyPatch) -> None:
    """Borde: env vars pisan defaults de C-09."""
    monkeypatch.setenv("MAIL_ACTION_TTL_MIN", "60")
    monkeypatch.setenv("MAIL_RATE_LIMIT", "5")
    monkeypatch.setenv("API_PUBLIC_URL", "https://clinica.example.ar")
    monkeypatch.setenv("WORKER_SCHEDULER_TICK_S", "30")
    settings = Settings()
    assert settings.mail_action_ttl_min == 60
    assert settings.mail_rate_limit == 5
    assert settings.api_public_url == "https://clinica.example.ar"
    assert settings.worker_scheduler_tick_s == 30


def test_env_override_borde(monkeypatch: pytest.MonkeyPatch) -> None:
    """Borde/error: env vars pisan defaults y secrets nunca hardcodeados en repo."""
    monkeypatch.setenv("JWT_SECRET", "secreto-de-test-ficticio")
    monkeypatch.setenv("WHATSAPP_ENABLED", "false")
    settings = Settings()
    assert settings.jwt_secret == "secreto-de-test-ficticio"
    assert settings.whatsapp_enabled is False


def test_pago_modo_default_simulado_feliz() -> None:
    """Feliz: PAGO_MODO default es 'simulado' (D14)."""
    settings = Settings()
    assert settings.pago_modo == "simulado"


def test_pago_modo_mercadopago_feliz(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feliz: PAGO_MODO='mercadopago' se resuelve desde env."""
    monkeypatch.setenv("PAGO_MODO", "mercadopago")
    monkeypatch.setenv("MP_ACCESS_TOKEN", "TEST-ficticio")
    monkeypatch.setenv("MP_PUBLIC_KEY", "TEST-public-ficticio")
    settings = Settings()
    assert settings.pago_modo == "mercadopago"


def test_pago_modo_mercadopago_sin_credenciales_falla_negocio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Negocio P5: modo mercadopago sin MP_ACCESS_TOKEN/MP_PUBLIC_KEY falla."""
    monkeypatch.setenv("PAGO_MODO", "mercadopago")
    with pytest.raises(ValueError, match="MP_ACCESS_TOKEN"):
        Settings()


def test_pago_modo_invalido_falla_negocio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Negocio: PAGO_MODO inválido rechaza el arranque."""
    monkeypatch.setenv("PAGO_MODO", "efectivo")
    with pytest.raises(ValueError, match="PAGO_MODO"):
        Settings()


def test_pago_modo_mercadopago_con_credenciales_feliz(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Triangulate: modo mercadopago con credenciales válidas arranca."""
    monkeypatch.setenv("PAGO_MODO", "mercadopago")
    monkeypatch.setenv("MP_ACCESS_TOKEN", "TEST-ficticio-token")
    monkeypatch.setenv("MP_PUBLIC_KEY", "TEST-public-ficticio-key")
    settings = Settings()
    assert settings.pago_modo == "mercadopago"
    assert settings.mp_access_token == "TEST-ficticio-token"
    assert settings.mp_public_key == "TEST-public-ficticio-key"


def test_mp_webhook_secret_requerido_en_produccion_negocio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Negocio P5: MP_WEBHOOK_SECRET placeholder o vacío en mercadopago falla en producción."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "secreto-real-de-produccion-ficticio")
    monkeypatch.setenv("MP_WEBHOOK_SECRET", "cambiar-en-produccion")
    with pytest.raises(ValueError, match="MP_WEBHOOK_SECRET"):
        Settings()

    monkeypatch.setenv("MP_WEBHOOK_SECRET", "")
    monkeypatch.setenv("PAGO_MODO", "mercadopago")
    monkeypatch.setenv("MP_ACCESS_TOKEN", "TEST-ficticio")
    monkeypatch.setenv("MP_PUBLIC_KEY", "TEST-public")
    with pytest.raises(ValueError, match="MP_WEBHOOK_SECRET"):
        Settings()
