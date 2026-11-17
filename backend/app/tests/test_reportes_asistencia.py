"""C-12 1.1 — conteo de turnos por estado y período (feliz / negocio / borde)."""

import pytest
from sqlalchemy.orm import Session

from app.domain.reportes.consultas import (
    ESTADOS_TURNO,
    PeriodoInvalido,
    conteo_por_estado,
)
from app.tests._reportes_seed import (
    BASE,
    DESDE,
    HASTA,
    sembrar_odontologo,
    sembrar_turno,
)


def test_conteos_por_estado_con_ceros(db_session: Session) -> None:
    od = sembrar_odontologo(db_session, "a1")
    for _ in range(3):
        sembrar_turno(db_session, od, estado="atendido")
    sembrar_turno(db_session, od, estado="no_show")

    res = conteo_por_estado(db_session, DESDE, HASTA)

    assert res["atendido"] == 3
    assert res["no_show"] == 1
    assert set(res) == set(ESTADOS_TURNO)
    assert res["cancelado"] == 0


def test_periodo_invalido_levanta(db_session: Session) -> None:
    with pytest.raises(PeriodoInvalido):
        conteo_por_estado(db_session, HASTA, DESDE)


def test_periodo_sin_turnos_trae_siete_ceros(db_session: Session) -> None:
    res = conteo_por_estado(db_session, DESDE, HASTA)
    assert len(res) == 7
    assert all(v == 0 for v in res.values())


def test_filtro_odontologo_y_fuera_de_periodo(db_session: Session) -> None:
    a = sembrar_odontologo(db_session, "a2")
    b = sembrar_odontologo(db_session, "b2")
    sembrar_turno(db_session, a, estado="atendido")
    sembrar_turno(db_session, b, estado="atendido")
    sembrar_turno(db_session, a, estado="atendido", inicio=BASE.replace(year=2027))

    res = conteo_por_estado(db_session, DESDE, HASTA, odontologo_id=a)

    assert res["atendido"] == 1
