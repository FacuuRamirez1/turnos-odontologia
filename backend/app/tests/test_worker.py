"""Tests C-09 task 5.1/5.2/5.3 — worker y scheduler (RED primero).

Escenarios (U2 feliz / negocio / borde):
- feliz: primer intento exitoso → `enviado` + `enviado_at`;
- negocio: fallo transitorio → `reintentando`, `intentos=1`, `proximo_intento_at`
  ~1 min; error SMTP queda en `ultimo_error`;
- borde: tercer fallo → `fallido`, `intentos=3`, sin retry;
- idempotencia: replay del mismo job no reenvía;
- descartes: fila inexistente / no sendable / reintentando no vencido;
- scheduler: ventana encola exactamente 1; fuera de ventana no encola;
  reintento vencido se re-publica una vez.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.domain.notificaciones.outbox import (
    encolar_recordatorios_ventana,
    republicar_reintentando,
)
from app.domain.notificaciones.tokens import emitir_token_para_recordatorio
from app.infra.db.models import RecordatorioMail, Turno
from app.workers.main import BACKOFF_MINUTOS, MAX_INTENTOS, procesar_job


class _FakeMailer:
    def __init__(self, fail: bool = False, fail_n_veces: int = 0) -> None:
        self.fail = fail
        self.fail_n_veces = fail_n_veces
        self.llamadas: int = 0
        self.ultimo_error: str | None = None

    def enviar(self, destinatario: str, asunto: str, texto: str, html: str) -> None:
        self.llamadas += 1
        if self.fail or self.llamadas <= self.fail_n_veces:
            self.ultimo_error = "SMTP caído"
            raise ConnectionError("SMTP caído")


def _sembrar(
    db_session: Session, email: str = "ana@ficticia.example.ar",
    estado: str = "creado",
) -> Turno:
    import uuid

    from app.infra.db.models import Odontologo, Paciente, Usuario

    h = "$2b$04$" + "j" * 53
    fecha = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    u = Usuario(email=f"od-w-{uuid.uuid4().hex[:8]}@clinica-ficticia.example.ar",
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
                  idempotency_key=f"key-w-{uuid.uuid4().hex[:12]}")
    db_session.add(turno)
    db_session.commit()
    return turno


def _encolar_y_emitir(
    db_session: Session, turno: Turno, tipo: str = "confirmacion",
) -> tuple[RecordatorioMail, str]:
    from app.domain.notificaciones.outbox import encolar_confirmacion, encolar_recordatorio
    fn = encolar_confirmacion if tipo == "confirmacion" else encolar_recordatorio
    fila = fn(db_session, turno)
    assert fila is not None
    db_session.commit()
    token = emitir_token_para_recordatorio(db_session, fila)
    db_session.commit()
    return fila, token


def _factory(db_session: Session) -> Session:
    return sessionmaker(bind=db_session.get_bind(), class_=Session,
                        expire_on_commit=False)()


def test_primer_intento_exitoso_feliz(db_session: Session) -> None:
    """Feliz: job encolado → `enviado`, `enviado_at` seteado, 1 llamada SMTP."""
    turno = _sembrar(db_session)
    fila, _ = _encolar_y_emitir(db_session, turno)
    mailer: Any = _FakeMailer()
    estado = procesar_job(db_session, mailer, str(fila.id))
    assert estado == "enviado"
    assert mailer.llamadas == 1
    db_session.refresh(fila)
    assert fila.estado == "enviado"
    assert fila.enviado_at is not None


def test_fallo_transitorio_reintenta_negocio(db_session: Session) -> None:
    """Negocio: fallo del intento 1 → `reintentando`, `intentos=1`, retry en +1 min."""
    turno = _sembrar(db_session)
    fila, _ = _encolar_y_emitir(db_session, turno)
    mailer: Any = _FakeMailer(fail=True, fail_n_veces=1)  # falla la 1ª vez
    estado = procesar_job(db_session, mailer, str(fila.id))
    assert estado == "fallo"
    db_session.refresh(fila)
    assert fila.estado == "reintentando"
    assert fila.intentos == 1
    assert fila.ultimo_error == "SMTP caído"
    assert fila.proximo_intento_at is not None
    esperado = datetime.now(UTC) + timedelta(minutes=BACKOFF_MINUTOS[0])
    prox = fila.proximo_intento_at
    if prox.tzinfo is not None:
        prox = prox.replace(tzinfo=None)
    if esperado.tzinfo is not None:
        esperado = esperado.replace(tzinfo=None)
    assert abs((prox - esperado).total_seconds()) < 5


def test_tercer_fallo_termina_fallido_borde(db_session: Session) -> None:
    """Borde: 3 fallos → `fallido`, `intentos=3`, sin retry (proximo None)."""
    turno = _sembrar(db_session)
    fila, _ = _encolar_y_emitir(db_session, turno)
    mailer: Any = _FakeMailer(fail=True, fail_n_veces=3)
    # Intento 1: encolado → fallo → reintentando (proximo en el futuro).
    procesar_job(db_session, mailer, str(fila.id))
    db_session.commit()
    db_session.refresh(fila)
    assert fila.estado == "reintentando"
    assert fila.intentos == 1
    # Intento 2: vence el proximo_intento_at → fallo → intentos=2.
    fila.proximo_intento_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.add(fila)
    db_session.commit()
    procesar_job(db_session, mailer, str(fila.id))
    db_session.commit()
    db_session.refresh(fila)
    assert fila.estado == "reintentando"
    assert fila.intentos == 2
    # Intento 3: vence de nuevo → fallo → fallido, intentos=3, sin retry.
    fila.proximo_intento_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.add(fila)
    db_session.commit()
    procesar_job(db_session, mailer, str(fila.id))
    db_session.commit()
    db_session.refresh(fila)
    assert fila.estado == "fallido"
    assert fila.intentos == MAX_INTENTOS
    assert fila.proximo_intento_at is None


def test_replay_no_reenvia_borde(db_session: Session) -> None:
    """Borde: segundo consumo del mismo job no reenvía (ya `enviado`)."""
    turno = _sembrar(db_session)
    fila, _ = _encolar_y_emitir(db_session, turno)
    mailer: Any = _FakeMailer(fail=False)
    procesar_job(db_session, mailer, str(fila.id))
    db_session.commit()
    db_session.refresh(fila)
    assert fila.estado == "enviado"
    llamadas_previas = mailer.llamadas
    procesar_job(db_session, mailer, str(fila.id))
    db_session.commit()
    assert mailer.llamadas == llamadas_previas  # sin reenvío


def test_fila_inexistente_descartada_borde(db_session: Session) -> None:
    """Borde: recordatorio_id inválido → descartado, sin crash."""
    import uuid
    mailer: Any = _FakeMailer(fail=False)
    estado = procesar_job(db_session, mailer, str(uuid.uuid4()))
    assert estado == "descartado-inexistente"
    assert mailer.llamadas == 0


def test_reintentando_no_vencido_descartado_borde(db_session: Session) -> None:
    """Borde: `reintentando` con proximo_intento_at futuro → descartado."""
    turno = _sembrar(db_session)
    fila, _ = _encolar_y_emitir(db_session, turno)
    # Fuerza reintentando con vencimiento futuro
    fila.estado = "reintentando"
    fila.proximo_intento_at = datetime.now(UTC) + timedelta(hours=1)
    db_session.add(fila)
    db_session.commit()
    mailer: Any = _FakeMailer(fail=False)
    estado = procesar_job(db_session, mailer, str(fila.id))
    assert estado == "descartado-no-vencido"
    assert mailer.llamadas == 0


def test_scheduler_ventana_encala_exactamente_uno_feliz(db_session: Session) -> None:
    """Feliz: turno `confirmado` dentro de la ventana → 1 recordatorio."""
    turno = _sembrar(db_session, estado="confirmado")
    # inicio dentro de la ventana (usa ahora mismo)
    ahora = datetime.now(UTC).replace(microsecond=0)
    turno.inicio = ahora
    turno.fin = ahora + timedelta(minutes=30)
    db_session.add(turno)
    db_session.commit()
    creados = encolar_recordatorios_ventana(db_session, ventana_hs=24, ahora=ahora)
    assert len(creados) == 1


def test_scheduler_fuera_ventana_no_encala_negocio(db_session: Session) -> None:
    """Negocio: turno fuera de la ventana → no se crea recordatorio."""
    turno = _sembrar(db_session, estado="confirmado")
    ahora = datetime.now(UTC).replace(microsecond=0)
    turno.inicio = ahora + timedelta(hours=48)  # fuera de 24h
    turno.fin = turno.inicio + timedelta(minutes=30)
    db_session.add(turno)
    db_session.commit()
    creados = encolar_recordatorios_ventana(db_session, ventana_hs=24, ahora=ahora)
    assert len(creados) == 0


def test_reintento_vencido_se_republica_borde(db_session: Session) -> None:
    """Borde: `reintentando` vencido → `republicar_reintentando` lo publica."""
    turno = _sembrar(db_session)
    fila, _ = _encolar_y_emitir(db_session, turno)
    fila.estado = "reintentando"
    fila.proximo_intento_at = datetime.now(UTC) - timedelta(minutes=1)  # vencido
    fila.publicado_at = datetime.now(UTC) - timedelta(hours=1)
    db_session.add(fila)
    db_session.commit()
    republicados = republicar_reintentando(db_session)
    assert len(republicados) == 1
    db_session.refresh(fila)
    assert fila.publicado_at is None  # listo para republicar
