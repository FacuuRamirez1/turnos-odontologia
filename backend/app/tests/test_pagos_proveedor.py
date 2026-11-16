"""Tests C-07 task 2 — Puerto ProveedorPago + adaptador simulado (RED primero).

Escenarios (U2 feliz / negocio / borde):
- feliz: adaptador simulado genera checkout_url + checkout_token (1 uso, vida corta);
- negocio: modo mercadopago sin credenciales falla en selección de adaptador;
- borde: checkout_token se invalida tras consumo (1 uso).
"""

import uuid
from decimal import Decimal

import pytest

from app.domain.pagos.proveedor import ProveedorPago, TipoAccionPago
from app.infra.pago_simulado.adapter import PagoSimuladoAdapter


def _make_pago() -> dict:
    return {
        "id": uuid.uuid4(),
        "turno_id": uuid.uuid4(),
        "odontologo_id": uuid.uuid4(),
        "monto": 65000,
        "moneda": "ARS",
        "proveedor": "simulado",
        "mp_payment_id": f"sim_pay_{uuid.uuid4()}",
        "estado": "pendiente",
        "idempotency_key": f"idem-{uuid.uuid4().hex[:12]}",
    }


def test_adaptador_simulado_genera_checkout_feliz() -> None:
    """Feliz: adaptador simulado genera checkout_url y checkout_token de 1 uso."""
    adapter = PagoSimuladoAdapter(webhook_secret="secreto-de-test-ficticio")
    pago = _make_pago()
    checkout_url, checkout_token = adapter.generar_checkout(pago)
    assert checkout_url is not None
    assert "checkout" in checkout_url.lower()
    assert checkout_token is not None
    assert isinstance(checkout_token, str)
    assert len(checkout_token) > 0


def test_checkout_token_un_uso_invalido_tras_consumo_borde() -> None:
    """Borde: checkout_token se invalida tras consumo (1 uso, P12)."""
    adapter = PagoSimuladoAdapter(webhook_secret="secreto-de-test-ficticio")
    pago = _make_pago()
    _, token = adapter.generar_checkout(pago)
    # Primer consumo: válido
    evento = adapter.ejecutar_accion(pago["id"], TipoAccionPago.APROBAR, token)
    assert evento is not None
    # Segundo consumo con mismo token: inválido
    with pytest.raises(ValueError, match="token"):
        adapter.ejecutar_accion(pago["id"], TipoAccionPago.APROBAR, token)


