"""Outbox tests including C-08 aviso devolucion (6.3)."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.domain.notificaciones.outbox import encolar_aviso_devolucion, encolar_confirmacion
from app.infra.db.models import Odontologo, Paciente, RecordatorioMail, Turno, Usuario


def _sembrar(db_session: Session, email: str | None = "ana@ficticia.example.ar") -> Turno:
    h = "$2b$04$" + "j" * 53
    fecha = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    u = Usuario(
        email=f"od-ox-{uuid.uuid4().hex[:8]}@clinica-ficticia.example.ar",
        password_hash=h,
        rol="odontologo",
    )
    db_session.add(u)
    db_session.commit()
    od = Odontologo(user_id=u.id, monto_turno=70000, monto_senia=65000)
    db_session.add(od)
    db_session.commit()
    pac = Paciente(
        dni=f"99{uuid.uuid4().int % 90000000 + 10000000:08d}",
        nombre="Ana",
        apellido="Ficticia",
        email=email,
        consentimiento_datos=True,
        consentimiento_fecha=fecha,
    )
    db_session.add(pac)
    db_session.commit()
    ahora = datetime.now(UTC).replace(microsecond=0)
    turno = Turno(
        paciente_id=pac.id,
        odontologo_id=od.id,
        inicio=ahora,
        fin=ahora + timedelta(minutes=30),
        estado="confirmado",
        canal="web",
        idempotency_key=f"key-ox-{uuid.uuid4().hex[:12]}",
    )
    db_session.add(turno)
    db_session.commit()
    return turno


def test_confirmacion_encola_feliz(db_session: Session) -> None:
    turno = _sembrar(db_session)
    fila = encolar_confirmacion(db_session, turno)
    assert fila is not None and fila.estado == "encolado" and fila.destinatario


def test_aviso_devolucion_ejecucion_v2_contexto_feliz(db_session: Session) -> None:
    turno = _sembrar(db_session)
    cid = uuid.uuid4()
    fila = encolar_aviso_devolucion(
        db_session, turno, 60, monto="6000.00", resultado="ejecutada", comprobante_id=cid
    )
    assert fila is not None
    assert fila.tipo == "aviso_devolucion" and fila.plantilla_version == "v2"
    assert fila.contexto_json["resultado"] == "ejecutada"
    assert fila.contexto_json["monto"] == "6000.00"
    assert fila.contexto_json["comprobante_id"] == str(cid)


def test_aviso_devolucion_rechazo_sin_adjunto_negocio(db_session: Session) -> None:
    turno = _sembrar(db_session)
    fila = encolar_aviso_devolucion(
        db_session, turno, 60, monto="0.00", resultado="rechazada", comprobante_id=None
    )
    assert fila is not None
    assert fila.plantilla_version == "v2"
    assert fila.contexto_json["resultado"] == "rechazada"
    assert "comprobante_id" not in fila.contexto_json


def test_aviso_devolucion_idempotente_no_duplica_borde(db_session: Session) -> None:
    turno = _sembrar(db_session)
    f1 = encolar_aviso_devolucion(
        db_session,
        turno,
        60,
        monto="6000.00",
        resultado="ejecutada",
        comprobante_id=uuid.uuid4(),
    )
    f2 = encolar_aviso_devolucion(
        db_session,
        turno,
        60,
        monto="6000.00",
        resultado="ejecutada",
        comprobante_id=uuid.uuid4(),
    )
    assert f1 is not None and f2 is not None and str(f1.id) == str(f2.id)
    assert (
        db_session.query(RecordatorioMail)
        .filter(
            RecordatorioMail.turno_id == turno.id,
            RecordatorioMail.tipo == "aviso_devolucion",
        )
        .count()
        == 1
    )
