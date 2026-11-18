"""Publicación outbox → Redis del scheduler del worker (C-09, fix RPUSH).

`publicar_pendientes` solo marcaba `publicado_at`; nadie empujaba el job a
`mail:pendientes`, así que el worker (`BLPOP`) nunca enviaba nada.
"""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.domain.notificaciones.outbox import encolar_confirmacion
from app.infra.db.models import RecordatorioMail
from app.tests.test_worker import _sembrar
from app.workers.main import QUEUE, ejecutar_tick_scheduler


class _FakeRedis:
    """Doble mínimo de la cola: `rpush`/`lrange` sobre listas en memoria."""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.colas: dict[str, list[str]] = {}

    def rpush(self, nombre: str, valor: str) -> int:
        if self.fail:
            raise ConnectionError("redis caído")
        self.colas.setdefault(nombre, []).append(valor)
        return len(self.colas[nombre])


def _factory(db_engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=db_engine, class_=Session, expire_on_commit=False)


def _fila_encolada(db_session: Session) -> RecordatorioMail:
    turno, _, _ = _sembrar(db_session)
    fila = encolar_confirmacion(db_session, turno)
    assert fila is not None
    db_session.commit()
    return fila


def _jobs(redis: _FakeRedis) -> list[dict[str, Any]]:
    return [json.loads(x) for x in redis.colas.get(QUEUE, [])]


def test_tick_empuja_job_a_redis_feliz(db_session: Session, db_engine: Engine) -> None:
    fila = _fila_encolada(db_session)
    redis = _FakeRedis()

    res = ejecutar_tick_scheduler(_factory(db_engine), 24, redis)

    assert res["publicados"] == 1
    assert _jobs(redis) == [{"recordatorio_id": str(fila.id)}]
    db_session.expire_all()
    assert db_session.get(RecordatorioMail, fila.id).publicado_at is not None  # type: ignore[union-attr]


def test_redis_caido_no_marca_publicado_error_de_negocio(
    db_session: Session, db_engine: Engine,
) -> None:
    fila = _fila_encolada(db_session)
    redis = _FakeRedis(fail=True)

    with pytest.raises(ConnectionError):
        ejecutar_tick_scheduler(_factory(db_engine), 24, redis)

    db_session.expire_all()
    recargada = db_session.get(RecordatorioMail, fila.id)
    assert recargada is not None
    assert recargada.publicado_at is None  # se reintenta en el próximo tick
    assert recargada.estado == "encolado"


def test_segundo_tick_no_duplica_el_job_borde(
    db_session: Session, db_engine: Engine,
) -> None:
    fila = _fila_encolada(db_session)
    redis = _FakeRedis()
    factory = _factory(db_engine)

    ejecutar_tick_scheduler(factory, 24, redis)
    res2 = ejecutar_tick_scheduler(factory, 24, redis)

    assert res2["publicados"] == 0
    assert _jobs(redis) == [{"recordatorio_id": str(fila.id)}]


def test_reintento_vencido_se_vuelve_a_empujar_borde(
    db_session: Session, db_engine: Engine,
) -> None:
    fila = _fila_encolada(db_session)
    ahora = datetime.now(UTC)
    fila.estado = "reintentando"
    fila.intentos = 1
    fila.publicado_at = ahora - timedelta(minutes=10)
    fila.proximo_intento_at = ahora - timedelta(minutes=1)
    db_session.add(fila)
    db_session.commit()
    redis = _FakeRedis()
    factory = _factory(db_engine)

    res = ejecutar_tick_scheduler(factory, 24, redis)
    res2 = ejecutar_tick_scheduler(factory, 24, redis)

    assert res["republicados"] == 1
    assert _jobs(redis) == [{"recordatorio_id": str(fila.id)}]  # una sola vez
    assert res2["republicados"] == 0
