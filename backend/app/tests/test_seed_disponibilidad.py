"""Tests C-04 §6.2 — seed extendido con disponibilidad + bloqueos (P11, P13).

- feliz: disponibilidad L–V 9–17 por odontólogo (10 filas), tope 14/día;
- feliz: 1 feriado = 2 filas + 1 bloqueo ejemplo;
- borde: doble corrida sin duplicados (idempotencia).
"""

from sqlalchemy.orm import Session

from app.infra.db.models import Bloqueo, Disponibilidad
from app.infra.db.seed_dev import seed


def test_disponibilidad_lv_por_odontologo_feliz(db_session: Session) -> None:
    seed(db_session)
    filas = db_session.query(Disponibilidad).all()
    assert len(filas) == 10  # 2 odontólogos × L–V
    for fila in filas:
        assert fila.dia_semana in (0, 1, 2, 3, 4)
        assert (fila.hora_inicio.hour, fila.hora_fin.hour) == (9, 17)
        assert fila.duracion_min == 30
        assert fila.tope_dia == 14
    ods = {str(f.odontologo_id) for f in filas}
    assert len(ods) == 2


def test_feriado_dos_filas_mas_bloqueo_feliz(db_session: Session) -> None:
    seed(db_session)
    bloqueos = db_session.query(Bloqueo).all()
    assert len(bloqueos) == 3
    feriados = [b for b in bloqueos if b.motivo == "feriado"]
    assert len(feriados) == 2  # D-BLOQ: un feriado = N filas
    assert len({str(b.odontologo_id) for b in feriados}) == 2
    assert any(b.motivo == "bloqueo" for b in bloqueos)


def test_seed_idempotente_con_nuevas_tablas_borde(db_session: Session) -> None:
    from app.infra.db.models import Odontologo, Paciente, Usuario

    modelos = (Usuario, Odontologo, Paciente, Disponibilidad, Bloqueo)
    seed(db_session)
    primera = tuple(db_session.query(m).count() for m in modelos)
    assert primera == (4, 2, 5, 10, 3)
    seed(db_session)
    assert tuple(db_session.query(m).count() for m in modelos) == primera
