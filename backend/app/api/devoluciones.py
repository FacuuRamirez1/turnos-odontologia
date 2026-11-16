"""Bandeja de devoluciones C-08 (design D8, spec § bandeja).

Solo staff con JWT (`require_role`): recepcionista/admin ven todas; odontólogo
solo las de sus turnos, con el scope forzado en `DevolucionRepository` (P8).
Los schemas son Pydantic v2 `extra='forbid'` (P2) y toda respuesta lleva
`marca` = `marca_pago_actual()` ("(simulado)" en modo simulado, P10/P15).
Esta ruta NO es pública (P12): no se agrega a `PUBLIC_ROUTES`.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.api.pagos import procesar_webhook
from app.core.security.dependencies import (
    Identity,
    require_role,
    scoped_odontologo_id,
)
from app.domain.devoluciones.estados import (
    TransicionDevolucionInvalida,
    validar_transicion,
)
from app.domain.devoluciones.repositories import (
    DevolucionFueraDeScope,
    DevolucionRepository,
)
from app.domain.notificaciones.outbox import encolar_aviso_devolucion
from app.domain.pagos.service import get_proveedor_pago, marca_pago_actual
from app.infra.db.models import Comprobante, Devolucion, Turno
from app.infra.db.models.pago import EventoPago, Pago
from app.infra.db.session import get_db

router = APIRouter(prefix="/devoluciones", tags=["devoluciones"])

STAFF = require_role("odontologo", "recepcionista", "admin")

EstadoDevolucion = Literal["pendiente", "aprobada", "rechazada", "ejecutada"]


class DevolucionOut(BaseModel):
    """Devolución de la bandeja — P2 `extra='forbid'` + marca simulada."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    pago_id: uuid.UUID
    turno_id: uuid.UUID
    monto: float
    porcentaje: int
    motivo: str | None
    motivo_rechazo: str | None
    estado: str
    aprobada_at: datetime | None
    rechazada_at: datetime | None
    marca: str


def _out(devolucion: Devolucion) -> DevolucionOut:
    return DevolucionOut(
        id=uuid.UUID(str(devolucion.id)),
        pago_id=uuid.UUID(str(devolucion.pago_id)),
        turno_id=uuid.UUID(str(devolucion.turno_id)),
        monto=float(devolucion.monto),
        porcentaje=int(devolucion.porcentaje),
        motivo=devolucion.motivo,
        motivo_rechazo=devolucion.motivo_rechazo,
        estado=str(devolucion.estado),
        aprobada_at=devolucion.aprobada_at,
        rechazada_at=devolucion.rechazada_at,
        marca=marca_pago_actual(),
    )


def _devolucion_visible(
    repo: DevolucionRepository,
    devolucion_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> Devolucion:
    """Resuelve la devolución dentro del scope: ajena → 403, inexistente → 404."""
    try:
        devolucion = (
            repo.get_for_update(devolucion_id)
            if for_update
            else repo.get(devolucion_id)
        )
    except DevolucionFueraDeScope as exc:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "devolución de otro profesional"
        ) from exc
    if devolucion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "devolución inexistente")
    return devolucion


@router.get("", response_model=list[DevolucionOut])
def listar_devoluciones(
    estado: EstadoDevolucion | None = Query(default=None),
    ident: Identity = Depends(STAFF),
    db: Session = Depends(get_db),
) -> list[DevolucionOut]:
    """Lista devoluciones visibles para el rol, filtrables por estado (P8)."""
    repo = DevolucionRepository.scoped(db, ident)
    return [_out(d) for d in repo.list(estado)]


class AlertaConciliacionOut(BaseModel):
    """Alerta de conciliación (`evento_pago(conciliado)`) — P2 + marca (P15)."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    pago_id: uuid.UUID
    turno_id: uuid.UUID
    tipo: str
    detalle: str | None
    estado_pago: str | None
    estado_esperado: str | None
    estado_turno: str | None
    discrepancia: bool
    actor: str
    fecha: datetime
    marca: str


def _texto_opcional(valor: object) -> str | None:
    return str(valor) if valor is not None else None


# NOTA: declarada ANTES de `/{devolucion_id}` para que "alertas" no se
# interprete como UUID y colisione con el detalle (FastAPI matchea por orden).
@router.get("/alertas", response_model=list[AlertaConciliacionOut])
def listar_alertas(
    ident: Identity = Depends(STAFF),
    db: Session = Depends(get_db),
) -> list[AlertaConciliacionOut]:
    """Alertas de conciliación visibles para el rol (D9, P8), con marca (P15)."""
    consulta = (
        db.query(EventoPago, Pago)
        .join(Pago, Pago.id == EventoPago.pago_id)
        .filter(EventoPago.tipo_evento == "conciliado", Pago.is_active.is_(True))
    )
    if ident.rol == "odontologo":
        consulta = consulta.filter(
            Pago.odontologo_id == scoped_odontologo_id(ident)
        )
    filas = consulta.order_by(EventoPago.created_at, EventoPago.id).all()

    alertas: list[AlertaConciliacionOut] = []
    for evento, pago in filas:
        payload = evento.payload_json if isinstance(evento.payload_json, dict) else {}
        if payload.get("discrepancia") is not True:
            continue
        alertas.append(
            AlertaConciliacionOut(
                id=uuid.UUID(str(evento.id)),
                pago_id=uuid.UUID(str(pago.id)),
                turno_id=uuid.UUID(str(pago.turno_id)),
                tipo=str(payload.get("tipo", "pago")),
                detalle=_texto_opcional(payload.get("detalle")),
                estado_pago=_texto_opcional(payload.get("estado_pago")),
                estado_esperado=_texto_opcional(payload.get("estado_esperado")),
                estado_turno=_texto_opcional(payload.get("estado_turno")),
                discrepancia=True,
                actor=str(evento.actor),
                fecha=evento.created_at,
                marca=marca_pago_actual(),
            )
        )
    return alertas


@router.get("/{devolucion_id}", response_model=DevolucionOut)
def detalle_devolucion(
    devolucion_id: uuid.UUID,
    ident: Identity = Depends(STAFF),
    db: Session = Depends(get_db),
) -> DevolucionOut:
    """Detalle bajo el mismo scope; ajena → 403, inexistente → 404 (P8)."""
    repo = DevolucionRepository.scoped(db, ident)
    return _out(_devolucion_visible(repo, devolucion_id))


class AprobarBody(BaseModel):
    """Aprobación manual con confirmación del monto — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

    monto_confirmado: Decimal
    motivo: str | None = Field(default=None, max_length=500)


