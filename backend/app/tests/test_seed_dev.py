"""Tests C-02 4.1 y C-08 8.1 - seed dev idempotente con datos ficticios."""

import json
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session

from app.infra.db.models import (
    Comprobante,
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
from app.infra.db.seed_dev import (
    ID_COMPROBANTE_DEVOLUCION,
    ID_COMPROBANTE_PAGO,
    ID_DEVOLUCION_EJECUTADA,
    ID_PAGO_APROBADO,
    ID_PAGO_DEVUELTO,
    ID_RECORDATORIO_AVISO_DEVOLUCION,
    ID_TURNO_DEVUELTO,
    ID_TURNO_PAGO_APROBADO,
    seed,
)

DNI_FICTICIO = re.compile(r"^99\.999\.9\d{2}$")
SEED_DATA = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "infra"
    / "db"
    / "seed_data"
    / "feriados_bloqueos_ejemplo.json"
)


def test_seed_idempotente_doble_corrida(db_session: Session) -> None:
    """4.1/8.1: dos corridas -> mismos conteos, cero duplicados."""
    seed(db_session)
    primera = (
        db_session.query(Usuario).count(),
        db_session.query(Odontologo).count(),
        db_session.query(Paciente).count(),
        db_session.query(Turno).count(),
        db_session.query(Pago).count(),
        db_session.query(Devolucion).count(),
        db_session.query(Comprobante).count(),
        db_session.query(EventoPago).count(),
        db_session.query(TurnoHistorial).count(),
        db_session.query(RecordatorioMail).count(),
    )
    assert primera == (4, 2, 5, 2, 2, 1, 2, 7, 6, 1)

    seed(db_session)
    assert (
        db_session.query(Usuario).count(),
        db_session.query(Odontologo).count(),
        db_session.query(Paciente).count(),
        db_session.query(Turno).count(),
        db_session.query(Pago).count(),
        db_session.query(Devolucion).count(),
        db_session.query(Comprobante).count(),
        db_session.query(EventoPago).count(),
        db_session.query(TurnoHistorial).count(),
        db_session.query(RecordatorioMail).count(),
    ) == primera


def test_seed_solo_datos_ficticios(db_session: Session) -> None:
    """P11: pacientes con DNI patron 99.999.9xx y consentimiento completo."""
    seed(db_session)
    pacientes = db_session.query(Paciente).all()
    assert len(pacientes) == 5
    for paciente in pacientes:
        assert DNI_FICTICIO.match(paciente.dni), paciente.dni
        assert paciente.consentimiento_datos is True
        assert isinstance(paciente.consentimiento_fecha, datetime)


def test_seed_montos_distintos_por_odontologo(db_session: Session) -> None:
    """4.1: los 2 odontologos tienen montos distintos (senia 65000 vs 70000)."""
    seed(db_session)
    senias = sorted(o.monto_senia for o in db_session.query(Odontologo).all())
    assert len(senias) == 2 and senias[0] != senias[1]


def test_seed_roles_completos(db_session: Session) -> None:
    """4.1: 2 odontologos + 1 recepcionista + 1 admin, hashes demo no-plaintext."""
    seed(db_session)
    roles = sorted(u.rol for u in db_session.query(Usuario).all())
    assert roles == ["admin", "odontologo", "odontologo", "recepcionista"]
    for usuario in db_session.query(Usuario).all():
        assert len(usuario.password_hash) >= 60


def test_fixture_feriados_bloqueos_valida_para_c04() -> None:
    """4.1: 1 feriado + 1 bloqueo de ejemplo como fixture (tabla bloqueo = C-04)."""
    fixture = json.loads(SEED_DATA.read_text(encoding="utf-8"))
    motivos = [b["motivo"] for b in fixture["bloqueos"]]
    assert motivos.count("feriado") == 1 and motivos.count("bloqueo") == 1
    for bloqueo in fixture["bloqueos"]:
        assert bloqueo["motivo"] in ("pausa", "feriado", "bloqueo", "vacaciones")
        assert bloqueo["desde"] < bloqueo["hasta"]


def test_seed_c08_pago_aprobado_y_devolucion_ejecutada(db_session: Session) -> None:
    """8.1: pago aprobado con recibo y devolucion 60% ejecutada con recibo/aviso."""
    seed(db_session)

    pago_aprobado = db_session.get(Pago, ID_PAGO_APROBADO)
    pago_devuelto = db_session.get(Pago, ID_PAGO_DEVUELTO)
    turno_aprobado = db_session.get(Turno, ID_TURNO_PAGO_APROBADO)
    turno_devuelto = db_session.get(Turno, ID_TURNO_DEVUELTO)
    devolucion = db_session.get(Devolucion, ID_DEVOLUCION_EJECUTADA)
    recibo_pago = db_session.get(Comprobante, ID_COMPROBANTE_PAGO)
    recibo_dev = db_session.get(Comprobante, ID_COMPROBANTE_DEVOLUCION)
    aviso = db_session.get(RecordatorioMail, ID_RECORDATORIO_AVISO_DEVOLUCION)

    assert pago_aprobado is not None and pago_aprobado.estado == "aprobado"
    assert pago_aprobado.proveedor == "simulado"
    assert pago_aprobado.mp_payment_id == "sim_pay_seed_c08_aprobado"
    assert pago_devuelto is not None and pago_devuelto.estado == "reembolsado_parcial"
    assert pago_devuelto.proveedor == "simulado"
    assert pago_devuelto.mp_payment_id == "sim_pay_seed_c08_devuelto"
    assert turno_aprobado is not None and turno_aprobado.estado == "confirmado"
    assert turno_devuelto is not None and turno_devuelto.estado == "devuelto"

    assert devolucion is not None and devolucion.estado == "ejecutada"
    assert devolucion.porcentaje == 60
    assert devolucion.monto == Decimal("39000.00")
    assert devolucion.mp_refund_id == "sim_refund_seed_c08_60"
    assert devolucion.idempotency_key == f"dev_{ID_PAGO_DEVUELTO}"

    assert recibo_pago is not None and recibo_pago.concepto == "pago"
    assert recibo_pago.simulado is True and recibo_pago.tipo == "recibo_interno"
    assert recibo_dev is not None and recibo_dev.concepto == "devolucion"
    assert recibo_dev.simulado is True and recibo_dev.devolucion_id == devolucion.id

    eventos_dev = (
        db_session.query(EventoPago)
        .filter(EventoPago.pago_id == ID_PAGO_DEVUELTO)
        .order_by(EventoPago.created_at)
        .all()
    )
    assert [e.tipo_evento for e in eventos_dev] == [
        "creado",
        "webhook_recibido",
        "devolucion_solicitada",
        "devolucion_aprobada",
        "devolucion_ejecutada",
    ]
    historial_dev = (
        db_session.query(TurnoHistorial)
        .filter(TurnoHistorial.turno_id == ID_TURNO_DEVUELTO)
        .order_by(TurnoHistorial.fecha)
        .all()
    )
    assert [h.estado_nuevo for h in historial_dev] == [
        "creado",
        "confirmado",
        "cancelado",
        "devuelto",
    ]
    assert all(h.actor_tipo and h.fecha for h in historial_dev)

    assert aviso is not None and aviso.tipo == "aviso_devolucion"
    assert aviso.turno_id == ID_TURNO_DEVUELTO
    assert aviso.plantilla_version == "v2"
    assert aviso.contexto_json["resultado"] == "ejecutada"
    assert aviso.contexto_json["porcentaje"] == 60
    assert aviso.contexto_json["monto"] == "39000.00"
