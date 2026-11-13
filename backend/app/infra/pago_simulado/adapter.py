"""Adaptador simulado de pagos C-07 (infra/pago_simulado).

Genera `checkout_url` (pantalla "Checkout simulado") + `checkout_token` de 1
uso/vida corta. Al ejecutar una acción, emite un evento firmado con HMAC-SHA256
sobre `MP_WEBHOOK_SECRET` para entrega al handler del webhook (P10).

El `checkout_token` se almacena en memoria con expiración y se invalida tras
consumo (1 uso, P12).
"""

import hashlib
import hmac
import uuid
from datetime import UTC, datetime, timedelta

from app.domain.pagos.proveedor import ProveedorPago, TipoAccionPago

CHECKOUT_URL_BASE = "http://localhost:5173/checkout-simulado"
TOKEN_TTL_MIN = 10


class PagoSimuladoAdapter(ProveedorPago):
    """Adaptador de pagos en modo simulado (MVP, D14)."""

    def __init__(self, webhook_secret: str) -> None:
        self._webhook_secret = webhook_secret
        self._tokens: dict[str, dict] = {}

    def generar_checkout(self, pago: dict) -> tuple[str, str]:
        checkout_token = f"chk_{uuid.uuid4().hex}"
        expira_at = datetime.now(UTC) + timedelta(minutes=TOKEN_TTL_MIN)
        self._tokens[checkout_token] = {
            "pago_id": str(pago["id"]),
            "consumido": False,
            "expira_at": expira_at,
        }
        checkout_url = f"{CHECKOUT_URL_BASE}?token={checkout_token}"
        return checkout_url, checkout_token

    def ejecutar_accion(
        self, pago_id: object, accion: TipoAccionPago, checkout_token: str,
    ) -> dict:
        token_data = self._tokens.get(checkout_token)
        if token_data is None:
            raise ValueError("checkout_token inválido o inexistente")
        if token_data["consumido"]:
            raise ValueError("checkout_token ya consumido (1 uso, P12)")
        if datetime.now(UTC) > token_data["expira_at"]:
            raise ValueError("checkout_token expirado")
        if str(token_data["pago_id"]) != str(pago_id):
            raise ValueError("checkout_token no pertenece a este pago")

        token_data["consumido"] = True

        estado_map = {
            TipoAccionPago.APROBAR: "aprobado",
            TipoAccionPago.RECHAZAR: "rechazado",
            TipoAccionPago.EXPIRAR: "expirado",
        }
        estado_accion = estado_map[accion]

        payload = (
            f"mp_payment_id=sim_pay_{pago_id}&"
            f"status={estado_accion}&"
            f"timestamp={datetime.now(UTC).isoformat()}"
        )
        firma = hmac.new(
            self._webhook_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return {
            "pago_id": str(pago_id),
            "accion": estado_accion,
            "payload": payload,
            "firma": firma,
            "proveedor": "simulado",
        }
