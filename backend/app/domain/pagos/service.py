"""Servicio de pagos C-07 — selección de proveedor por PAGO_MODO.

Provee `get_proveedor_pago()` que retorna la implementación de `ProveedorPago`
según `settings.pago_modo`:
- `simulado` → `PagoSimuladoAdapter` (infra/pago_simulado)
- `mercadopago` → pendiente (v2, no construido en el MVP, P13)

Usa un patrón de lazy singleton para compartir el store de `checkout_token`
entre `POST /reservas` (generar_checkout) y `POST /pagos/{pago_id}/simular`
(ejecutar_accion).
"""

from app.core.settings import get_settings
from app.domain.pagos.proveedor import ProveedorPago
from app.infra.pago_simulado.adapter import PagoSimuladoAdapter

MARCA_SIMULADO = "(simulado)"
LEYENDA_COMPROBANTE_SIMULADO = "SIMULADO — sin valor fiscal ni movimiento de dinero"

_proveedor_pago: ProveedorPago | None = None


def marca_pago_actual() -> str:
    """Devuelve '(simulado)' en PAGO_MODO=simulado; '' en producción/MP (D14)."""
    return MARCA_SIMULADO if get_settings().pago_modo == "simulado" else ""


def leyenda_comprobante_actual() -> str:
    """Devuelve la leyenda de comprobante simulado cuando aplica (D14)."""
    if get_settings().pago_modo == "simulado":
        return LEYENDA_COMPROBANTE_SIMULADO
    return ""


def get_proveedor_pago() -> ProveedorPago:
    """Devuelve el adaptador de pago activo según `PAGO_MODO` (lazy singleton)."""
    global _proveedor_pago
    if _proveedor_pago is None:
        settings = get_settings()
        if settings.pago_modo == "simulado":
            _proveedor_pago = PagoSimuladoAdapter(
                webhook_secret=settings.mp_webhook_secret
            )
        elif settings.pago_modo == "mercadopago":
            raise NotImplementedError(
                "PAGO_MODO=mercadopago no construido en v1 (P13/D14)."
            )
        else:
            raise ValueError(f"PAGO_MODO desconocido: {settings.pago_modo}")
    return _proveedor_pago


def reset_proveedor_pago() -> None:
    """Reinicia el singleton (seam solo para tests)."""
    global _proveedor_pago
    _proveedor_pago = None
