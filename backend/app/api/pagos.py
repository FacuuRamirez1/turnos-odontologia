"""API de pagos C-07 — sandbox simulado + webhook MercadoPago (P10, P12, P15).

- `GET /pagos/{pago_id}`: consulta staff con RBAC (`require_role`) y marca
  `"(simulado)"` cuando `PAGO_MODO=simulado`.
- `POST /pagos/{pago_id}/simular`: sandbox solo en `PAGO_MODO=simulado`,
  exige `checkout_token` de 1 uso + rate-limit. El adaptador emite el evento
  firmado entregado al handler del webhook.
- `POST /webhooks/mercadopago`: mismo handler en ambos modos; valida firma
  HMAC (`MP_WEBHOOK_SECRET`), persiste `evento_pago(webhook_recibido)` con
  payload crudo, idempotencia por `mp_payment_id`, transita
  `creado→confirmado` (aprobado) o `creado→cancelado` (rechazado/expirado)
  con actor `sistema`.
"""

import hashlib
import hmac
import json as _json
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.security.dependencies import Identity, require_role
from app.core.settings import get_settings
from app.domain.comprobantes.service import emitir_recibo_devolucion, emitir_recibo_pago
from app.domain.notificaciones.outbox import encolar_confirmacion
from app.domain.pagos.proveedor import TipoAccionPago
from app.domain.pagos.repositories import EventoPagoRepository
from app.domain.pagos.service import (
    get_proveedor_pago,
    leyenda_comprobante_actual,
    marca_pago_actual,
)
from app.domain.turnos.estados import transition
from app.infra.db.models import Devolucion, Turno, TurnoHistorial
from app.infra.db.models.pago import EventoPago, Pago
from app.infra.db.session import get_db
from app.infra.redis.rate_limit import LoginRateLimiter, build_rate_limiter

router = APIRouter(tags=["pagos"])

STAFF_PAGOS = require_role("odontologo", "recepcionista", "admin")

_sandbox_limiter: LoginRateLimiter | None = None


def get_sandbox_limiter() -> LoginRateLimiter:
    global _sandbox_limiter
    if _sandbox_limiter is None:
        _sandbox_limiter = build_rate_limiter(
            get_settings().redis_url, limit=10, window_seconds=60
        )
    return _sandbox_limiter


def reset_sandbox_limiter(
    limit: int = 10, window_seconds: int = 60,
) -> None:
    global _sandbox_limiter
    _sandbox_limiter = LoginRateLimiter(
        client=None, limit=limit, window_seconds=window_seconds
    )


class SimularBody(BaseModel):
    """Cuerpo del sandbox — P2 extra='forbid'."""

    model_config = ConfigDict(extra="forbid")

    accion: str = Field(pattern="^(aprobar|rechazar|expirar)$")


class WebhookBody(BaseModel):
    """Cuerpo del webhook MP — P2 extra='forbid'."""

    model_config = ConfigDict(extra="forbid")

    mp_payment_id: str
    status: str


class PagoOut(BaseModel):
    """Detalle de pago con marca simulada — P2 extra='forbid'."""

    model_config = ConfigDict(extra="forbid")

    pago_id: str
    turno_id: str
    estado: str
    monto: float
    moneda: str
    proveedor: str
    marca: str
    leyenda_comprobante: str


def _simulado_requerido() -> None:
    """P12/P15: el sandbox solo existe en PAGO_MODO=simulado."""
    if get_settings().pago_modo != "simulado":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "sandbox no disponible")


def _extraer_estado_mp(status_str: str) -> str:
    """Mapea estados MP/acción a estados de pago interno."""
    mapeo = {
        "approved": "aprobado",
        "rejected": "rechazado",
        "expired": "expirado",
        "aprobado": "aprobado",
        "rechazado": "rechazado",
        "expirado": "expirado",
        "aprobar": "aprobado",
        "rechazar": "rechazado",
        "expirar": "expirado",
    }
    return mapeo.get(status_str, status_str)


