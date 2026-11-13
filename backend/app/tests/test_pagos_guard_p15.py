"""Tests C-07 task 8 — Guard de arranque/CI P15 (RED → GREEN → TRIANGULATE)."""

from pathlib import Path

import pytest

from app.main import verificar_guard_produccion


def test_guard_dev_simulado_permitido_feliz(monkeypatch: pytest.MonkeyPatch) -> None:
    """Feliz: en dev con PAGO_MODO=simulado el arranque pasa."""
    monkeypatch.setenv("ENVIRONMENT", "dev")
    monkeypatch.setenv("PAGO_MODO", "simulado")
    verificar_guard_produccion()


def test_guard_produccion_simulado_falla_negocio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Error de negocio P15: ENVIRONMENT=production + PAGO_MODO=simulado falla."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "secreto-real-de-produccion-ficticio")
    monkeypatch.setenv("MP_WEBHOOK_SECRET", "webhook-real-de-produccion-ficticio")
    monkeypatch.setenv("PAGO_MODO", "simulado")
    with pytest.raises(ValueError, match="P15"):
        verificar_guard_produccion()


def test_guard_produccion_mercadopago_permitido_borde(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Borde: ENVIRONMENT=production + PAGO_MODO=mercadopago pasa y CI valida P15."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "secreto-real-de-produccion-ficticio")
    monkeypatch.setenv("MP_WEBHOOK_SECRET", "webhook-real-de-produccion-ficticio")
    monkeypatch.setenv("PAGO_MODO", "mercadopago")
    monkeypatch.setenv("MP_ACCESS_TOKEN", "TEST-ficticio-token")
    monkeypatch.setenv("MP_PUBLIC_KEY", "TEST-public-ficticio")
    verificar_guard_produccion()

    ci_path = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "ci.yml"
    ci_src = ci_path.read_text(encoding="utf-8")
    assert "PAGO_MODO" in ci_src
    assert "verificar_guard_produccion" in ci_src
