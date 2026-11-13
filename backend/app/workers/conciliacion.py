"""Worker C-07 task 7 — Job diario de conciliación interna (D14 §6).

En `PAGO_MODO=simulado` compara `pago.estado` contra el estado reportado en
los `evento_pago` internos (verificación de consistencia interna, no contra
API externa de MercadoPago). Ante discrepancias persiste `evento_pago`
(`tipo_evento='conciliado'`, actor `'sistema'`) y devuelve alertas para bandeja.
"""

from sqlalchemy.orm import Session

from app.infra.db.models.pago import EventoPago, Pago

_ESTADOS_APROBADOS = ("approved", "aprobado", "aprobar", "webhook_recibido")
_ESTADOS_RECHAZADOS = (
    "rejected",
    "rechazado",
    "rechazar",
    "expired",
    "expirado",
    "expirar",
)


def _estado_esperado_desde_eventos(eventos: list[EventoPago]) -> str | None:
    """Infiere el estado esperado del pago según su secuencia de eventos."""
    estado_esperado: str | None = None
    for evento in eventos:
        tipo = str(evento.tipo_evento)
        if tipo == "aprobado":
            estado_esperado = "aprobado"
        elif tipo == "rechazado":
            estado_esperado = "rechazado"
        elif tipo == "webhook_recibido":
            payload = evento.payload_json if isinstance(evento.payload_json, dict) else {}
            status_val = str(payload.get("status", "")).lower()
            if status_val in _ESTADOS_APROBADOS:
                estado_esperado = "aprobado"
            elif status_val in _ESTADOS_RECHAZADOS:
                estado_esperado = "rechazado"
    return estado_esperado


def conciliar_pagos(session: Session) -> list[dict[str, object]]:
    """Compara cada pago activo con sus eventos y reporta discrepancias."""
    pagos = session.query(Pago).filter(Pago.is_active.is_(True)).all()
    alertas: list[dict[str, object]] = []

    for pago in pagos:
        eventos = (
            session.query(EventoPago)
            .filter(EventoPago.pago_id == pago.id)
            .order_by(EventoPago.created_at)
            .all()
        )
        if not eventos:
            continue
        if any(str(ev.tipo_evento) == "conciliado" for ev in eventos):
            continue

        estado_esperado = _estado_esperado_desde_eventos(eventos)
        if estado_esperado is None or str(pago.estado) == estado_esperado:
            continue

        alerta: dict[str, object] = {
            "pago_id": str(pago.id),
            "turno_id": str(pago.turno_id),
            "estado_pago": str(pago.estado),
            "estado_esperado": estado_esperado,
            "discrepancia": True,
        }
        session.add(
            EventoPago(
                pago_id=pago.id,
                tipo_evento="conciliado",
                payload_json={
                    "estado_pago": str(pago.estado),
                    "estado_esperado": estado_esperado,
                    "discrepancia": True,
                },
                actor="sistema",
            )
        )
        alertas.append(alerta)

    if alertas:
        session.commit()

    return alertas
