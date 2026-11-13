"""Puerto ProveedorPago C-07 — interfaz de proveedor de pagos.

Seleccionable por `PAGO_MODO=simulado|mercadopago` (default `simulado`).
El adaptador simulado no expone checkout externo: genera `checkout_url`
apuntando a la pantalla "Checkout simulado" y `checkout_token` (1 uso, vida
corta). Al ejecutar una acción, emite un evento firmado con HMAC sobre
`MP_WEBHOOK_SECRET` para entrega al handler del webhook (P10).
"""

from abc import ABC, abstractmethod
from enum import StrEnum


class TipoAccionPago(StrEnum):
    APROBAR = "aprobar"
    RECHAZAR = "rechazar"
    EXPIRAR = "expirar"


class ProveedorPago(ABC):
    """Puerto de proveedor de pagos. Una implementación por modo (PAGO_MODO)."""

    @abstractmethod
    def generar_checkout(self, pago: dict) -> tuple[str, str]:
        """Genera `(checkout_url, checkout_token)` para un pago pendiente.

        El `checkout_token` es de 1 uso y vida corta; se almacena con
        expiración para validación posterior en el sandbox/webhook.
        """

    @abstractmethod
    def ejecutar_accion(
        self, pago_id: object, accion: TipoAccionPago, checkout_token: str,
    ) -> dict:
        """Ejecuta `accion` sobre el pago validando `checkout_token` (1 uso).

        Retorna un dict con `payload` (crudo, para el webhook) y `firma`
        (HMAC-SHA256 sobre `MP_WEBHOOK_SECRET`). El evento es entregado al
        handler `POST /webhooks/mercadopago`, que valida la firma y persiste.
        """