def _validar_firma_webhook(payload: str, firma: str, secret: str) -> bool:
    """Valida HMAC-SHA256 del payload contra MP_WEBHOOK_SECRET."""
    esperado = hmac.new(
        secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(esperado, firma)


def _procesar_webhook_pago(
    db: Session,
    mp_payment_id: str,
    estado_interno: str,
    payload_crudo: str,
    actor: str = "sistema",
    kind: str = "pago",
) -> dict[str, object]:
    """Procesa un webhook de pago: idempotencia, evento, transición turno.

    Retorna un dict con `pago`, `turno`, `transicionado`.
    """
    pago = db.query(Pago).filter(Pago.mp_payment_id == mp_payment_id).first()
    if pago is None:
        return {"error": "pago_no_encontrado", "mp_payment_id": mp_payment_id}

    previos = (
        db.query(EventoPago)
        .filter(
            EventoPago.pago_id == pago.id,
            EventoPago.tipo_evento == "webhook_recibido",
        )
        .all()
    )
    for previo in previos:
        datos = previo.payload_json or {}
        if (
            str(datos.get("kind", "pago")) == "pago"
            and str(datos.get("mp_payment_id", "")) == str(mp_payment_id)
        ):
            return {
                "pago": pago,
                "turno": None,
                "transicionado": False,
                "idempotente": True,
            }

    evento_repo = EventoPagoRepository(db)
    evento_repo.add_evento(
        pago_id=pago.id,
        tipo_evento="webhook_recibido",
        payload_json={
            "kind": kind,
            "mp_payment_id": mp_payment_id,
            "status": estado_interno,
            "payload_crudo": payload_crudo,
        },
        actor=actor,
    )
    db.flush()

    pago_estado_anterior = str(pago.estado)
    if estado_interno == "aprobado":
        pago.estado = "aprobado"
        turno_destino: str | None = "confirmado"
    elif estado_interno in ("rechazado", "expirado"):
        pago.estado = "rechazado"
        turno_destino = "cancelado"
    else:
        pago.estado = estado_interno
        turno_destino = None
    db.add(pago)
    db.flush()

    transicionado = False
    turno: Turno | None = None
    if turno_destino is not None:
        try:
            turno_id_val: object = pago.turno_id
            if isinstance(turno_id_val, str):
                turno_id_val = uuid.UUID(turno_id_val)
            turno = db.get(Turno, turno_id_val)
            if turno is not None and str(turno.estado) == "creado":
                ahora = datetime.now(UTC)
                turno.estado = turno_destino
                turno.version = int(turno.version) + 1
                db.add(
                    TurnoHistorial(
                        turno_id=turno.id,
                        estado_anterior="creado",
                        estado_nuevo=turno_destino,
                        actor_tipo="sistema",
                        actor_id="sistema",
                        fecha=ahora,
                        motivo=f"pago {estado_interno} vía webhook",
                    )
                )
                db.flush()
                transicionado = True
                if turno_destino == "confirmado":
                    encolar_confirmacion(db, turno)
        except Exception:
            transicionado = False

    if estado_interno == "aprobado":
        emitir_recibo_pago(db, pago)

    return {
        "pago": pago,
        "turno": turno,
        "transicionado": transicionado,
        "pago_estado_anterior": pago_estado_anterior,
    }


def _procesar_webhook_devolucion(
    db: Session,
    datos: dict[str, str],
    payload_crudo: str,
    actor: str = "sistema",
) -> dict[str, object]:
    """Rama devolución del webhook (D4/D5): solo `aprobada` se ejecuta.

    - Replay: si la devolución ya está `ejecutada` con el mismo `mp_refund_id`,
      no hace nada (idempotente, P4).
    - Devolución no `aprobada`: persiste el payload crudo para auditoría y
      responde error explícito SIN efectos (borde de la spec).
    - Efectos en la misma transacción: devolución `ejecutada` + `mp_refund_id`,
      pago `reembolsado_total|parcial` (monto original intacto),
      `evento_pago(devolucion_ejecutada, actor=sistema, solicitado_por)` y
      `transition(cancelado→devuelto, sistema)` con historial (P9).
    """
    mp_refund_id = str(datos.get("mp_refund_id", ""))
    mp_payment_id = str(datos.get("mp_payment_id", ""))
    pago = db.query(Pago).filter(Pago.mp_payment_id == mp_payment_id).first()
    if pago is None:
        return {
            "error": "pago_no_encontrado",
            "kind": "devolucion",
            "mp_refund_id": mp_refund_id,
            "mp_payment_id": mp_payment_id,
        }

    devolucion = (
        db.query(Devolucion)
        .filter(Devolucion.pago_id == pago.id, Devolucion.is_active.is_(True))
        .first()
    )
    if devolucion is None:
        return {
            "error": "devolucion_no_encontrada",
            "kind": "devolucion",
            "mp_refund_id": mp_refund_id,
            "pago": pago,
        }

    if str(devolucion.estado) == "ejecutada":
        if str(devolucion.mp_refund_id) == mp_refund_id:
            return {
                "pago": pago,
                "devolucion": devolucion,
                "turno": None,
                "ejecutada": False,
                "transicionado": False,
                "idempotente": True,
                "kind": "devolucion",
            }
        return {
            "error": "mp_refund_distinto",
            "kind": "devolucion",
            "mp_refund_id": mp_refund_id,
            "devolucion": devolucion,
            "pago": pago,
        }

    EventoPagoRepository(db).add_evento(
        pago_id=pago.id,
        tipo_evento="webhook_recibido",
        payload_json={
            "kind": "devolucion",
            "mp_payment_id": mp_payment_id,
            "mp_refund_id": mp_refund_id,
            "status": str(datos.get("status", "refunded")),
            "payload_crudo": payload_crudo,
        },
        actor=actor,
    )

    if str(devolucion.estado) != "aprobada":
        return {
            "error": "devolucion_no_aprobada",
            "kind": "devolucion",
            "mp_refund_id": mp_refund_id,
            "devolucion": devolucion,
            "pago": pago,
        }

    if devolucion.ejecutada_por is None or devolucion.ejecutada_at is None:
        return {
            "error": "devolucion_sin_solicitante",
            "kind": "devolucion",
            "mp_refund_id": mp_refund_id,
            "devolucion": devolucion,
            "pago": pago,
        }

    turno_id_val: object = devolucion.turno_id
    if isinstance(turno_id_val, str):
        turno_id_val = uuid.UUID(turno_id_val)
    turno = db.get(Turno, turno_id_val)
    if turno is None or str(turno.estado) != "cancelado":
        return {
            "error": "turno_no_cancelado",
            "kind": "devolucion",
            "mp_refund_id": mp_refund_id,
            "devolucion": devolucion,
            "pago": pago,
        }

    monto_devolucion = Decimal(str(devolucion.monto))
    monto_pago = Decimal(str(pago.monto))
    devolucion.estado = "ejecutada"
    devolucion.mp_refund_id = mp_refund_id
    db.add(devolucion)
    pago.estado = (
        "reembolsado_total"
        if monto_devolucion == monto_pago
        else "reembolsado_parcial"
    )
    db.add(pago)

    solicitado_por = str(devolucion.ejecutada_por)
    EventoPagoRepository(db).add_evento(
        pago_id=pago.id,
        tipo_evento="devolucion_ejecutada",
        payload_json={
            "solicitado_por": solicitado_por,
            "monto": str(monto_devolucion),
            "porcentaje": int(devolucion.porcentaje),
            "mp_refund_id": mp_refund_id,
        },
        actor="sistema",
    )

    turno = transition(
        db,
        uuid.UUID(str(turno.id)),
        "devuelto",
        actor_tipo="sistema",
        actor_id="sistema",
        motivo=f"devolución {mp_refund_id} ejecutada",
    )

    emitir_recibo_devolucion(db, devolucion)

    return {
        "pago": pago,
        "devolucion": devolucion,
        "turno": turno,
        "ejecutada": True,
        "transicionado": True,
        "kind": "devolucion",
        "mp_refund_id": mp_refund_id,
    }


def _parsear_payload(payload_crudo: str) -> dict[str, str] | None:
    """Acepta JSON (MP/webhook público) o `k=v&k=v` (adaptador simulado)."""
    try:
        cargado = _json.loads(payload_crudo)
    except (_json.JSONDecodeError, ValueError):
        cargado = None
    if isinstance(cargado, dict):
        return {str(k): str(v) for k, v in cargado.items()}
    if "=" not in payload_crudo:
        return None
    partes: dict[str, str] = {}
    for parte in payload_crudo.split("&"):
        clave, _, valor = parte.partition("=")
        if clave:
            partes[clave] = valor
    return partes


def procesar_webhook(
    db: Session, payload_crudo: str, firma: str, actor: str = "sistema",
) -> dict[str, object]:
    """Pipeline compartido del webhook (P10): firma → payload crudo → rama.

    Lo usan `POST /webhooks/mercadopago` y la ejecución de devoluciones, así
    la firma HMAC y la idempotencia son idénticas en ambos caminos.
    """
    settings = get_settings()
    if not firma:
        return {"error": "FIRMA_REQUERIDA"}
    if not _validar_firma_webhook(payload_crudo, firma, settings.mp_webhook_secret):
        return {"error": "FIRMA_INVALIDA"}
    datos = _parsear_payload(payload_crudo)
    if datos is None:
        return {"error": "PAYLOAD_INVALIDO"}

    if str(datos.get("kind", "pago")) == "devolucion":
        return _procesar_webhook_devolucion(db, datos, payload_crudo, actor)

    mp_payment_id = str(datos.get("mp_payment_id", ""))
    estado_interno = _extraer_estado_mp(str(datos.get("status", "aprobado")))
    resultado = _procesar_webhook_pago(
        db, mp_payment_id, estado_interno, payload_crudo, actor=actor,
    )
    resultado["mp_payment_id"] = mp_payment_id
    resultado["estado"] = estado_interno
    return resultado


@router.get("/pagos/{pago_id}", response_model=PagoOut)
def obtener_pago(
    pago_id: uuid.UUID,
    ident: Identity = Depends(STAFF_PAGOS),
    db: Session = Depends(get_db),
) -> PagoOut:
    """Consulta detalle de pago para staff con scope P8 y marca simulada."""
    pago = db.query(Pago).filter(Pago.id == pago_id, Pago.is_active.is_(True)).first()
    if pago is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "pago inexistente")
    if ident.rol == "odontologo" and (
        ident.odontologo_id is None
        or str(pago.odontologo_id) != str(ident.odontologo_id)
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "pago de otro profesional")
    return PagoOut(
        pago_id=str(pago.id),
        turno_id=str(pago.turno_id),
        estado=str(pago.estado),
        monto=float(pago.monto),
        moneda=str(pago.moneda),
        proveedor=str(pago.proveedor),
        marca=marca_pago_actual(),
        leyenda_comprobante=leyenda_comprobante_actual(),
    )


