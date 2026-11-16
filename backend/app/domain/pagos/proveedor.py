"""Puerto ProveedorPago C-07 — interfaz de proveedor de pagos.

Seleccionable por `PAGO_MODO=simulado|mercadopago` (default `simulado`).
El adaptador simulado no expone checkout externo: genera `checkout_url`
apuntando a la pantalla "Checkout simulado" y `checkout_token` (1 uso, vida
corta). Al ejecutar una acción, emite un evento firmado con HMAC sobre
`MP_WEBHOOK_SECRET` para entrega al handler del webhook (P10).
"""

from abc import ABC, abstractmethod
from decimal import Decimal
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

    @abstractmethod
    def ejecutar_devolucion(
        self, *, idempotency_key: str, mp_payment_id: str, monto: Decimal,
    ) -> dict[str, object]:
        """Ejecuta (o recupera) la devolución de una `idempotency_key` (P4).

        Retorna `mp_refund_id`, `status`, `payload` crudo y `firma` HMAC para
        entrega al handler del webhook. Reintentar con la misma key devuelve
        el mismo `mp_refund_id` sin mover dinero dos veces.
        """

    @abstractmethod
    def consultar_devolucion(self, idempotency_key: str) -> dict[str, object] | None:
        """Consulta una devolución ejecutada; `None` si la key nunca se ejecutó.

        Nunca crea la devolución: es solo lectura (borde de idempotencia).
        """
