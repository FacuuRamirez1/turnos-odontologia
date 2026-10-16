"""Tests C-04 §2.1 — motor puro generar_slots() (RED primero).

- feliz: grilla 09:00–10:00/30min → 2 slots exactos;
- negocio: pausa mediodía y feriado día completo restan;
- borde: resto parcial 09:00–09:50/30 → solo 1; solape parcial bloque-slot
  lo elimina; tope_dia=2 corta en 2; anticipación 23h ausente / 24h exactas
  presente con `ahora` fijo (límite inclusivo).
"""

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from app.domain.disponibilidad.motor import Slot, generar_slots

CORDOBA = ZoneInfo("America/Argentina/Cordoba")
AHORA = datetime(2026, 10, 5, 10, 0, tzinfo=UTC)  # lunes 07:00 Córdoba


def _slot(inicio: datetime, fin: datetime) -> Slot:
    return Slot(inicio=inicio, fin=fin)


def test_grilla_exacta_30min_feliz() -> None:
    slots = generar_slots(
        dia_semana=0,
        hora_inicio=time(9, 0),
        hora_fin=time(10, 0),
        duracion_min=30,
        tope_dia=14,
        fecha=AHORA.date(),
        ahora=AHORA,
        anticipacion_hs=0,
        bloqueos=[],
        ocupados=[],
        tz=CORDOBA,
    )
    assert [(s.inicio.hour, s.inicio.minute, s.fin.hour, s.fin.minute) for s in slots] == [
        (9, 0, 9, 30),
        (9, 30, 10, 0),
    ]


def test_resto_parcial_no_se_ofrece_borde() -> None:
    slots = generar_slots(
        dia_semana=0, hora_inicio=time(9, 0), hora_fin=time(9, 50),
        duracion_min=30, tope_dia=14, fecha=AHORA.date(), ahora=AHORA,
        anticipacion_hs=0, bloqueos=[], ocupados=[], tz=CORDOBA,
    )
    assert len(slots) == 1
    assert (slots[0].inicio.hour, slots[0].inicio.minute) == (9, 0)


def test_pausa_mediodia_resta_negocio() -> None:
    base = datetime(2026, 10, 5, 12, 0, tzinfo=CORDOBA)
    pausa = _slot(base, base.replace(hour=13, minute=0))
    slots = generar_slots(
        dia_semana=0, hora_inicio=time(11, 0), hora_fin=time(14, 0),
        duracion_min=30, tope_dia=14, fecha=AHORA.date(), ahora=AHORA,
        anticipacion_hs=0, bloqueos=[pausa], ocupados=[], tz=CORDOBA,
    )
    horas = [(s.inicio.hour, s.inicio.minute) for s in slots]
    assert horas == [(11, 0), (11, 30), (13, 0), (13, 30)]


def test_feriado_dia_completo_vacia_negocio() -> None:
    base = datetime(2026, 10, 5, 0, 0, tzinfo=CORDOBA)
    feriado = _slot(base, base.replace(hour=23, minute=59))
    slots = generar_slots(
        dia_semana=0, hora_inicio=time(9, 0), hora_fin=time(17, 0),
        duracion_min=30, tope_dia=14, fecha=AHORA.date(), ahora=AHORA,
        anticipacion_hs=0, bloqueos=[feriado], ocupados=[], tz=CORDOBA,
    )
    assert slots == []


def test_solape_parcial_bloque_elimina_slot_borde() -> None:
    # Slot 11:30–12:00 vs bloqueo 11:45–11:55 → ausente (cualquier solape resta).
    bloque = _slot(
        datetime(2026, 10, 5, 11, 45, tzinfo=CORDOBA),
        datetime(2026, 10, 5, 11, 55, tzinfo=CORDOBA),
    )
    slots = generar_slots(
        dia_semana=0, hora_inicio=time(11, 30), hora_fin=time(12, 30),
        duracion_min=30, tope_dia=14, fecha=AHORA.date(), ahora=AHORA,
        anticipacion_hs=0, bloqueos=[bloque], ocupados=[], tz=CORDOBA,
    )
    assert [(s.inicio.hour, s.inicio.minute) for s in slots] == [(12, 0)]


def test_tope_dia_corta_oferta_borde() -> None:
    slots = generar_slots(
        dia_semana=0, hora_inicio=time(9, 0), hora_fin=time(11, 0),
        duracion_min=30, tope_dia=2, fecha=AHORA.date(), ahora=AHORA,
        anticipacion_hs=0, bloqueos=[], ocupados=[], tz=CORDOBA,
    )
    assert len(slots) == 2


def test_anticipacion_23h_ausente_24h_presente_borde() -> None:
    # Slot mañana 09:00 Córdoba = 12:00 UTC; ahora 10:00 UTC → 26h: presente con 24h.
    maniana = datetime(2026, 10, 6, 9, 0, tzinfo=CORDOBA)
    ahora_24 = datetime(2026, 10, 5, 12, 0, tzinfo=UTC)  # justo 24h antes
    ahora_23 = datetime(2026, 10, 5, 13, 0, tzinfo=UTC)  # 23h antes → ausente
    kwargs = dict(
        dia_semana=1, hora_inicio=time(9, 0), hora_fin=time(10, 0),
        duracion_min=30, tope_dia=14, fecha=maniana.date(),
        bloqueos=[], ocupados=[], tz=CORDOBA,
    )
    assert generar_slots(ahora=ahora_23, anticipacion_hs=24, **kwargs) == []  # type: ignore[arg-type]
    presentes = generar_slots(ahora=ahora_24, anticipacion_hs=24, **kwargs)  # type: ignore[arg-type]
    assert len(presentes) == 2  # borde inclusivo: >= anticipación se ofrece
