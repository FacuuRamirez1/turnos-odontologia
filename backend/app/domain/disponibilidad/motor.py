"""Motor puro de slots C-04 (D-SLOT) — sin I/O, testeable sin fixtures.

`generar_slots(...) -> list[Slot]`: múltiplos exactos desde `hora_inicio`
(RN-DURACION, resto parcial descartado), tope/día (RN-TOPE), resta de
bloqueos + `ocupados` por solape (RN-PAUSAS; `ocupados=[]` en C-04, seam que
C-05 conecta a `turno` sin cambiar la firma), anticipación inclusiva
`slot.inicio - ahora >= anticipacion_hs` (RN-ANTICIPACION, D-ANT).

Zona: `fecha` es el día en `tz` (default `America/Argentina_Cordoba`, D-TZ);
`ahora` UTC convertido a local para comparar; slots con offset incluido.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# IANA canónico con barra (el alias con guion bajo no existe en tzdata).
DEFAULT_TZ_NAME = "America/Argentina/Cordoba"
DEFAULT_TZ = ZoneInfo(DEFAULT_TZ_NAME)


def resolver_zona(nombre: str | None) -> ZoneInfo:
    """Acepta el alias histórico con guion bajo y devuelve la zona IANA real."""
    if not nombre:
        return DEFAULT_TZ
    candidato = nombre.replace("America/Argentina_Cordoba", DEFAULT_TZ_NAME)
    try:
        return ZoneInfo(candidato)
    except ZoneInfoNotFoundError:
        return DEFAULT_TZ


@dataclass(frozen=True)
class Slot:
    """Par ofrecible `inicio/fin` con offset (serializa ISO en el endpoint)."""

    inicio: datetime
    fin: datetime


def _solapa(a_inicio: datetime, a_fin: datetime, b_inicio: datetime, b_fin: datetime) -> bool:
    return a_inicio < b_fin and b_inicio < a_fin


def generar_slots(
    *,
    dia_semana: int,
    hora_inicio: time,
    hora_fin: time,
    duracion_min: int,
    tope_dia: int,
    fecha: date,
    ahora: datetime,
    anticipacion_hs: int | float = 24,
    bloqueos: list[Slot] | None = None,
    ocupados: list[Slot] | None = None,
    tz: ZoneInfo | None = None,
) -> list[Slot]:
    """Genera slots ofrecibles del día `fecha` (D-SLOT, función pura)."""
    zona = tz or DEFAULT_TZ
    bloqueos = bloqueos or []
    ocupados = ocupados or []
    _ = dia_semana  # el filtrado por día lo hace el caller/endpoint (vigencia)

    medianoche = datetime(fecha.year, fecha.month, fecha.day, tzinfo=zona)
    inicio_dia = medianoche.replace(
        hour=hora_inicio.hour, minute=hora_inicio.minute, second=0, microsecond=0
    )
    fin_dia = medianoche.replace(
        hour=hora_fin.hour, minute=hora_fin.minute, second=0, microsecond=0
    )
    paso = timedelta(minutes=duracion_min)

    candidatos: list[Slot] = []
    cursor = inicio_dia
    while cursor + paso <= fin_dia:
        candidatos.append(Slot(inicio=cursor, fin=cursor + paso))
        cursor += paso

    ahora_local = ahora.astimezone(zona)
    anticipacion = timedelta(hours=anticipacion_hs)
    ofrecibles: list[Slot] = []
    for slot in candidatos:
        if slot.inicio - ahora_local < anticipacion:
            continue
        if any(_solapa(slot.inicio, slot.fin, b.inicio, b.fin) for b in bloqueos):
            continue
        if any(_solapa(slot.inicio, slot.fin, o.inicio, o.fin) for o in ocupados):
            continue
        ofrecibles.append(slot)
        if len(ofrecibles) >= tope_dia:
            break
    return ofrecibles
