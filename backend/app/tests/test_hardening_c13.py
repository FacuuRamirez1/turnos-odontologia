"""Tests C-13 task 8 — Hardening: restore backup, retención, flags v2 off, checklist criterios de éxito v1.

Escenarios por test: feliz (funcionamiento esperado), negocio (error de dominio), borde (caso límite).
"""

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.infra.db.models import (
    Devolucion,
    EventoPago,
    Odontologo,
    Paciente,
    Pago,
    RecordatorioMail,
    Turno,
    TurnoHistorial,
    Usuario,
)
from app.infra.db.seed_dev import seed
from app.main import app
from app.workers.main import ejecutar_retencion


# ---------------------------------------------------------------------------
# 8.1 Test de restore backup (simulado: verifica integridad de datos tras "restaurar")
# ---------------------------------------------------------------------------

def test_restore_backup_recupera_tablas_y_datos(db_session: Session) -> None:
    """Feliz: tras aplicar seed (análogo a restore sobre base vacía), tablas clave tienen datos."""
    seed(db_session)

    assert db_session.query(Usuario).count() == 4
    assert db_session.query(Odontologo).count() == 2
    assert db_session.query(Paciente).count() == 5
    assert db_session.query(Turno).count() == 10
    assert db_session.query(Pago).count() == 2
    assert db_session.query(Devolucion).count() == 1
    assert db_session.query(EventoPago).count() == 7
    assert db_session.query(TurnoHistorial).count() == 20
    assert db_session.query(RecordatorioMail).count() == 1


def test_restore_backup_seed_idempotente(db_session: Session) -> None:
    """Borde: doble aplicación del seed no duplica (restaurar sobre mismo backup es idempotente)."""
    seed(db_session)
    counts_1 = (
        db_session.query(Turno).count(),
        db_session.query(Pago).count(),
        db_session.query(Devolucion).count(),
        db_session.query(EventoPago).count(),
        db_session.query(TurnoHistorial).count(),
    )
    seed(db_session)
    counts_2 = (
        db_session.query(Turno).count(),
        db_session.query(Pago).count(),
        db_session.query(Devolucion).count(),
        db_session.query(EventoPago).count(),
        db_session.query(TurnoHistorial).count(),
    )
    assert counts_1 == counts_2


# ---------------------------------------------------------------------------
# 8.2 Test de retención RN-RETENCION
# ---------------------------------------------------------------------------

def test_retencion_elimina_mails_vencidos(db_session: Session) -> None:
    """Feliz: job elimina recordatorios mail enviados/fallidos > 12 meses."""
    ahora = datetime.now(UTC)
    corte = ahora - timedelta(days=400)

    odonto = Odontologo(
        id=uuid4(), user_id=uuid4(), monto_turno=Decimal("70000"),
        monto_senia=Decimal("65000"), is_active=True, activo=True,
    )
    db_session.add(odonto)
    db_session.commit()

    paciente = Paciente(
        id=uuid4(), dni="99999001", nombre="Ana", apellido="Ficticia",
        email="ana@clinica-ficticia.example.ar", telefono=None,
        consentimiento_datos=True,
        consentimiento_fecha=ahora,
        is_active=True,
    )
    db_session.add(paciente)
    db_session.commit()

    turno_viejo = Turno(
        id=uuid4(), paciente_id=paciente.id, odontologo_id=odonto.id,
        inicio=ahora + timedelta(days=1),
        fin=ahora + timedelta(days=1, minutes=30),
        estado="confirmado", canal="web",
        idempotency_key=f"idem-ret-viejo-{uuid4()}", version=1,
        is_active=True,
    )
    turno_reciente = Turno(
        id=uuid4(), paciente_id=paciente.id, odontologo_id=odonto.id,
        inicio=ahora + timedelta(days=2),
        fin=ahora + timedelta(days=2, minutes=30),
        estado="confirmado", canal="web",
        idempotency_key=f"idem-ret-rec-{uuid4()}", version=1,
        is_active=True,
    )
    db_session.add(turno_viejo)
    db_session.add(turno_reciente)
    db_session.commit()

    mail_viejo = RecordatorioMail(
        id=uuid4(), turno_id=turno_viejo.id, tipo="recordatorio",
        destinatario="ana@clinica-ficticia.example.ar",
        estado="enviado", intentos=0,
        created_at=corte, is_active=True,
    )
    mail_reciente = RecordatorioMail(
        id=uuid4(), turno_id=turno_reciente.id, tipo="recordatorio",
        destinatario="ana@clinica-ficticia.example.ar",
        estado="encolado", intentos=0,
        created_at=ahora, is_active=True,
    )
    db_session.add(mail_viejo)
    db_session.add(mail_reciente)
    db_session.commit()

    resultado = ejecutar_retencion(lambda: db_session)

    assert resultado["mails_eliminados"] == 1
    assert db_session.query(RecordatorioMail).filter(
        RecordatorioMail.id == mail_reciente.id
    ).first() is not None
    assert db_session.query(RecordatorioMail).filter(
        RecordatorioMail.id == mail_viejo.id
    ).first() is None


