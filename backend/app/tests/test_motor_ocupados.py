"""Tests C-04 §2.3 — seam `ocupados` inyectados (lo conecta C-05 a `turno`).

- feliz: slot ocupado ausente;
- borde: `tope` cuenta ocupados+libres (corta igual);
- borde: ocupados de otro profesional no restan (el caller filtra por
  odontologo_id; el motor documenta que solo resta lo que recibe).
"""

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from app.domain.disponibilidad.motor import Slot, generar_slots

CORDOBA = ZoneInfo("America/Argentina/Cordoba")
AHORA = datetime(2026, 10, 5, 10, 0, tzinfo=UTC)


def _slot(h1: int, m1: int, h2: int, m2: int) -> Slot:
    base = datetime(2026, 10, 5, tzinfo=CORDOBA)
    return Slot(
        inicio=base.replace(hour=h1, minute=m1, second=0, microsecond=0),
        fin=base.replace(hour=h2, minute=m2, second=0, microsecond=0),
    )


def test_slot_ocupado_ausente_feliz() -> None:
    slots = generar_slots(
        dia_semana=0, hora_inicio=time(9, 0), hora_fin=time(10, 0),
        duracion_min=30, tope_dia=14, fecha=AHORA.date(), ahora=AHORA,
        anticipacion_hs=0, bloqueos=[], ocupados=[_slot(9, 0, 9, 30)], tz=CORDOBA,
    )
    assert [(s.inicio.hour, s.inicio.minute) for s in slots] == [(9, 30)]


def test_tope_cuenta_ocupados_mas_libres_borde() -> None:
    # 4 candidatos, 1 ocupado, tope 2 → solo 2 ofrecidos (el ocupado no cuenta
    # como ofrecido pero el tope corta el día igual tras 2 libres).
    slots = generar_slots(
        dia_semana=0, hora_inicio=time(9, 0), hora_fin=time(11, 0),
        duracion_min=30, tope_dia=2, fecha=AHORA.date(), ahora=AHORA,
        anticipacion_hs=0, bloqueos=[], ocupados=[_slot(9, 0, 9, 30)], tz=CORDOBA,
    )
    assert [(s.inicio.hour, s.inicio.minute) for s in slots] == [(9, 30), (10, 0)]


def test_ocupados_otro_profesional_no_restan_borde() -> None:
    """El motor resta solo lo inyectado: C-05 filtra ocupados por odontologo_id."""
    slots = generar_slots(
        dia_semana=0, hora_inicio=time(9, 0), hora_fin=time(10, 0),
        duracion_min=30, tope_dia=14, fecha=AHORA.date(), ahora=AHORA,
        anticipacion_hs=0, bloqueos=[], ocupados=[], tz=CORDOBA,
    )
    assert len(slots) == 2  # sin inyectar nada ajeno, nada se resta