def test_adaptador_simulado_firma_evento_con_hmac_feliz() -> None:
    """Feliz: el adaptador simulado firma eventos con HMAC sobre MP_WEBHOOK_SECRET."""
    import hashlib
    import hmac

    adapter = PagoSimuladoAdapter(webhook_secret="secreto-de-test-ficticio")
    pago = _make_pago()
    _, token = adapter.generar_checkout(pago)
    evento = adapter.ejecutar_accion(pago["id"], TipoAccionPago.APROBAR, token)
    firma = evento["firma"]
    payload = evento["payload"]
    esperado = hmac.new(
        b"secreto-de-test-ficticio",
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    assert firma == esperado


def test_checkout_token_expirado_rechazado_triangulate() -> None:
    """Triangulate: checkout_token vencido → error de expiración."""
    from datetime import UTC, datetime, timedelta

    adapter = PagoSimuladoAdapter(webhook_secret="secreto-de-test-ficticio")
    pago = _make_pago()
    _, token = adapter.generar_checkout(pago)
    adapter._tokens[token]["expira_at"] = datetime.now(UTC) - timedelta(minutes=1)
    with pytest.raises(ValueError, match="expirado"):
        adapter.ejecutar_accion(pago["id"], TipoAccionPago.APROBAR, token)


def test_checkout_token_pago_diferente_rechazado_triangulate() -> None:
    """Triangulate: checkout_token de otro pago → error de pertenencia."""
    adapter = PagoSimuladoAdapter(webhook_secret="secreto-de-test-ficticio")
    pago1 = _make_pago()
    pago2 = _make_pago()
    _, token = adapter.generar_checkout(pago1)
    with pytest.raises(ValueError, match="pertenece"):
        adapter.ejecutar_accion(pago2["id"], TipoAccionPago.APROBAR, token)


def test_accion_rechazar_y_expirar_triangulate() -> None:
    """Triangulate: acciones RECHAZAR y EXPIRAR generan eventos firmados."""
    adapter = PagoSimuladoAdapter(webhook_secret="secreto-de-test-ficticio")
    pago = _make_pago()
    _, token = adapter.generar_checkout(pago)

    evento_rechazo = adapter.ejecutar_accion(pago["id"], TipoAccionPago.RECHAZAR, token)
    assert evento_rechazo["accion"] == "rechazado"
    assert "rechazado" in evento_rechazo["payload"]

    _, token2 = adapter.generar_checkout(pago)
    evento_expiracion = adapter.ejecutar_accion(pago["id"], TipoAccionPago.EXPIRAR, token2)
    assert evento_expiracion["accion"] == "expirado"
    assert "expirado" in evento_expiracion["payload"]


def test_proveedor_pago_puerto_define_interfaz_feliz() -> None:
    """Feliz: ProveedorPago es un puerto (interfaz) con los métodos esperados."""
    assert hasattr(ProveedorPago, "generar_checkout")
    assert hasattr(ProveedorPago, "ejecutar_accion")
    assert hasattr(ProveedorPago, "ejecutar_devolucion")
    assert hasattr(ProveedorPago, "consultar_devolucion")
    assert hasattr(TipoAccionPago, "APROBAR")
    assert hasattr(TipoAccionPago, "RECHAZAR")
    assert hasattr(TipoAccionPago, "EXPIRAR")


def _ejecutar_devolucion(adapter: PagoSimuladoAdapter, key: str) -> dict[str, object]:
    return adapter.ejecutar_devolucion(
        idempotency_key=key,
        mp_payment_id="sim_pay_ficticio",
        monto=Decimal("6000.00"),
    )


def test_devolucion_simulada_misma_key_mismo_id_feliz() -> None:
    """Feliz: misma idempotency_key → mismo mp_refund_id sin mover dinero."""
    adapter = PagoSimuladoAdapter(webhook_secret="secreto-de-test-ficticio")

    evento1 = _ejecutar_devolucion(adapter, "dev_pago-ficticio")
    evento2 = _ejecutar_devolucion(adapter, "dev_pago-ficticio")

    refund_id = evento1["mp_refund_id"]
    assert isinstance(refund_id, str)
    assert refund_id.startswith("sim_refund_")
    assert evento2["mp_refund_id"] == refund_id
    assert evento2["payload"] == evento1["payload"]
    assert evento1["status"] == "refunded"
    assert "kind=devolucion" in str(evento1["payload"])

    consulta = adapter.consultar_devolucion("dev_pago-ficticio")
    assert consulta is not None
    assert consulta["mp_refund_id"] == refund_id


def test_consulta_devolucion_inexistente_no_la_crea_borde() -> None:
    """Borde: consultar una key nunca ejecutada → no existe y no se persiste."""
    adapter = PagoSimuladoAdapter(webhook_secret="secreto-de-test-ficticio")

    assert adapter.consultar_devolucion("dev_nunca_ejecutada") is None
    assert adapter.consultar_devolucion("dev_nunca_ejecutada") is None

    _ejecutar_devolucion(adapter, "dev_otra_pago")
    assert adapter.consultar_devolucion("dev_nunca_ejecutada") is None


def test_devolucion_firma_invalida_detectada_negocio() -> None:
    """Error: la firma HMAC del evento de devolución se detecta al verificarla."""
    import hashlib
    import hmac

    adapter = PagoSimuladoAdapter(webhook_secret="secreto-de-test-ficticio")
    evento = _ejecutar_devolucion(adapter, "dev_firma")

    payload = str(evento["payload"])
    esperada = hmac.new(
        b"secreto-de-test-ficticio", payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    assert evento["firma"] == esperada

    otra = hmac.new(
        b"otro-secreto", payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    assert not hmac.compare_digest(str(evento["firma"]), otra)