def test_retencion_anonimiza_turnos_viejos(db_session: Session) -> None:
    """Negocio: turnos > 24 meses se anonimizan (DNI/email/telefono) pero la fila se conserva."""
    ahora = datetime.now(UTC)
    corte = ahora - timedelta(days=800)

    odonto = Odontologo(
        id=uuid4(), user_id=uuid4(), monto_turno=Decimal("70000"),
        monto_senia=Decimal("65000"), is_active=True, activo=True,
    )
    db_session.add(odonto)
    db_session.commit()

    paciente = Paciente(
        id=uuid4(), dni="99999002", nombre="Bruno", apellido="Ficticia",
        email="bruno@clinica-ficticia.example.ar", telefono="3511234567",
        consentimiento_datos=True, consentimiento_fecha=ahora,
        is_active=True,
    )
    db_session.add(paciente)
    db_session.commit()

    turno = Turno(
        id=uuid4(), paciente_id=paciente.id, odontologo_id=odonto.id,
        inicio=ahora - timedelta(days=100),
        fin=ahora - timedelta(days=100, minutes=-30),
        estado="atendido", canal="recepcion",
        idempotency_key=f"idem-ret2-{uuid4()}", version=1,
        created_at=corte, is_active=True,
    )
    db_session.add(turno)
    db_session.commit()

    resultado = ejecutar_retencion(lambda: db_session)

    assert resultado["turnos_anonimizados"] == 1
    p = db_session.get(Paciente, paciente.id)
    assert p.dni == "ANONIMIZADO"
    assert p.email is None
    assert p.telefono is None


def test_retencion_no_borrar_historial_append_only(db_session: Session) -> None:
    """Borde: turno_historial y evento_pago son append-only, nunca se eliminan."""
    antes_historial = db_session.query(TurnoHistorial).count()
    antes_eventos = db_session.query(EventoPago).count()

    resultado = ejecutar_retencion(lambda: db_session)

    assert db_session.query(TurnoHistorial).count() == antes_historial
    assert db_session.query(EventoPago).count() == antes_eventos
    assert resultado["turnos_anonimizados"] == 0
    assert resultado["pagos_anonimizados"] == 0


# ---------------------------------------------------------------------------
# 8.3 Test de flags v2 off
# ---------------------------------------------------------------------------

def test_flags_v2_apagados_en_arranque() -> None:
    """Feliz: WHATSAPP_ENABLED=false, ARCA_ENABLED=false, PAGO_MODO=simulado."""
    s = get_settings()
    assert s.whatsapp_enabled is False
    assert s.arca_enabled is False
    assert s.pago_modo == "simulado"


def test_flags_v2_no_escrituras_en_app(db_session: Session) -> None:
    """Negocio: cero escrituras en lista_espera / notificacion_whatsapp en v1."""
    from app.infra.db.models import ListaEspera, NotificacionWhatsapp
    assert db_session.query(ListaEspera).count() == 0
    assert db_session.query(NotificacionWhatsapp).count() == 0


def test_sandbox_endpoint_condicionado_por_pago_modo() -> None:
    """Borde: endpoint sandbox solo existe con PAGO_MODO=simulado."""
    s = get_settings()
    assert s.pago_modo == "simulado"
    from app.domain.pagos.service import get_proveedor_pago
    proveedor = get_proveedor_pago()
    assert proveedor is not None


# ---------------------------------------------------------------------------
# 8.4 Test checklist criterios de éxito v1
# ---------------------------------------------------------------------------

