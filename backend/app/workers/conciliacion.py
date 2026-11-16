"""Worker C-07 task 7 / C-08 task 7.2 — conciliación interna (D14 §6, D9).

En `PAGO_MODO=simulado` compara `pago.estado` contra el estado reportado en
los `evento_pago` internos (verificación de consistencia interna, no contra
API externa de MercadoPago). Ante discrepancias persiste `evento_pago`
(`tipo_evento='conciliado'`, actor `'sistema'`) y devuelve alertas para bandeja.

C-08 D9 incorpora los reembolsos:
- `devolucion_ejecutada` en los eventos espera `reembolsado_total|parcial`
  según el payload (`porcentaje`/`monto`);
- un pago `aprobado` de turno `cancelado`/`no_show` sin devolución (cotización
  0 %) es estado esperado, no discrepancia;
- `conciliar_devoluciones` verifica cada devolución `ejecutada`: pago
  `reembolsado_*` y turno `devuelto`, o `evento_pago(conciliado)` con
  `payload={tipo:"devolucion", detalle}`.
"""

from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from app.infra.db.models import Devolucion, Turno
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
_ESTADOS_REEMBOLSADOS = ("reembolsado_parcial", "reembolsado_total")
_ESTADOS_SIN_DEVOLUCION = ("cancelado", "no_show")


def _payload(evento: EventoPago) -> dict[str, object]:
    """Payload JSON del evento, defensivo ante NULL/no-dict."""
    return evento.payload_json if isinstance(evento.payload_json, dict) else {}


def _es_alerta_devolucion(evento: EventoPago) -> bool:
    """Distingue una alerta de devolución de una discrepancia de pago."""
    return str(_payload(evento).get("tipo", "")) == "devolucion"


def _estado_reembolso(payload: dict[str, object], pago: Pago | None) -> str:
    """`reembolsado_total|parcial` según `porcentaje` o `monto` del payload (D9)."""
    porcentaje = payload.get("porcentaje")
    if porcentaje is not None:
        try:
            return (
                "reembolsado_total"
                if int(str(porcentaje)) >= 100
                else "reembolsado_parcial"
            )
        except (TypeError, ValueError):
            pass
    monto = payload.get("monto")
    if monto is not None and pago is not None:
        try:
            total = Decimal(str(monto)) >= Decimal(str(pago.monto))
            return "reembolsado_total" if total else "reembolsado_parcial"
        except (InvalidOperation, ValueError):
            pass
    return "reembolsado_parcial"


def _estado_esperado_desde_eventos(
    eventos: list[EventoPago], pago: Pago | None = None
) -> str | None:
    """Infiere el estado esperado del pago según su secuencia de eventos."""
    estado_esperado: str | None = None
    for evento in eventos:
        tipo = str(evento.tipo_evento)
        payload = _payload(evento)
        if tipo == "aprobado":
            estado_esperado = "aprobado"
        elif tipo == "rechazado":
            estado_esperado = "rechazado"
        elif tipo == "devolucion_ejecutada":
            estado_esperado = _estado_reembolso(payload, pago)
        elif tipo == "webhook_recibido":
            status_val = str(payload.get("status", "")).lower()
            if status_val in _ESTADOS_APROBADOS:
                estado_esperado = "aprobado"
            elif status_val in _ESTADOS_RECHAZADOS:
                estado_esperado = "rechazado"
    return estado_esperado


def _es_cero_esperado(session: Session, pago: Pago) -> bool:
    """Cotización 0 %: aprobado + turno cancelado/no_show sin devolución (D9)."""
    if str(pago.estado) != "aprobado":
        return False
    turno = session.get(Turno, pago.turno_id)
    if turno is None or str(turno.estado) not in _ESTADOS_SIN_DEVOLUCION:
        return False
    devolucion = (
        session.query(Devolucion)
        .filter(
            Devolucion.pago_id == pago.id,
            Devolucion.is_active.is_(True),
        )
        .first()
    )
    return devolucion is None


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
        ya_conciliado_pago = any(
            str(ev.tipo_evento) == "conciliado"
            and not _es_alerta_devolucion(ev)
            for ev in eventos
        )
        if ya_conciliado_pago:
            continue

        estado_esperado = _estado_esperado_desde_eventos(eventos, pago)
        if estado_esperado is None or str(pago.estado) == estado_esperado:
            continue
        if _es_cero_esperado(session, pago):
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


def _ya_alertada_devolucion(
    session: Session, pago_id: object, devolucion_id: object,
) -> bool:
    """Idempotencia: no duplica la alerta de la misma devolución en corridas."""
    eventos = (
        session.query(EventoPago).filter(EventoPago.pago_id == pago_id).all()
    )
    for evento in eventos:
        if str(evento.tipo_evento) != "conciliado":
            continue
        payload = _payload(evento)
        if (
            str(payload.get("tipo", "")) == "devolucion"
            and str(payload.get("devolucion_id", "")) == str(devolucion_id)
            and payload.get("discrepancia") is True
        ):
            return True
    return False


def conciliar_devoluciones(session: Session) -> list[dict[str, object]]:
    """Verifica devoluciones `ejecutada`: pago reembolsado y turno `devuelto` (D9)."""
    devoluciones = (
        session.query(Devolucion)
        .filter(
            Devolucion.is_active.is_(True),
            Devolucion.estado == "ejecutada",
        )
        .all()
    )
    alertas: list[dict[str, object]] = []

    for devolucion in devoluciones:
        pago = session.get(Pago, devolucion.pago_id)
        turno = session.get(Turno, devolucion.turno_id)
        if pago is None or turno is None:
            continue

        detalle: str | None = None
        if str(pago.estado) not in _ESTADOS_REEMBOLSADOS:
            detalle = "pago_no_reembolsado"
        elif str(turno.estado) != "devuelto":
            detalle = "turno_no_devuelto"
        if detalle is None:
            continue
        if _ya_alertada_devolucion(session, pago.id, devolucion.id):
            continue

        payload: dict[str, object] = {
            "tipo": "devolucion",
            "detalle": detalle,
            "devolucion_id": str(devolucion.id),
            "pago_id": str(pago.id),
            "turno_id": str(turno.id),
            "estado_pago": str(pago.estado),
            "estado_turno": str(turno.estado),
            "discrepancia": True,
        }
        session.add(
            EventoPago(
                pago_id=pago.id,
                tipo_evento="conciliado",
                payload_json=payload,
                actor="sistema",
            )
        )
        alertas.append(
            {
                "tipo": "devolucion",
                "detalle": detalle,
                "devolucion_id": str(devolucion.id),
                "pago_id": str(pago.id),
                "turno_id": str(turno.id),
                "estado_pago": str(pago.estado),
                "estado_turno": str(turno.estado),
                "discrepancia": True,
            }
        )

    if alertas:
        session.commit()

    return alertas
