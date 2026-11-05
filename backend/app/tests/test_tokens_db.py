"""Tests C-09 task 2.1/2.2 — tokens de acción un solo uso en DB (RED primero).

Escenarios (U2 feliz / negocio / borde):
- feliz: primer uso válido del token consume y devuelve la fila;
- negocio: reuso del mismo token es rechazado sin cambios de estado;
- borde: token expirado es rechazado; el hash se guarda, nunca el raw.
No depende de ActionTokenStore ni de Redis (regla de un uso en DB).
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.security.action_tokens import issue_action_token
from app.core.settings import get_settings
from app.domain.notificaciones.tokens import (
    consumir_token_db,
    token_hash_raw,
)
from app.infra.db.models import RecordatorioMail

SECRET = "secreto-de-test-ficticio"


def _crear_fila(db_session: Session, turno_id: uuid.UUID) -> RecordatorioMail:
    fila = RecordatorioMail(turno_id=turno_id, tipo="confirmacion",
                            destinatario="a@b.c", estado="encolado")
    db_session.add(fila)
    db_session.commit()
    return fila


def test_primer_uso_valido_consume_feliz(db_session: Session) -> None:
    """Feliz: token sin usar, emisión + consumo DB devuelve la fila."""
    from app.core.security.jwt import decode_and_validate
    turno_id = _sembrar_turno(db_session)
    fila = _crear_fila(db_session, turno_id)
    token = issue_action_token(str(fila.id), "mail_accion", secret=SECRET,
                               action_min=get_settings().mail_action_ttl_min)
    fila.token_accion_hash = token_hash_raw(token)
    fila.token_expira_at = datetime.now(UTC) + timedelta(minutes=30)
    db_session.add(fila)
    db_session.commit()

    claims = decode_and_validate(token, "action", SECRET)
    assert claims["type"] == "action"
    consumida = consumir_token_db(db_session, token)
    assert consumida is not None
    assert consumida.token_usado_at is not None


def test_reuso_mismo_token_rechazado_negocio(db_session: Session) -> None:
    """Negocio: segundo consumo del mismo token devuelve None sin cambios."""
    turno_id = _sembrar_turno(db_session)
    fila = _crear_fila(db_session, turno_id)
    token = issue_action_token(str(fila.id), "mail_accion", secret=SECRET,
                               action_min=get_settings().mail_action_ttl_min)
    fila.token_accion_hash = token_hash_raw(token)
    fila.token_expira_at = datetime.now(UTC) + timedelta(minutes=30)
    db_session.add(fila)
    db_session.commit()

    primera = consumir_token_db(db_session, token)
    assert primera is not None
    segunda = consumir_token_db(db_session, token)
    assert segunda is None  # ya usado → rechazar


def test_token_expirado_rechazado_borde(db_session: Session) -> None:
    """Borde: token con expira_at pasado es rechazado por DB."""
    turno_id = _sembrar_turno(db_session)
    fila = _crear_fila(db_session, turno_id)
    token = issue_action_token(str(fila.id), "mail_accion", secret=SECRET,
                               action_min=get_settings().mail_action_ttl_min)
    fila.token_accion_hash = token_hash_raw(token)
    fila.token_expira_at = datetime.now(UTC) - timedelta(minutes=5)  # ya expiró
    db_session.add(fila)
    db_session.commit()

    assert consumir_token_db(db_session, token) is None


def test_hash_guardado_nunca_raw_borde(db_session: Session) -> None:
    """Borde: solo se persiste sha256, nunca el token crudo."""
    turno_id = _sembrar_turno(db_session)
    fila = _crear_fila(db_session, turno_id)
    token = issue_action_token(str(fila.id), "mail_accion", secret=SECRET,
                               action_min=get_settings().mail_action_ttl_min)
    fila.token_accion_hash = token_hash_raw(token)
    fila.token_expira_at = datetime.now(UTC) + timedelta(hours=1)
    db_session.add(fila)
    db_session.commit()
    persistido = (
        db_session.query(RecordatorioMail).filter(
            RecordatorioMail.id == fila.id).first()
    )
    assert persistido is not None
    assert persistido.token_accion_hash == token_hash_raw(token)
    assert persistido.token_accion_hash != token  # nunca el raw


def _sembrar_turno(db_session: Session) -> uuid.UUID:
    import uuid
    from datetime import UTC, datetime

    from app.infra.db.models import Odontologo, Paciente, Turno, Usuario

    h = "$2b$04$" + "j" * 53
    fecha = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    u = Usuario(email=f"od-tk-{uuid.uuid4().hex[:8]}@clinica-ficticia.example.ar",
                password_hash=h, rol="odontologo")
    db_session.add(u)
    db_session.commit()
    od = Odontologo(user_id=u.id, monto_turno=70000, monto_senia=65000)
    db_session.add(od)
    db_session.commit()
    pac = Paciente(dni=f"99{uuid.uuid4().int % 90000000 + 10000000:08d}",
                   nombre="Ana", apellido="Ficticia", email="ana@ficticia.example.ar",
                   consentimiento_datos=True, consentimiento_fecha=fecha)
    db_session.add(pac)
    db_session.commit()
    ahora = datetime.now(UTC).replace(microsecond=0)
    turno = Turno(paciente_id=pac.id, odontologo_id=od.id, inicio=ahora,
                  fin=ahora + timedelta(minutes=30), estado="creado", canal="web",
                  idempotency_key=f"key-tk-{uuid.uuid4().hex[:12]}")
    db_session.add(turno)
    db_session.commit()
    return turno.id
