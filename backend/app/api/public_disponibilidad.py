"""Endpoint público C-04 — GET /api/disponibilidad (03 §3.1, P12, D-PUB).

- Sin JWT (ruta pública cerrada 03 §3.1); rate-limit 30/min por IP (D-RATE,
  implementado en 5.3 sobre este mismo handler).
- Query requerida: `odontologo_id` + `fecha` YYYY-MM-DD (ausente/malformada
  → 422 por FastAPI; pasada → 422 explícito, D-ERR).
- `odontologo_id` desconocido o inactivo → 404 (distingue "sin huecos" de
  "profesional inválido" para el frontend).
- Solo pares `inicio/fin` ISO con offset; cero datos de pacientes por
  construcción (el motor nunca los ve).
- D-PUB checkpoint: path físico `/api/disponibilidad` (montado como los
  routers existentes); la entrada lógica `GET /disponibilidad` de
  `PUBLIC_ROUTES` no se renombra (test_public_routes intacto).
"""

import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.domain.disponibilidad.motor import Slot, generar_slots, resolver_zona
from app.domain.turnos.ocupados import ocupados_rango
from app.infra.db.models import Bloqueo, Disponibilidad, Odontologo
from app.infra.db.session import get_db
from app.infra.redis.rate_limit import (
    DISPONIBILIDAD_LIMIT,
    WINDOW_SECONDS,
    LoginRateLimiter,
    build_rate_limiter,
    disponibilidad_key,
)

router = APIRouter(tags=["disponibilidad-publica"])

_public_limiter: LoginRateLimiter | None = None


def get_public_limiter() -> LoginRateLimiter:
    """Limitador activo (lazy de env; `reset_public_limiter` lo renueva en tests)."""
    global _public_limiter
    if _public_limiter is None:
        _public_limiter = build_rate_limiter(
            get_settings().redis_url, limit=DISPONIBILIDAD_LIMIT, window_seconds=WINDOW_SECONDS
        )
    return _public_limiter


def reset_public_limiter(
    limit: int = DISPONIBILIDAD_LIMIT, window_seconds: int = WINDOW_SECONDS
) -> None:
    """Renueva el limitador en memoria (seam solo para tests)."""
    global _public_limiter
    _public_limiter = LoginRateLimiter(client=None, limit=limit, window_seconds=window_seconds)


class SlotOut(BaseModel):
    """Par ofrecible — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

    inicio: datetime
    fin: datetime


class DisponibilidadPublicaOut(BaseModel):
    """Huecos libres del día — P2 `extra='forbid'`."""

    model_config = ConfigDict(extra="forbid")

    slots: list[SlotOut]


def _hoy_local() -> date:
    from zoneinfo import ZoneInfo

    try:
        return datetime.now(ZoneInfo("America/Argentina/Cordoba")).date()
    except Exception:
        return datetime.now(UTC).date()


@router.get("/disponibilidad", response_model=DisponibilidadPublicaOut)
def huecos_libres(
    request: Request,
    odontologo_id: uuid.UUID = Query(),
    fecha: date = Query(),
    db: Session = Depends(get_db),
) -> DisponibilidadPublicaOut:
    """Devuelve solo huecos libres del profesional en la fecha (público)."""
    ip = request.client.host if request.client is not None else "desconocida"
    if not get_public_limiter().check_and_count(disponibilidad_key(ip)):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "demasiadas consultas")
    settings = get_settings()
    zona = resolver_zona(settings.timezone)
    if fecha < _hoy_local():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "fecha en el pasado")
    od = db.query(Odontologo).filter(Odontologo.id == odontologo_id).first()
    if od is None or not bool(od.is_active and od.activo):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "odontólogo desconocido")

    franjas = (
        db.query(Disponibilidad)
        .filter(
            Disponibilidad.odontologo_id == odontologo_id,
            Disponibilidad.is_active.is_(True),
            Disponibilidad.dia_semana == fecha.weekday(),
        )
        .all()
    )
    vigentes = [
        f
        for f in franjas
        if (f.vigente_desde is None or f.vigente_desde <= fecha)
        and (f.vigente_hasta is None or f.vigente_hasta >= fecha)
    ]
    medianoche = datetime(fecha.year, fecha.month, fecha.day, tzinfo=zona)
    inicio_dia = medianoche.replace(hour=0, minute=0)
    fin_dia = medianoche.replace(hour=23, minute=59, second=59)
    bloqueos_db = (
        db.query(Bloqueo)
        .filter(
            Bloqueo.odontologo_id == odontologo_id,
            Bloqueo.is_active.is_(True),
            Bloqueo.desde < fin_dia,
            Bloqueo.hasta > inicio_dia,
        )
        .all()
    )
    bloques = [
        Slot(
            inicio=b.desde if b.desde.tzinfo else b.desde.replace(tzinfo=zona),
            fin=b.hasta if b.hasta.tzinfo else b.hasta.replace(tzinfo=zona),
        )
        for b in bloqueos_db
    ]
    ahora = datetime.now(UTC)
    # C-05 (design D7, delta spec): resta turnos activos del profesional/día
    # (`creado` no-vencido + `confirmado`); el resto libera por cómputo.
    ocupados_db = ocupados_rango(
        db, odontologo_id, inicio_dia, fin_dia,
        settings.reserva_ttl_min, ahora)
    ocupados = [
        Slot(inicio=o[0] if o[0].tzinfo else o[0].replace(tzinfo=UTC),
             fin=o[1] if o[1].tzinfo else o[1].replace(tzinfo=UTC))
        for o in ocupados_db
    ]
    salida: list[SlotOut] = []
    for f in vigentes:
        for s in generar_slots(
            dia_semana=f.dia_semana,
            hora_inicio=f.hora_inicio,
            hora_fin=f.hora_fin,
            duracion_min=f.duracion_min,
            tope_dia=f.tope_dia,
            fecha=fecha,
            ahora=ahora,
            anticipacion_hs=settings.anticipacion_min_hs,
            bloqueos=bloques,
            ocupados=ocupados,
            tz=zona,
        ):
            salida.append(SlotOut(inicio=s.inicio, fin=s.fin))
    salida.sort(key=lambda s: s.inicio)
    return DisponibilidadPublicaOut(slots=salida)
