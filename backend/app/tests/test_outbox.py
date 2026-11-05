"""Tests C-09 task 4.1/4.2/4.3/4.4 — outbox transaccional (RED primero).

Escenarios (U2 feliz / negocio / borde):
- feliz: primer encolado crea `encolado`; segundo no duplica; tipos
  distintos conviven;
- negocio: paciente sin email → fila `fallido`, no se publica, visible en
  métricas;
- borde: `publicar_pendientes` no re-publica una fila ya publicada;
- hook: `transition()` `creado→confirmado` actor sistema deja outbox en el
  mismo commit; rollback no deja huérfano; otras transiciones no generan
  confirmación.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.domain.notificaciones.outbox import (
    encolar_confirmacion,
    encolar_recordatorio,
    publicar_pendientes,
)
from app.domain.turnos.estados import transition
from app.infra.db.models import Turno


def _sembrar(
    db_session: Session, email: str | None = "ana@ficticia.example.ar",
    estado: str = "creado",
) -> Turno:
    import uuid

    from app.infra.db.models import Odontologo, Paciente, Turno, Usuario

    h = "$2b$04$" + "j" * 53
    fecha = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    u = Usuario(email=f"od-ox-{uuid.uuid4().hex[:8]}@clinica-ficticia.example.ar",
                password_hash=h, rol="odontologo")
    db_session.add(u)
    db_session.commit()
    od = Odontologo(user_id=u.id, monto_turno=70000, monto_senia=65000)
    db_session.add(od)
    db_session.commit()
    pac = Paciente(dni=f"99{uuid.uuid4().int % 90000000 + 10000000:08d}",
                   nombre="Ana", apellido="Ficticia", email=email,
                   consentimiento_datos=True, consentimiento_fecha=fecha)
    db_session.add(pac)
    db_session.commit()
    ahora = datetime.now(UTC).replace(microsecond=0)
    turno = Turno(paciente_id=pac.id, odontologo_id=od.id, inicio=ahora,
                  fin=ahora + timedelta(minutes=30), estado=estado, canal="web",
                  idempotency_key=f"key-ox-{uuid.uuid4().hex[:12]}")
    db_session.add(turno)
    db_session.commit()
    return turno


def _contar(db_session: Session, tipo: str | None = None) -> int:
    from app.infra.db.models import RecordatorioMail
    q = db_session.query(RecordatorioMail)
    if tipo:
        q = q.filter(RecordatorioMail.tipo == tipo)
    return q.count()


def test_primer_encolado_crea_encolado_feliz(db_session: Session) -> None:
    """Feliz: encolar_confirmacion crea una fila `encolado` con token hash."""
    turno = _sembrar(db_session)
    fila = encolar_confirmacion(db_session, turno)
    assert fila is not None
    assert fila.estado == "encolado"
    assert fila.intentos == 0
    assert fila.destinatario == "ana@ficticia.example.ar"
    assert fila.token_accion_hash is not None
    assert len(fila.token_accion_hash) == 64


def test_segundo_encolado_no_duplica_negocio(db_session: Session) -> None:
    """Negocio: mismo (turno, tipo) devuelve la existente sin duplicar."""
    turno = _sembrar(db_session)
    f1 = encolar_confirmacion(db_session, turno)
    f2 = encolar_confirmacion(db_session, turno)
    assert f1 is not None and f2 is not None
    assert str(f2.id) == str(f1.id)
    assert _contar(db_session, "confirmacion") == 1


def test_tipos_distintos_conviven_feliz(db_session: Session) -> None:
    """Feliz: confirmacion y recordatorio sobre el mismo turno son 2 filas."""
    turno = _sembrar(db_session)
    encolar_confirmacion(db_session, turno)
    encolar_recordatorio(db_session, turno)
    assert _contar(db_session) == 2


def test_sin_email_fallido_no_se_publica_negocio(db_session: Session) -> None:
    """Negocio: paciente sin email → `fallido`, intentos=0, sin publicado_at."""
    turno = _sembrar(db_session, email=None)
    fila = encolar_confirmacion(db_session, turno)
    assert fila is not None
    assert fila.estado == "fallido"
    assert fila.intentos == 0
    assert fila.destinatario == ""
    assert fila.ultimo_error == "paciente sin email"
    assert fila.publicado_at is None


def test_fallido_visible_en_metricas_negocio(db_session: Session) -> None:
    """Negocio: el fallo por falta de email se cuenta en métricas."""
    from app.domain.notificaciones.metricas import contar_por_estado
    _sembrar(db_session, email=None)
    encolar_confirmacion(db_session, _sembrar(db_session, email=None))
    conteo = contar_por_estado(db_session)
    assert conteo["fallido"] >= 1


def test_email_presente_encola_feliz(db_session: Session) -> None:
    """Borde: email presente → `encolado` (candidato a la cola)."""
    turno = _sembrar(db_session, email="a@b.c")
    fila = encolar_recordatorio(db_session, turno)
    assert fila is not None
    assert fila.estado == "encolado"


def test_publicar_pendientes_no_duplica(db_session: Session) -> None:
    """Borde: una fila ya publicada no se re-publica ni se envía dos veces."""
    turno = _sembrar(db_session)
    encolar_confirmacion(db_session, turno)
    primeros = publicar_pendientes(db_session)
    db_session.commit()
    segundos = publicar_pendientes(db_session)
    assert len(segundos) == 0  # ya publicados → nada
    assert len(primeros) == 1


def test_hook_creado_confirmado_mismo_commit_feliz(db_session: Session) -> None:
    """Feliz: transición `creado→confirmado` por sistema deja outbox en el commit."""
    turno = _sembrar(db_session)
    transition(db_session, turno.id, "confirmado", actor_tipo="sistema",
               actor_id="sistema", motivo="aprobado")
    db_session.commit()
    from app.infra.db.models import RecordatorioMail
    filas = db_session.query(RecordatorioMail).filter(
        RecordatorioMail.turno_id == turno.id).all()
    assert len(filas) == 1
    assert filas[0].tipo == "confirmacion"
    assert filas[0].estado == "encolado"


def test_rollback_no_deja_outbox_huerfano_negocio(db_session: Session) -> None:
    """Negocio: rollback de la transición no deja outbox huérfano."""
    turno = _sembrar(db_session)
    # Fuerza un error tras encolar: viola UNIQUE del turno (mismo idempotency no,
    # usamos una FK inválida para que el commit falle). Más simple: haga un
    # rollback explícito y verifique que no hay recordatorio.
    transition(db_session, turno.id, "confirmado", actor_tipo="sistema",
               actor_id="sistema", motivo="aprobado")
    db_session.rollback()
    from app.infra.db.models import RecordatorioMail
    filas = db_session.query(RecordatorioMail).filter(
        RecordatorioMail.turno_id == turno.id).all()
    assert len(filas) == 0


def test_otras_transiciones_no_generan_confirmacion_borde(db_session: Session) -> None:
    """Borde: `confirmado→atendido` no crea `confirmacion` automática."""
    turno = _sembrar(db_session, estado="confirmado")
    transition(db_session, turno.id, "atendido", actor_tipo="odontologo",
               actor_id="od-1", motivo="asistió")
    db_session.commit()
    from app.infra.db.models import RecordatorioMail
    filas = db_session.query(RecordatorioMail).filter(
        RecordatorioMail.turno_id == turno.id).all()
    assert len(filas) == 0
