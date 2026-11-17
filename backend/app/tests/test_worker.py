"""Worker tests with C-08 aviso devolucion scenarios."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.domain.notificaciones.outbox import encolar_aviso_devolucion, encolar_confirmacion
from app.domain.notificaciones.tokens import emitir_token_para_recordatorio
from app.infra.db.models import (
    Comprobante,
    Devolucion,
    Odontologo,
    Paciente,
    Pago,
    RecordatorioMail,
    Turno,
    Usuario,
)
from app.infra.smtp.client import SmtpMailer
from app.workers.main import procesar_job


class _FakeMailer(SmtpMailer):
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.llamadas: int = 0
        self.ultimo: dict[str, Any] | None = None

    def enviar(
        self,
        destinatario: str,
        asunto: str,
        texto: str,
        html: str,
        adjuntos: list[tuple[str, bytes, str]] | None = None,
    ) -> None:
        self.llamadas += 1
        self.ultimo = {
            "destinatario": destinatario,
            "asunto": asunto,
            "texto": texto,
            "html": html,
            "adjuntos": adjuntos,
        }
        if self.fail:
            raise ConnectionError("SMTP caído")


def _sembrar(
    db_session: Session, email: str = "ana@ficticia.example.ar"
) -> tuple[Turno, Pago, Devolucion]:
    suf = uuid.uuid4().hex[:8]
    h = "$2b$04$" + "j" * 53
    fecha = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    u = Usuario(
        email=f"od-w-{suf}@clinica-ficticia.example.ar",
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
        estado="cancelado",
        canal="web",
        idempotency_key=f"key-w-{suf}",
    )
    db_session.add(turno)
    db_session.commit()
    pago = Pago(
        turno_id=turno.id,
        odontologo_id=od.id,
        monto=Decimal("10000.00"),
        moneda="ARS",
        proveedor="simulado",
        mp_payment_id=f"sim_pay_{suf}",
        estado="reembolsado_parcial",
        idempotency_key=f"idem-w-{suf}",
    )
    db_session.add(pago)
    db_session.commit()
    dev = Devolucion(
        pago_id=pago.id,
        turno_id=turno.id,
        monto=Decimal("6000.00"),
        porcentaje=60,
        estado="ejecutada",
        idempotency_key=f"dev_{pago.id}",
        mp_refund_id=f"sim_refund_{suf}",
        aprobada_por=u.id,
        aprobada_at=ahora,
        ejecutada_por=u.id,
        ejecutada_at=ahora,
    )
    db_session.add(dev)
    db_session.commit()
    return turno, pago, dev


def _sembrar_confirmacion(db_session: Session) -> tuple[Turno, RecordatorioMail]:
    turno, _, _ = _sembrar(db_session)
    fila = encolar_confirmacion(db_session, turno)
    assert fila is not None
    db_session.commit()
    emitir_token_para_recordatorio(db_session, fila)
    db_session.commit()
    return turno, fila


def test_primer_intento_exitoso_feliz(db_session: Session) -> None:
    _, fila = _sembrar_confirmacion(db_session)
    mailer = _FakeMailer()
    estado = procesar_job(db_session, mailer, str(fila.id))
    assert estado == "enviado" and mailer.llamadas == 1
    db_session.refresh(fila)
    assert fila.estado == "enviado" and fila.enviado_at is not None


def test_ejecucion_encola_aviso_con_adjunto_feliz(db_session: Session) -> None:
    turno, pago, dev = _sembrar(db_session)
    comp = Comprobante(
        pago_id=pago.id,
        devolucion_id=dev.id,
        turno_id=turno.id,
        tipo="recibo_interno",
        concepto="devolucion",
        monto=dev.monto,
        moneda="ARS",
        cae=None,
        simulado=True,
        payload_json={
            "paciente_nombre": "Ana",
            "paciente_apellido": "Ficticia",
            "monto": "6000.00",
        },
    )
    db_session.add(comp)
    db_session.commit()
    db_session.refresh(comp)
    fila = encolar_aviso_devolucion(
        db_session, turno, 60, monto="6000.00", resultado="ejecutada", comprobante_id=comp.id
    )
    assert fila is not None and fila.plantilla_version == "v2"
    db_session.commit()
    mailer = _FakeMailer()
    estado = procesar_job(db_session, mailer, str(fila.id))
    assert estado == "enviado"
    assert mailer.ultimo is not None
    adj = mailer.ultimo["adjuntos"]
    assert adj and adj[0][2] == "application/pdf"
    assert "6000.00" in mailer.ultimo["texto"]


def test_rechazo_aviso_sin_adjunto_negocio(db_session: Session) -> None:
    turno, _, _ = _sembrar(db_session)
    fila = encolar_aviso_devolucion(
        db_session, turno, 60, monto="0.00", resultado="rechazada", comprobante_id=None
    )
    assert fila is not None
    db_session.commit()
    mailer = _FakeMailer()
    estado = procesar_job(db_session, mailer, str(fila.id))
    assert estado == "enviado"
    assert mailer.ultimo is not None
    assert mailer.ultimo["adjuntos"] is None
    texto = mailer.ultimo["texto"].lower()
    assert "no se otorgó" in texto or "no se otorgo" in texto


def test_reintento_ejecucion_no_duplica_aviso_borde(db_session: Session) -> None:
    turno, pago, dev = _sembrar(db_session)
    comp = Comprobante(
        pago_id=pago.id,
        devolucion_id=dev.id,
        turno_id=turno.id,
        tipo="recibo_interno",
        concepto="devolucion",
        monto=dev.monto,
        moneda="ARS",
        cae=None,
        simulado=True,
        payload_json={},
    )
    db_session.add(comp)
    db_session.commit()
    db_session.refresh(comp)
    f1 = encolar_aviso_devolucion(
        db_session, turno, 60, monto="6000.00", resultado="ejecutada", comprobante_id=comp.id
    )
    db_session.commit()
    f2 = encolar_aviso_devolucion(
        db_session, turno, 60, monto="6000.00", resultado="ejecutada", comprobante_id=comp.id
    )
    db_session.commit()
    assert f1 is not None and f2 is not None and str(f1.id) == str(f2.id)
    filas = (
        db_session.query(RecordatorioMail)
        .filter(
            RecordatorioMail.turno_id == turno.id,
            RecordatorioMail.tipo == "aviso_devolucion",
        )
        .all()
    )
    assert len(filas) == 1
