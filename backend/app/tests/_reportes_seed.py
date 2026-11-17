"""Ayudas de siembra para tests de reportes C-12 (DNI ficticios, P11)."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.infra.db.models import (
    Devolucion,
    Odontologo,
    Paciente,
    Pago,
    Turno,
    Usuario,
)
from app.infra.db.models.pago import EventoPago

BASE = datetime(2026, 12, 1, 9, 0, tzinfo=UTC)
DESDE = datetime(2026, 12, 1, 0, 0, tzinfo=UTC)
HASTA = datetime(2026, 12, 31, 23, 59, tzinfo=UTC)


def sembrar_odontologo(db: Session, sufijo: str) -> uuid.UUID:
    usuario = Usuario(
        email=f"od-rep-{sufijo}@clinica-ficticia.example.ar",
        password_hash="$2b$04$" + "b" * 53,
        rol="odontologo",
    )
    db.add(usuario)
    db.commit()
    od = Odontologo(
        user_id=usuario.id, monto_turno=Decimal("70000"), monto_senia=Decimal("10000")
    )
    db.add(od)
    db.commit()
    return uuid.UUID(str(od.id))


def sembrar_paciente(db: Session) -> Paciente:
    pac = Paciente(
        dni=f"76{uuid.uuid4().int % 90000000 + 10000000:08d}",
        nombre="Ana",
        apellido="Ficticia",
        consentimiento_datos=True,
        consentimiento_fecha=datetime(2026, 10, 1, 9, 0, tzinfo=UTC),
    )
    db.add(pac)
    db.commit()
    return pac


def sembrar_turno(
    db: Session,
    od_id: uuid.UUID,
    *,
    estado: str = "confirmado",
    inicio: datetime | None = None,
) -> Turno:
    pac = sembrar_paciente(db)
    ini = inicio or BASE + timedelta(minutes=(uuid.uuid4().int % 1000) * 30)
    turno = Turno(
        paciente_id=pac.id,
        odontologo_id=od_id,
        inicio=ini,
        fin=ini + timedelta(minutes=30),
        estado=estado,
        canal="web",
        idempotency_key=f"key-rep-{uuid.uuid4().hex[:12]}",
    )
    db.add(turno)
    db.commit()
    return turno


def sembrar_pago(
    db: Session,
    turno: Turno,
    *,
    monto: str = "10000.00",
    estado: str = "aprobado",
    creado: datetime | None = None,
) -> Pago:
    pago = Pago(
        turno_id=turno.id,
        odontologo_id=turno.odontologo_id,
        monto=Decimal(monto),
        moneda="ARS",
        proveedor="simulado",
        mp_payment_id=f"sim_pay_{uuid.uuid4()}",
        estado=estado,
        idempotency_key=f"idem-rep-{uuid.uuid4().hex[:12]}",
        created_at=creado or BASE,
    )
    db.add(pago)
    db.commit()
    return pago


def sembrar_evento(db: Session, pago: Pago, tipo: str = "webhook_recibido") -> EventoPago:
    ev = EventoPago(
        pago_id=pago.id,
        tipo_evento=tipo,
        payload_json={"secreto": "no-exportar"},
        actor="sistema",
        created_at=BASE,
    )
    db.add(ev)
    db.commit()
    return ev


def sembrar_devolucion(
    db: Session,
    pago: Pago,
    *,
    monto: str = "6000.00",
    estado: str = "ejecutada",
    ejecutada: datetime | None = None,
) -> Devolucion:
    actor = Usuario(
        email=f"rec-rep-{uuid.uuid4().hex[:8]}@clinica-ficticia.example.ar",
        password_hash="$2b$04$" + "c" * 53,
        rol="recepcionista",
    )
    db.add(actor)
    db.commit()
    cuando = ejecutada or BASE
    dev = Devolucion(
        pago_id=pago.id,
        turno_id=pago.turno_id,
        monto=Decimal(monto),
        porcentaje=60,
        motivo="=cancelación",
        estado=estado,
        idempotency_key=f"dev_{pago.id}_{uuid.uuid4().hex[:6]}",
        mp_refund_id=f"sim_refund_{uuid.uuid4()}" if estado == "ejecutada" else None,
        aprobada_por=actor.id if estado in ("aprobada", "ejecutada") else None,
        aprobada_at=cuando if estado in ("aprobada", "ejecutada") else None,
        ejecutada_por=actor.id if estado == "ejecutada" else None,
        ejecutada_at=cuando if estado == "ejecutada" else None,
    )
    db.add(dev)
    db.commit()
    return dev
