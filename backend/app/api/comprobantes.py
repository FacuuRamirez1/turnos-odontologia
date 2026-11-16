"""Comprobantes C-08 (design D6/D8) - staff: detalle y descarga de PDF."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.security.dependencies import Identity, require_role
from app.domain.comprobantes.pdf import generar_pdf
from app.domain.comprobantes.repositories import (
    ComprobanteFueraDeScope,
    ComprobanteRepository,
)
from app.domain.pagos.service import marca_pago_actual
from app.infra.db.models import Comprobante
from app.infra.db.session import get_db

router = APIRouter(prefix="/comprobantes", tags=["comprobantes"])

STAFF = require_role("odontologo", "recepcionista", "admin")


class ComprobanteOut(BaseModel):
    """Comprobante (recibo) - P2 `extra='forbid'` + marca simulada (P15)."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    pago_id: uuid.UUID
    devolucion_id: uuid.UUID | None
    turno_id: uuid.UUID
    tipo: str
    concepto: str
    numero: str
    monto: float
    moneda: str
    cae: str | None
    emitida_at: datetime | None
    simulado: bool
    marca: str


def _out(comprobante: Comprobante) -> ComprobanteOut:
    return ComprobanteOut(
        id=uuid.UUID(str(comprobante.id)),
        pago_id=uuid.UUID(str(comprobante.pago_id)),
        devolucion_id=(
            uuid.UUID(str(comprobante.devolucion_id))
            if comprobante.devolucion_id is not None
            else None
        ),
        turno_id=uuid.UUID(str(comprobante.turno_id)),
        tipo=comprobante.tipo,
        concepto=comprobante.concepto,
        numero=comprobante.numero,
        monto=float(comprobante.monto),
        moneda=comprobante.moneda,
        cae=comprobante.cae,
        emitida_at=comprobante.emitida_at,
        simulado=comprobante.simulado,
        marca=marca_pago_actual(),
    )


def _comprobante_visible(
    repo: ComprobanteRepository, comprobante_id: uuid.UUID,
) -> Comprobante:
    """Resuelve el comprobante dentro del scope: ajeno -> 403, inexistente -> 404."""
    try:
        comprobante = repo.get(comprobante_id)
    except ComprobanteFueraDeScope as exc:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "comprobante de otro profesional"
        ) from exc
    if comprobante is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "comprobante inexistente")
    return comprobante


@router.get("/{comprobante_id}", response_model=ComprobanteOut)
def detalle_comprobante(
    comprobante_id: uuid.UUID,
    ident: Identity = Depends(STAFF),
    db: Session = Depends(get_db),
) -> ComprobanteOut:
    """Detalle bajo el mismo scope; ajeno -> 403, inexistente -> 404 (P8/D6)."""
    repo = ComprobanteRepository.scoped(db, ident)
    return _out(_comprobante_visible(repo, comprobante_id))


@router.get("/{comprobante_id}/pdf")
def descargar_pdf(
    comprobante_id: uuid.UUID,
    ident: Identity = Depends(STAFF),
    db: Session = Depends(get_db),
) -> Response:
    """PDF on-demand regenerado desde el snapshot (D6); sin blobs en DB."""
    repo = ComprobanteRepository.scoped(db, ident)
    comprobante = _comprobante_visible(repo, comprobante_id)
    return Response(content=generar_pdf(comprobante), media_type="application/pdf")