@router.post("/{devolucion_id}/aprobar", response_model=DevolucionOut)
def aprobar_devolucion(
    devolucion_id: uuid.UUID,
    cuerpo: AprobarBody,
    ident: Identity = Depends(STAFF),
    db: Session = Depends(get_db),
) -> DevolucionOut | JSONResponse:
    """`pendiente→aprobada` con actor+fecha+monto y evento append-only (P9).

    Valida transición (→409) y monto (→422) ANTES de mutar: un fallo no escribe
    evento ni toca la fila.
    """
    repo = DevolucionRepository.scoped(db, ident)
    devolucion = _devolucion_visible(repo, devolucion_id)

    try:
        validar_transicion(str(devolucion.estado), "aprobada")
    except TransicionDevolucionInvalida as exc:
        return JSONResponse(
            status_code=409,
            content={"code": "TRANSICION_DEVOLUCION_INVALIDA", "detail": str(exc)},
        )

    monto_esperado = Decimal(str(devolucion.monto))
    if Decimal(cuerpo.monto_confirmado) != monto_esperado:
        return JSONResponse(
            status_code=422,
            content={
                "code": "MONTO_NO_COINCIDE",
                "detail": (
                    f"monto confirmado {cuerpo.monto_confirmado} "
                    f"no coincide con {monto_esperado}"
                ),
            },
        )

    devolucion.estado = "aprobada"
    devolucion.aprobada_por = uuid.UUID(ident.sub)
    devolucion.aprobada_at = datetime.now(UTC)
    db.add(devolucion)
    db.add(
        EventoPago(
            pago_id=devolucion.pago_id,
            tipo_evento="devolucion_aprobada",
            payload_json={
                "actor_id": ident.sub,
                "monto": str(monto_esperado),
                "porcentaje": int(devolucion.porcentaje),
                "motivo": cuerpo.motivo,
            },
            actor=ident.rol,
        )
    )
    db.commit()
    db.refresh(devolucion)
    return _out(devolucion)


class RechazarBody(BaseModel):
    """Rechazo con motivo obligatorio — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

    motivo: str = Field(min_length=1, max_length=500)

    @field_validator("motivo")
    @classmethod
    def _motivo_no_vacio(cls, value: str) -> str:
        limpio = value.strip()
        if not limpio:
            raise ValueError("el motivo del rechazo es obligatorio")
        return limpio


@router.post("/{devolucion_id}/rechazar", response_model=DevolucionOut)
def rechazar_devolucion(
    devolucion_id: uuid.UUID,
    cuerpo: RechazarBody,
    ident: Identity = Depends(STAFF),
    db: Session = Depends(get_db),
) -> DevolucionOut | JSONResponse:
    """`pendiente→rechazada` con motivo, actor y fecha; terminal (P9).

    No altera el turno (`cancelado`) ni el pago (`aprobado`): el rechazo solo
    cierra la devolución y deja el rastro en `evento_pago`.
    """
    repo = DevolucionRepository.scoped(db, ident)
    devolucion = _devolucion_visible(repo, devolucion_id)

    try:
        validar_transicion(str(devolucion.estado), "rechazada")
    except TransicionDevolucionInvalida as exc:
        return JSONResponse(
            status_code=409,
            content={"code": "TRANSICION_DEVOLUCION_INVALIDA", "detail": str(exc)},
        )

    devolucion.estado = "rechazada"
    devolucion.rechazada_por = uuid.UUID(ident.sub)
    devolucion.rechazada_at = datetime.now(UTC)
    devolucion.motivo_rechazo = cuerpo.motivo
    db.add(devolucion)
    db.add(
        EventoPago(
            pago_id=devolucion.pago_id,
            tipo_evento="devolucion_rechazada",
            payload_json={
                "actor_id": ident.sub,
                "motivo": cuerpo.motivo,
                "monto": str(devolucion.monto),
                "porcentaje": int(devolucion.porcentaje),
            },
            actor=ident.rol,
        )
    )
    turno = db.get(Turno, devolucion.turno_id)
    if turno is not None:
        encolar_aviso_devolucion(
            db,
            turno,
            int(devolucion.porcentaje),
            monto=Decimal(str(devolucion.monto)),
            resultado="rechazada",
            comprobante_id=None,
        )
    db.commit()
    db.refresh(devolucion)
    return _out(devolucion)


class EjecutarOut(BaseModel):
    """Resultado de ejecutar la devolución — P2 `extra='forbid'` + marca (P15)."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    estado: str
    monto: float
    porcentaje: int
    mp_refund_id: str
    pago_estado: str
    marca: str


