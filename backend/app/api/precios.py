"""Router público C-10 — `GET /api/precios` (03 §3.6, D11, P12).

Lista aranceles de odontólogos activos + condiciones de trial público. Sin
JWT y sin PII de pacientes por construcción: solo ids profesionales y montos.
Rate-limit fixed-window por IP (`PRECIOS_LIMIT`/min). Schemas Pydantic v2
`extra='forbid'` (P2), incluido el modelo de query: parámetros no declarados
se rechazan con 422.
"""

import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.domain.pagos.service import marca_pago_actual
from app.infra.db.models import Odontologo
from app.infra.db.session import get_db
from app.infra.redis.rate_limit import LoginRateLimiter, build_rate_limiter

router = APIRouter(tags=["precios-publicos"])

PRECIOS_PREFIX = "precios:ratelimit:"
PRECIOS_LIMIT = 30
PRECIOS_WINDOW = 60

_precios_limiter: LoginRateLimiter | None = None


def get_precios_limiter() -> LoginRateLimiter:
    """Limitador activo (lazy de env; `reset_precios_limiter` lo renueva)."""
    global _precios_limiter
    if _precios_limiter is None:
        _precios_limiter = build_rate_limiter(
            get_settings().redis_url, limit=PRECIOS_LIMIT, window_seconds=PRECIOS_WINDOW
        )
    return _precios_limiter


def reset_precios_limiter(
    limit: int = PRECIOS_LIMIT, window_seconds: int = PRECIOS_WINDOW,
) -> None:
    """Renueva el limitador en memoria (seam solo para tests)."""
    global _precios_limiter
    _precios_limiter = LoginRateLimiter(
        client=None, limit=limit, window_seconds=window_seconds
    )


class PreciosQuery(BaseModel):
    """Query cerrada — cualquier parámetro extra → 422 (P2)."""

    model_config = ConfigDict(extra="forbid")


class PrecioOdontologoPublicoOut(BaseModel):
    """Arancel público de un profesional activo — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

    odontologo_id: uuid.UUID
    monto_turno: Decimal
    monto_senia: Decimal


class TrialPublicoOut(BaseModel):
    """Condiciones públicas del trial D11 — P2 `extra='forbid'`.

    `dias` queda en `None` mientras Q9 (cifras y límites del trial) siga
    abierta: el contrato no inventa un límite.
    """

    model_config = ConfigDict(extra="forbid")

    disponible: bool
    requiere_tarjeta: bool
    dias: int | None = None


class PreciosPublicosOut(BaseModel):
    """Aranceles vigentes + trial — P2 `extra='forbid'`, sin PII de pacientes."""

    model_config = ConfigDict(extra="forbid")

    odontologos: list[PrecioOdontologoPublicoOut]
    trial: TrialPublicoOut
    marca: str


@router.get("/precios", response_model=PreciosPublicosOut)
def precios_publicos(
    params: Annotated[PreciosQuery, Query()],
    request: Request,
    db: Session = Depends(get_db),
) -> PreciosPublicosOut:
    """Aranceles de profesionales activos + trial, sin exigir JWT."""
    _ = params
    ip = request.client.host if request.client is not None else "desconocida"
    if not get_precios_limiter().check_and_count(f"{PRECIOS_PREFIX}{ip}"):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "demasiadas consultas de precios"
        )
    filas = (
        db.query(Odontologo)
        .filter(Odontologo.is_active.is_(True), Odontologo.activo.is_(True))
        .all()
    )
    return PreciosPublicosOut(
        odontologos=[
            PrecioOdontologoPublicoOut(
                odontologo_id=uuid.UUID(str(f.id)),
                monto_turno=f.monto_turno,
                monto_senia=f.monto_senia,
            )
            for f in filas
        ],
        trial=TrialPublicoOut(disponible=True, requiere_tarjeta=False, dias=None),
        marca=marca_pago_actual(),
    )
