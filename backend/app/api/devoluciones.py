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

from app.core.security.dependencies import Identity, require_role
from app.domain.devoluciones.estados import (
    TransicionDevolucionInvalida,
    validar_transicion,
)
from app.domain.devoluciones.repositories import (
    DevolucionFueraDeScope,
    DevolucionRepository,
)
from app.domain.pagos.service import marca_pago_actual
from app.infra.db.models import Devolucion
from app.infra.db.models.pago import EventoPago
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
    repo: DevolucionRepository, devolucion_id: uuid.UUID
) -> Devolucion:
    """Resuelve la devolución dentro del scope: ajena → 403, inexistente → 404."""
    try:
        devolucion = repo.get(devolucion_id)
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
    db.commit()
    db.refresh(devolucion)
    return _out(devolucion)
