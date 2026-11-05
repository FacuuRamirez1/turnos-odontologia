"""Tests C-09 task 1.2 — modelo `RecordatorioMail` (RED primero, task 1.2).

Escenarios (U2 feliz / negocio / borde):
- feliz: insert válido persiste con defaults (estado='encolado', intentos=0);
- negocio: tipo/estado inválido rechazado por CHECK;
- borde: duplicado (turno_id, tipo) rechazado por UNIQUE.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infra.db.models import RecordatorioMail


def _sembrar_turno(db_session: Session) -> uuid.UUID:
    from app.infra.db.models import Odontologo, Paciente, Turno, Usuario

    h = "$2b$04$" + "j" * 53
    fecha = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    u = Usuario(email=f"od-m-{uuid_hex()}@clinica-ficticia.example.ar",
                password_hash=h, rol="odontologo")
    db_session.add(u)
    db_session.commit()
    od = Odontologo(user_id=u.id, monto_turno=70000, monto_senia=65000)
    db_session.add(od)
    db_session.commit()
    pac = Paciente(dni=f"99{uuid_hex_int()}", nombre="Ana", apellido="Ficticia",
                   email="ana@ficticia.example.ar",
                   consentimiento_datos=True, consentimiento_fecha=fecha)
    db_session.add(pac)
    db_session.commit()
    ahora = datetime.now(UTC).replace(microsecond=0)
    turno = Turno(paciente_id=pac.id, odontologo_id=od.id, inicio=ahora,
                  fin=ahora + timedelta(minutes=30), estado="creado", canal="web",
                  idempotency_key=f"key-m-{uuid_hex()[:12]}")
    db_session.add(turno)
    db_session.commit()
    return turno.id


def uuid_hex() -> str:
    import uuid
    return uuid.uuid4().hex


def uuid_hex_int() -> str:
    import uuid
    return str(uuid.uuid4().int % 90000000 + 10000000)


def _crear_recordatorio(db_session: Session, turno_id: uuid.UUID, tipo: str = "confirmacion",
                        email: str = "ana@ficticia.example.ar") -> RecordatorioMail:
    fila = RecordatorioMail(turno_id=turno_id, tipo=tipo, destinatario=email,
                            estado="encolado", intentos=0)
    db_session.add(fila)
    db_session.commit()
    return fila


def test_insert_valido_persiste_feliz(db_session: Session) -> None:
    """Feliz: una fila válida se guarda con defaults y clave única."""
    turno_id = _sembrar_turno(db_session)
    fila = _crear_recordatorio(db_session, turno_id, "confirmacion")
    assert fila.id is not None
    assert fila.turno_id == turno_id
    assert fila.tipo == "confirmacion"
    assert fila.estado == "encolado"
    assert fila.intentos == 0
    assert fila.destinatario == "ana@ficticia.example.ar"
    assert fila.plantilla_version == "v1"


def test_tipo_estado_invalido_rechazado_negocio(db_session: Session) -> None:
    """Negocio: tipo o estado fuera de los CHECK cerrados fallan."""
    from app.infra.db.models import RecordatorioMail
    turno_id = _sembrar_turno(db_session)

    fila_tipo = RecordatorioMail(turno_id=turno_id, tipo="whatsapp",
                                 destinatario="a@b.c")
    db_session.add(fila_tipo)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    fila_estado = RecordatorioMail(turno_id=turno_id, tipo="confirmacion",
                                   destinatario="a@b.c", estado="envio_desconocido")
    db_session.add(fila_estado)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_duplicado_turno_tipo_rechazado_borde(db_session: Session) -> None:
    """Borde: UNIQUE (turno_id, tipo) impide dos filas iguales."""
    from app.infra.db.models import RecordatorioMail
    turno_id = _sembrar_turno(db_session)
    _crear_recordatorio(db_session, turno_id, "confirmacion")
    dup = RecordatorioMail(turno_id=turno_id, tipo="confirmacion",
                           destinatario="otra@ficticia.example.ar")
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_tipos_distintos_mismo_turno_conviven(db_session: Session) -> None:
    """Borde: un turno puede tener confirmacion y recordatorio independientes."""
    from app.infra.db.models import RecordatorioMail
    turno_id = _sembrar_turno(db_session)
    _crear_recordatorio(db_session, turno_id, "confirmacion")
    _crear_recordatorio(db_session, turno_id, "recordatorio")
    count = db_session.query(RecordatorioMail).filter(
        RecordatorioMail.turno_id == turno_id).count()
    assert count == 2