def _ejecutar_out(db: Session, devolucion: Devolucion) -> EjecutarOut:
    pago = db.get(Pago, devolucion.pago_id)
    return EjecutarOut(
        id=uuid.UUID(str(devolucion.id)),
        estado=str(devolucion.estado),
        monto=float(devolucion.monto),
        porcentaje=int(devolucion.porcentaje),
        mp_refund_id=str(devolucion.mp_refund_id or ""),
        pago_estado=str(pago.estado) if pago is not None else "",
        marca=marca_pago_actual(),
    )


@router.post("/{devolucion_id}/ejecutar", response_model=EjecutarOut)
def ejecutar_devolucion(
    devolucion_id: uuid.UUID,
    ident: Identity = Depends(STAFF),
    db: Session = Depends(get_db),
) -> EjecutarOut | JSONResponse:
    """`aprobada→ejecutada` por el puerto y el MISMO handler del webhook (D4).

    1. `SELECT … FOR UPDATE` + scope P8 (ajena → 403 antes del proveedor).
    2. `ejecutada` → idempotente (mismo `mp_refund_id`, sin segundo evento).
    3. `ejecutada_por/at` se registran ANTES de llamar al proveedor.
    4. Consulta la key y solo ejecuta si no existe (P4).
    5. El evento firmado entra por `procesar_webhook`: solo el handler marca
       `ejecutada`, ajusta el pago y transiciona el turno (P10).
    6. `PAGO_MODO=mercadopago` (no construido) → 503 sin fallback simulado
       (P13/P15); la devolución queda `aprobada`.
    """
    repo = DevolucionRepository.scoped(db, ident)
    devolucion = _devolucion_visible(repo, devolucion_id, for_update=True)

    if str(devolucion.estado) == "ejecutada":
        return _ejecutar_out(db, devolucion)

    try:
        validar_transicion(str(devolucion.estado), "ejecutada")
    except TransicionDevolucionInvalida as exc:
        return JSONResponse(
            status_code=409,
            content={"code": "TRANSICION_DEVOLUCION_INVALIDA", "detail": str(exc)},
        )

    pago = db.get(Pago, devolucion.pago_id)
    if pago is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "pago inexistente")

    devolucion.ejecutada_por = uuid.UUID(ident.sub)
    devolucion.ejecutada_at = datetime.now(UTC)
    db.add(devolucion)
    db.flush()

    try:
        proveedor = get_proveedor_pago()
    except NotImplementedError:
        db.rollback()
        return JSONResponse(
            status_code=503,
            content={
                "code": "PROVEEDOR_NO_DISPONIBLE",
                "detail": "PAGO_MODO=mercadopago no construido en v1 (P15)",
            },
        )

    clave = str(devolucion.idempotency_key)
    evento = proveedor.consultar_devolucion(clave)
    if evento is None:
        evento = proveedor.ejecutar_devolucion(
            idempotency_key=clave,
            mp_payment_id=str(pago.mp_payment_id),
            monto=Decimal(str(devolucion.monto)),
        )

    resultado = procesar_webhook(
        db, str(evento["payload"]), str(evento["firma"]), actor="sistema",
    )
    error = str(resultado.get("error", ""))
    if error:
        db.commit()
        if error in ("pago_no_encontrado", "devolucion_no_encontrada"):
            raise HTTPException(status.HTTP_404_NOT_FOUND, error)
        return JSONResponse(
            status_code=409,
            content={"code": "EJECUCION_RECHAZADA", "detail": error},
        )

    db.refresh(devolucion)
    turno = db.get(Turno, devolucion.turno_id)
    comprobante = (
        db.query(Comprobante)
        .filter(
            Comprobante.devolucion_id == devolucion.id,
            Comprobante.concepto == "devolucion",
        )
        .first()
    )
    if turno is not None and str(devolucion.estado) == "ejecutada":
        encolar_aviso_devolucion(
            db,
            turno,
            int(devolucion.porcentaje),
            monto=Decimal(str(devolucion.monto)),
            resultado="ejecutada",
            comprobante_id=comprobante.id if comprobante is not None else None,
        )
    db.commit()
    db.refresh(devolucion)
    return _ejecutar_out(db, devolucion)
