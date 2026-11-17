"""C-12 1.3 — auditoría (turno_historial + evento_pago), scoped y sin payload."""

from sqlalchemy.orm import Session

from app.domain.reportes.consultas import filas_auditoria
from app.infra.db.models import TurnoHistorial
from app.tests._reportes_seed import (
    BASE,
    DESDE,
    HASTA,
    sembrar_evento,
    sembrar_odontologo,
    sembrar_pago,
    sembrar_turno,
)


def _historial(db: Session, turno_id: object) -> None:
    db.add(
        TurnoHistorial(
            turno_id=turno_id,
            estado_anterior="creado",
            estado_nuevo="confirmado",
            actor_tipo="sistema",
            actor_id="webhook",
            fecha=BASE,
        )
    )
    db.commit()


def test_union_de_transiciones_y_eventos(db_session: Session) -> None:
    od = sembrar_odontologo(db_session, "e1")
    turno = sembrar_turno(db_session, od)
    _historial(db_session, turno.id)
    sembrar_evento(db_session, sembrar_pago(db_session, turno))

    filas = filas_auditoria(db_session, DESDE, HASTA)

    origenes = sorted(f.origen for f in filas)
    assert origenes == ["evento_pago", "turno_historial"]
    assert all(f.actor and f.fecha for f in filas)


def test_sin_payload_crudo(db_session: Session) -> None:
    od = sembrar_odontologo(db_session, "e2")
    sembrar_evento(db_session, sembrar_pago(db_session, sembrar_turno(db_session, od)))

    filas = filas_auditoria(db_session, DESDE, HASTA)

    assert "no-exportar" not in repr(filas)


def test_aislamiento_por_odontologo(db_session: Session) -> None:
    a = sembrar_odontologo(db_session, "e3")
    b = sembrar_odontologo(db_session, "f3")
    _historial(db_session, sembrar_turno(db_session, b).id)

    assert filas_auditoria(db_session, DESDE, HASTA, odontologo_id=a) == []
    assert len(filas_auditoria(db_session, DESDE, HASTA, odontologo_id=b)) == 1