@router.post("/pagos/{pago_id}/simular")
def simular_pago(
    pago_id: uuid.UUID,
    cuerpo: SimularBody,
    request: Request,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Sandbox de pagos simulados: Aprobar / Rechazar / Expirar.

    Solo disponible con `PAGO_MODO=simulado`. Exige `checkout_token` de 1
    uso con rate-limit. El adaptador emite el evento firmado entregado al
    handler del webhook.
    """
    _simulado_requerido()

    ip = request.client.host if request.client is not None else "desconocida"
    if not get_sandbox_limiter().check_and_count(f"ratelimit:pagos_simular:{ip}"):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "demasiadas solicitudes sandbox"
        )

    checkout_token = request.headers.get("checkout_token")
    if not checkout_token:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "checkout_token requerido"
        )

    accion = TipoAccionPago(cuerpo.accion)
    proveedor = get_proveedor_pago()
    try:
        evento = proveedor.ejecutar_accion(pago_id, accion, checkout_token)
    except ValueError as exc:
        return JSONResponse(
            status_code=422,
            content={"code": "TOKEN_INVALIDO", "detail": str(exc)},
        )

    firma = str(evento["firma"])
    payload = str(evento["payload"])
    if not _validar_firma_webhook(payload, firma, get_settings().mp_webhook_secret):
        return JSONResponse(
            status_code=401,
            content={"code": "FIRMA_INVALIDA", "detail": "firma HMAC no válida"},
        )

    pago = db.get(Pago, pago_id)
    if pago is None:
        return JSONResponse(
            status_code=404,
            content={"code": "PAGO_NO_ENCONTRADO", "detail": "pago inexistente"},
        )

    partes: dict[str, str] = {}
    for parte in payload.split("&"):
        k, _, v = parte.partition("=")
        partes[k] = v
    status_mp = partes.get("status", "aprobado")
    estado_interno = _extraer_estado_mp(status_mp)

    resultado = _procesar_webhook_pago(
        db, pago.mp_payment_id, estado_interno, payload, actor="sistema"
    )
    if "error" in resultado:
        return JSONResponse(
            status_code=404,
            content={"code": "PAGO_NO_ENCONTRADO", "detail": resultado["error"]},
        )

    db.commit()

    pago_res = resultado["pago"]
    turno_res = resultado["turno"]
    assert isinstance(pago_res, Pago)
    return JSONResponse(
        status_code=200,
        content={
            "pago_id": str(pago_res.id),
            "estado_pago": str(pago_res.estado),
            "turno_id": str(turno_res.id) if isinstance(turno_res, Turno) else None,
            "estado_turno": (
                str(turno_res.estado) if isinstance(turno_res, Turno) else None
            ),
            "transicionado": resultado["transicionado"],
            "idempotente": resultado.get("idempotente", False),
            "proveedor": "simulado",
            "marca": marca_pago_actual(),
        },
    )


@router.post("/webhooks/mercadopago")
async def webhook_mercadopago(
    request: Request,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Webhook de MercadoPago (mismo handler en modo simulado y real).

    Valida firma HMAC → persiste evento_pago(webhook_recibido) con payload
    crudo → idempotencia por `mp_payment_id` (pago) o `mp_refund_id`
    (devolución) → transita el turno con actor `sistema` (P10).
    """
    body = await request.body()
    payload_str = body.decode("utf-8")
    firma = request.headers.get("x-signature", "")

    resultado = procesar_webhook(db, payload_str, firma, actor="sistema")
    db.commit()

    error = str(resultado.get("error", ""))
    if error == "FIRMA_REQUERIDA":
        return JSONResponse(
            status_code=401,
            content={"code": "FIRMA_REQUERIDA", "detail": "firma HMAC requerida"},
        )
    if error == "FIRMA_INVALIDA":
        return JSONResponse(
            status_code=401,
            content={"code": "FIRMA_INVALIDA", "detail": "firma HMAC no válida"},
        )
    if error == "PAYLOAD_INVALIDO":
        return JSONResponse(
            status_code=422,
            content={"code": "PAYLOAD_INVALIDO", "detail": "payload no es JSON válido"},
        )
    if error == "devolucion_no_aprobada":
        return JSONResponse(
            status_code=409,
            content={
                "code": "DEVOLUCION_NO_APROBADA",
                "detail": "la devolución no está aprobada; evento solo auditado",
            },
        )
    if error == "mp_refund_distinto":
        return JSONResponse(
            status_code=409,
            content={
                "code": "MP_REFUND_DISTINTO",
                "detail": "la devolución ya se ejecutó con otro mp_refund_id",
            },
        )
    if error in ("pago_no_encontrado", "devolucion_no_encontrada"):
        return JSONResponse(
            status_code=404,
            content={"code": "PAGO_NO_ENCONTRADO", "detail": error},
        )
    if error:
        return JSONResponse(
            status_code=422,
            content={"code": "WEBHOOK_NO_PROCESABLE", "detail": error},
        )

    return JSONResponse(
        status_code=200,
        content={
            "kind": resultado.get("kind", "pago"),
            "mp_payment_id": resultado.get("mp_payment_id", ""),
            "mp_refund_id": resultado.get("mp_refund_id"),
            "estado": resultado.get("estado", "refunded"),
            "transicionado": resultado.get("transicionado", False),
            "idempotente": resultado.get("idempotente", False),
            "marca": marca_pago_actual(),
        },
    )
