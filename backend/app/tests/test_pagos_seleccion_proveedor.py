"""Tests C-07 task 2.1 — selección de proveedor de pagos por PAGO_MODO (RED primero).

Escenarios:
- feliz: PAGO_MODO=simulado → PagoSimuladoAdapter sin credenciales MP;
- negocio: PAGO_MODO=mercadopago sin credenciales → error de configuración;
- borde: PAGO_MODO inválido → error.
"""

import pytest

from app.core.settings import get_settings
from app.domain.pagos.proveedor import ProveedorPago
from app.domain.pagos.service import get_proveedor_pago, reset_proveedor_pago
from app.infra.pago_simulado.adapter import PagoSimuladoAdapter


def test_proveedor_simulado_por_defecto_sin_credenciales_mp_feliz(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Feliz: PAGO_MODO=simulado (default) no requiere credenciales MP."""
    monkeypatch.setenv("PAGO_MODO", "simulado")
    monkeypatch.delenv("MP_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("MP_PUBLIC_KEY", raising=False)
    settings = get_settings()
    assert settings.pago_modo == "simulado"
    assert settings.mp_access_token == ""
    assert settings.mp_public_key == ""


def test_proveedor_mercadopago_requiere_credenciales_negocio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Negocio: PAGO_MODO=mercadopago sin MP_ACCESS_TOKEN falla."""
    monkeypatch.setenv("PAGO_MODO", "mercadopago")
    monkeypatch.delenv("MP_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("MP_PUBLIC_KEY", raising=False)
    with pytest.raises(ValueError, match="MP_ACCESS_TOKEN"):
        get_settings()


def test_seleccion_proveedor_por_pago_modo_borde(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Borde: PAGO_MODO inválido rechaza el arranque."""
    monkeypatch.setenv("PAGO_MODO", "invalido")
    with pytest.raises(ValueError, match="PAGO_MODO"):
        get_settings()


def test_get_proveedor_pago_retorna_simulado_feliz(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Feliz: get_proveedor_pago() retorna PagoSimuladoAdapter en modo simulado."""
    monkeypatch.setenv("PAGO_MODO", "simulado")
    reset_proveedor_pago()
    proveedor = get_proveedor_pago()
    assert isinstance(proveedor, ProveedorPago)
    assert isinstance(proveedor, PagoSimuladoAdapter)
    reset_proveedor_pago()


def test_get_proveedor_pago_mercadopago_no_construido_negocio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Negocio P13: get_proveedor_pago() con mercadopago lanza NotImplementedError."""
    monkeypatch.setenv("PAGO_MODO", "mercadopago")
    monkeypatch.setenv("MP_ACCESS_TOKEN", "TEST-ficticio")
    monkeypatch.setenv("MP_PUBLIC_KEY", "TEST-public")
    reset_proveedor_pago()
    with pytest.raises(NotImplementedError, match="no construido"):
        get_proveedor_pago()
    reset_proveedor_pago()