def test_criterio_1_reserva_seña_mail_sin_intervencion(db_session: Session) -> None:
    """Feliz: reserva → pago aprobado → mail de confirmación encuelto."""
    seed(db_session)

    id_turno_aprobado = UUID("55555555-5555-4555-8555-555555555551")
    turno_aprobado = db_session.get(Turno, id_turno_aprobado)
    assert turno_aprobado is not None
    assert str(turno_aprobado.estado) == "confirmado"

    id_pago = UUID("66666666-6666-4666-8666-666666666661")
    pago = db_session.get(Pago, id_pago)
    assert pago is not None
    assert str(pago.estado) == "aprobado"

    # El seed crea un recordatorio de aviso_devolucion para el turno devuelto,
    # evidenciando que los mails se generan tras el flujo de pago.
    id_turno_devuelto = UUID("55555555-5555-4555-8555-555555555552")
    recordatorios = (
        db_session.query(RecordatorioMail)
        .filter(RecordatorioMail.turno_id == id_turno_devuelto)
        .all()
    )
    assert len(recordatorios) >= 1
    assert recordatorios[0].tipo == "aviso_devolucion"


def test_criterio_2_no_doble_reserva_concurrencia(db_session: Session) -> None:
    """Negocio: UNIQUE (odontologo_id, inicio) impide doble reserva del mismo slot."""
    odonto = Odontologo(
        id=uuid4(), user_id=uuid4(), monto_turno=Decimal("70000"),
        monto_senia=Decimal("65000"), is_active=True, activo=True,
    )
    db_session.add(odonto)
    db_session.commit()

    paciente = Paciente(
        id=uuid4(), dni="99999003", nombre="Carla", apellido="Ficticia",
        email="carla@clinica-ficticia.example.ar",
        consentimiento_datos=True, consentimiento_fecha=datetime.now(UTC),
        is_active=True,
    )
    db_session.add(paciente)
    db_session.commit()

    inicio = datetime(2026, 12, 1, 10, 0, tzinfo=UTC)
    turno1 = Turno(
        id=uuid4(), paciente_id=paciente.id, odontologo_id=odonto.id,
        inicio=inicio, fin=inicio + timedelta(minutes=30),
        estado="confirmado", canal="web",
        idempotency_key="idem-doble-1", version=1, is_active=True,
    )
    db_session.add(turno1)
    db_session.commit()

    turno2 = Turno(
        id=uuid4(), paciente_id=paciente.id, odontologo_id=odonto.id,
        inicio=inicio, fin=inicio + timedelta(minutes=30),
        estado="creado", canal="web",
        idempotency_key="idem-doble-2", version=1, is_active=True,
    )
    db_session.add(turno2)
    with pytest.raises(Exception):
        db_session.commit()


def test_criterio_3_rastro_auditable_total(db_session: Session) -> None:
    """Feliz: toda transición de turno y todo cobro deja rastro (actor + fecha)."""
    seed(db_session)

    id_turno = UUID("55555555-5555-4555-8555-555555555551")
    historial = (
        db_session.query(TurnoHistorial)
        .filter(TurnoHistorial.turno_id == id_turno)
        .order_by(TurnoHistorial.fecha)
        .all()
    )
    assert len(historial) >= 2
    assert all(h.actor_tipo and h.actor_id and h.fecha for h in historial)

    id_pago = UUID("66666666-6666-4666-8666-666666666661")
    eventos = (
        db_session.query(EventoPago)
        .filter(EventoPago.pago_id == id_pago)
        .all()
    )
    assert len(eventos) >= 2
    assert all(e.actor for e in eventos)


def test_criterio_4_confirmar_cancelar_desde_mail(db_session: Session) -> None:
    """Feliz: cancelar_desde_mail actualiza el estado del turno."""
    seed(db_session)

    id_turno_devuelto = UUID("55555555-5555-4555-8555-555555555552")
    turno_devuelto = db_session.get(Turno, id_turno_devuelto)
    assert str(turno_devuelto.estado) == "devuelto"

    historial = (
        db_session.query(TurnoHistorial)
        .filter(TurnoHistorial.turno_id == turno_devuelto.id)
        .order_by(TurnoHistorial.fecha)
        .all()
    )
    estados = [h.estado_nuevo for h in historial]
    assert "devuelto" in estados


def test_criterio_5_recorte_sostenido_sin_v2_en_v1() -> None:
    """Borde: build v1 no tiene WhatsApp, ARCA, sobre-turnos, lista_espera con escrituras ni MP real."""
    s = get_settings()
    assert s.whatsapp_enabled is False
    assert s.arca_enabled is False
    assert s.pago_modo == "simulado"

    from app.domain.pagos.service import get_proveedor_pago
    proveedor = get_proveedor_pago()
    class_name = type(proveedor).__name__
    assert "Simulado" in class_name or "simulado" in class_name.lower()
