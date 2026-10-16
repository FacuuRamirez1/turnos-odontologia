"""Router montos C-04 (D-MONTOS, D1) — PATCH propio por odontólogo.

- Solo rol `odontologo` (recepción/admin → 403 por matriz 03 §2 fila montos).
- Lee `odontologo_id` del claim, nunca del body (anti-IDOR por diseño).
- Montos `NUMERIC(10,2)` no negativos; sin regla de proporción en v1
  (`monto_senia > monto_turno` permitido).
- Schemas P2 `extra='forbid'`; negativo → 422 sin cambios.
"""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.security.dependencies import Identity, require_role, scoped_odontologo_id
from app.infra.db.models import Odontologo
from app.infra.db.session import get_db

router = APIRouter(tags=["odontologos"])
SOLO_ODONTO = require_role("odontologo")


class MontosPatch(BaseModel):
    """Edición de montos propios — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

    monto_turno: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)
    monto_senia: Decimal | None = Field(default=None, ge=0, max_digits=10, decimal_places=2)


class MontosOut(BaseModel):
    """Montos vigentes — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

    odontologo_id: uuid.UUID
    monto_turno: Decimal
    monto_senia: Decimal


@router.patch("/odontologos/montos", response_model=MontosOut)
def actualizar_montos(
    body: MontosPatch,
    ident: Identity = Depends(SOLO_ODONTO),
    db: Session = Depends(get_db),
) -> MontosOut:
    """Actualiza montos del odontólogo autenticado (claim, nunca body)."""
    od = scoped_odontologo_id(ident)
    fila = db.query(Odontologo).filter(Odontologo.id == od).first()
    if fila is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "odontólogo inexistente")
    if body.monto_turno is not None:
        fila.monto_turno = body.monto_turno
    if body.monto_senia is not None:
        fila.monto_senia = body.monto_senia
    db.commit()
    db.refresh(fila)
    return MontosOut(
        odontologo_id=uuid.UUID(str(fila.id)),
        monto_turno=fila.monto_turno,
        monto_senia=fila.monto_senia,
    )
