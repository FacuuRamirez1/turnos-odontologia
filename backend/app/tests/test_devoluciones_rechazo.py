"""Tests C-08 task 3.4 — rechazo con motivo obligatorio (RED primero).

Escenarios (U2 feliz / negocio / borde):
- feliz: rechazar una `pendiente` con motivo → `rechazada` + actor/fecha/motivo
  + `evento_pago(devolucion_rechazada)`; turno sigue `cancelado` y pago
  `aprobado` sin cambios;
- negocio: motivo vacío o solo espacios → 422 y sigue `pendiente`; odontólogo
  ajeno → 403 sin evento;
- borde: rechazar `aprobada|ejecutada|rechazada` → 409
  `TRANSICION_DEVOLUCION_INVALIDA` sin cambios (terminal).
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security.jwt import create_access_token
from app.infra.db.models import (
    Devolucion,
    EventoPago,
    Odontologo,
    Paciente,
    Pago,
    Turno,
    Usuario,
)
from app.tests.conftest import TEST_AUTH_SECRET


def _sembrar_odontologo(db_session: Session, sufijo: str) -> uuid.UUID:
    u = Usuario(
        email=f"od-rech-{sufijo}@clinica-ficticia.example.ar",
        password_hash="$2b$04$" + "r" * 53,
        rol="odontologo",
    )
    db_session.add(u)
    db_session.commit()
    od = Odontologo(
        user_id=u.id, monto_turno=Decimal("70000"), monto_senia=Decimal("10000")
    )
    db_session.add(od)
    db_session.commit()
    return uuid.UUID(str(od.id))


def _sembrar_usuario(db_session: Session, rol: str) -> Usuario:
    u = Usuario(
        email=f"{rol}-rech-{uuid.uuid4().hex[:8]}@clinica-ficticia.example.ar",
        password_hash="$2b$04$" + "u" * 53,
        rol=rol,
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


def _sembrar_devolucion(
    db_session: Session,
    od_id: uuid.UUID,
    *,
    estado: str = "pendiente",
    actor_id: uuid.UUID | None = None,
) -> Devolucion:
    suf = uuid.uuid4().hex[:8]
    pac = Paciente(
        dni=f"74{uuid.uuid4().int % 90000000 + 10000000:08d}",
        nombre="Ana",
        apellido="Ficticia",
        consentimiento_datos=True,
        consentimiento_fecha=datetime(2026, 10, 1, 9, 0, tzinfo=UTC),
    )
    db_session.add(pac)
    db_session.commit()
    inicio = datetime(2026, 12, 1, 9, 0, tzinfo=UTC) + timedelta(
        minutes=(uuid.uuid4().int % 2000) * 30
    )
    turno = Turno(
        paciente_id=pac.id,
        odontologo_id=od_id,
        inicio=inicio,
        fin=inicio + timedelta(minutes=30),
        estado="cancelado",
        canal="web",
        idempotency_key=f"key-rech-{suf}",
    )
    db_session.add(turno)
    db_session.commit()
    pago = Pago(
        turno_id=turno.id,
        odontologo_id=od_id,
        monto=Decimal("10000.00"),
        moneda="ARS",
        proveedor="simulado",
        mp_payment_id=f"sim_pay_{uuid.uuid4()}",
        estado="aprobado",
        idempotency_key=f"idem-rech-{suf}",
    )
    db_session.add(pago)
    db_session.commit()
    ahora = datetime.now(UTC)
    dev = Devolucion(
        pago_id=pago.id,
        turno_id=turno.id,
        monto=Decimal("6000.00"),
        porcentaje=60,
        motivo="cancelación",
        estado=estado,
        idempotency_key=f"dev_{pago.id}",
    )
    if estado in ("aprobada", "ejecutada"):
        dev.aprobada_por = actor_id
        dev.aprobada_at = ahora
    if estado == "rechazada":
        dev.rechazada_por = actor_id
        dev.rechazada_at = ahora
        dev.motivo_rechazo = "duplicado"
    if estado == "ejecutada":
        dev.ejecutada_por = actor_id
        dev.ejecutada_at = ahora
        dev.mp_refund_id = f"sim_refund_{uuid.uuid4()}"
    db_session.add(dev)
    db_session.commit()
    db_session.refresh(dev)
    return dev


def _headers(rol: str, *, sub: str, odontologo_id: uuid.UUID | None = None) -> dict[str, str]:
    token = create_access_token(
        sub=sub,
        rol=rol,
        secret=TEST_AUTH_SECRET,
        odontologo_id=str(odontologo_id) if odontologo_id else None,
    )
    return {"Authorization": f"Bearer {token}"}


def _eventos(db_session: Session, dev: Devolucion, tipo: str) -> list[EventoPago]:
    return (
        db_session.query(EventoPago)
        .filter(EventoPago.pago_id == dev.pago_id, EventoPago.tipo_evento == tipo)
        .all()
    )


def test_rechazo_feliz_registra_actor_motivo_y_no_altera_pago_ni_turno(
    auth_client: TestClient, db_session: Session
) -> None:
    """Feliz: rechazo con motivo; turno `cancelado` y pago `aprobado` intactos."""
    od_a = _sembrar_odontologo(db_session, "a")
    rec = _sembrar_usuario(db_session, "recepcionista")
    dev = _sembrar_devolucion(db_session, od_a)

    r = auth_client.post(
        f"/api/devoluciones/{dev.id}/rechazar",
        json={"motivo": "pago duplicado verificado"},
        headers=_headers("recepcionista", sub=str(rec.id)),
    )

    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "rechazada"
    assert r.json()["marca"] == "(simulado)"

    db_session.expire_all()
    recargada = db_session.get(Devolucion, dev.id)
    assert recargada is not None
    assert str(recargada.estado) == "rechazada"
    assert uuid.UUID(str(recargada.rechazada_por)) == uuid.UUID(str(rec.id))
    assert recargada.rechazada_at is not None
    assert recargada.motivo_rechazo == "pago duplicado verificado"

    eventos = _eventos(db_session, dev, "devolucion_rechazada")
    assert len(eventos) == 1
    assert eventos[0].actor == "recepcionista"
    assert eventos[0].payload_json["actor_id"] == str(rec.id)
    assert eventos[0].payload_json["motivo"] == "pago duplicado verificado"

    turno = db_session.get(Turno, dev.turno_id)
    pago = db_session.get(Pago, dev.pago_id)
    assert turno is not None and str(turno.estado) == "cancelado"
    assert pago is not None and str(pago.estado) == "aprobado"


@pytest.mark.parametrize("motivo", ["", "   "])
def test_motivo_vacio_422_sin_cambio_negocio(
    auth_client: TestClient, db_session: Session, motivo: str
) -> None:
    """Negocio: motivo vacío o solo espacios → 422; sigue pendiente sin evento."""
    od_a = _sembrar_odontologo(db_session, f"a-{len(motivo)}")
    rec = _sembrar_usuario(db_session, "recepcionista")
    dev = _sembrar_devolucion(db_session, od_a)

    r = auth_client.post(
        f"/api/devoluciones/{dev.id}/rechazar",
        json={"motivo": motivo},
        headers=_headers("recepcionista", sub=str(rec.id)),
    )

    assert r.status_code == 422, r.text
    db_session.expire_all()
    recargada = db_session.get(Devolucion, dev.id)
    assert recargada is not None and str(recargada.estado) == "pendiente"
    assert recargada.rechazada_por is None
    assert _eventos(db_session, dev, "devolucion_rechazada") == []


def test_odontologo_ajeno_403_sin_evento_negocio(
    auth_client: TestClient, db_session: Session
) -> None:
    """Negocio (P8): odontólogo A no rechaza la devolución de B."""
    od_a = _sembrar_odontologo(db_session, "a3")
    od_b = _sembrar_odontologo(db_session, "b3")
    dev = _sembrar_devolucion(db_session, od_b)

    r = auth_client.post(
        f"/api/devoluciones/{dev.id}/rechazar",
        json={"motivo": "intento ajeno"},
        headers=_headers("odontologo", sub=str(uuid.uuid4()), odontologo_id=od_a),
    )

    assert r.status_code == 403
    db_session.expire_all()
    recargada = db_session.get(Devolucion, dev.id)
    assert recargada is not None and str(recargada.estado) == "pendiente"
    assert _eventos(db_session, dev, "devolucion_rechazada") == []


@pytest.mark.parametrize("estado", ["aprobada", "ejecutada", "rechazada"])
def test_rechazar_resuelta_409_sin_cambio_borde(
    auth_client: TestClient, db_session: Session, estado: str
) -> None:
    """Borde: rechazar una devolución ya resuelta → 409, sin evento."""
    od_a = _sembrar_odontologo(db_session, f"a-{estado}")
    rec = _sembrar_usuario(db_session, "recepcionista")
    dev = _sembrar_devolucion(
        db_session, od_a, estado=estado, actor_id=uuid.UUID(str(rec.id))
    )
    antes = str(dev.estado)

    r = auth_client.post(
        f"/api/devoluciones/{dev.id}/rechazar",
        json={"motivo": "tarde"},
        headers=_headers("recepcionista", sub=str(rec.id)),
    )

    assert r.status_code == 409, r.text
    assert r.json()["code"] == "TRANSICION_DEVOLUCION_INVALIDA"
    db_session.expire_all()
    recargada = db_session.get(Devolucion, dev.id)
    assert recargada is not None and str(recargada.estado) == antes
    assert _eventos(db_session, dev, "devolucion_rechazada") == []
