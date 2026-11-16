"""Tests C-08 task 3.3 — aprobación manual con confirmación de monto (RED primero).

Escenarios (U2 feliz / negocio / borde):
- feliz: recepcionista aprueba la devolución de otro profesional restating el
  monto exacto → `aprobada` + `aprobada_por/at` + `evento_pago(devolucion_aprobada)`
  con actor y monto;
- negocio: monto distinto → 422 `MONTO_NO_COINCIDE` sin evento; odontólogo
  ajeno → 403 sin evento ni cambio;
- borde: aprobar `aprobada|rechazada|ejecutada` → 409
  `TRANSICION_DEVOLUCION_INVALIDA`; la 60 % sin acción sigue `pendiente`
  (Q4: manual, sin auto-aprobación).
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
        email=f"od-apr-{sufijo}@clinica-ficticia.example.ar",
        password_hash="$2b$04$" + "a" * 53,
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
        email=f"{rol}-apr-{uuid.uuid4().hex[:8]}@clinica-ficticia.example.ar",
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
    porcentaje: int = 60,
    monto: str = "6000.00",
    actor_id: uuid.UUID | None = None,
) -> Devolucion:
    suf = uuid.uuid4().hex[:8]
    pac = Paciente(
        dni=f"75{uuid.uuid4().int % 90000000 + 10000000:08d}",
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
        idempotency_key=f"key-apr-{suf}",
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
        idempotency_key=f"idem-apr-{suf}",
    )
    db_session.add(pago)
    db_session.commit()
    ahora = datetime.now(UTC)
    dev = Devolucion(
        pago_id=pago.id,
        turno_id=turno.id,
        monto=Decimal(monto),
        porcentaje=porcentaje,
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


def test_recepcionista_aprueba_devolucion_ajena_feliz(
    auth_client: TestClient, db_session: Session
) -> None:
    """Feliz: recepcionista aprueba la pendiente de otro profesional con su monto."""
    od_b = _sembrar_odontologo(db_session, "b")
    rec = _sembrar_usuario(db_session, "recepcionista")
    dev = _sembrar_devolucion(db_session, od_b)

    r = auth_client.post(
        f"/api/devoluciones/{dev.id}/aprobar",
        json={"monto_confirmado": "6000.00"},
        headers=_headers("recepcionista", sub=str(rec.id)),
    )

    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "aprobada"
    assert r.json()["marca"] == "(simulado)"

    db_session.expire_all()
    recargada = db_session.get(Devolucion, dev.id)
    assert recargada is not None
    assert str(recargada.estado) == "aprobada"
    assert uuid.UUID(str(recargada.aprobada_por)) == uuid.UUID(str(rec.id))
    assert recargada.aprobada_at is not None

    eventos = _eventos(db_session, dev, "devolucion_aprobada")
    assert len(eventos) == 1
    assert eventos[0].actor == "recepcionista"
    assert eventos[0].payload_json["actor_id"] == str(rec.id)
    assert Decimal(str(eventos[0].payload_json["monto"])) == Decimal("6000.00")


def test_monto_distinto_422_sin_evento_negocio(
    auth_client: TestClient, db_session: Session
) -> None:
    """Negocio: restating un monto distinto → 422 MONTO_NO_COINCIDE, sin evento."""
    od_a = _sembrar_odontologo(db_session, "a2")
    rec = _sembrar_usuario(db_session, "recepcionista")
    dev = _sembrar_devolucion(db_session, od_a)

    r = auth_client.post(
        f"/api/devoluciones/{dev.id}/aprobar",
        json={"monto_confirmado": "6000.01"},
        headers=_headers("recepcionista", sub=str(rec.id)),
    )

    assert r.status_code == 422, r.text
    assert r.json()["code"] == "MONTO_NO_COINCIDE"

    db_session.expire_all()
    recargada = db_session.get(Devolucion, dev.id)
    assert recargada is not None and str(recargada.estado) == "pendiente"
    assert recargada.aprobada_por is None
    assert _eventos(db_session, dev, "devolucion_aprobada") == []


def test_odontologo_ajeno_403_sin_evento_negocio(
    auth_client: TestClient, db_session: Session
) -> None:
    """Negocio (P8): odontólogo A no aprueba la devolución de B."""
    od_a = _sembrar_odontologo(db_session, "a3")
    od_b = _sembrar_odontologo(db_session, "b3")
    dev = _sembrar_devolucion(db_session, od_b)

    r = auth_client.post(
        f"/api/devoluciones/{dev.id}/aprobar",
        json={"monto_confirmado": "6000.00"},
        headers=_headers("odontologo", sub=str(uuid.uuid4()), odontologo_id=od_a),
    )

    assert r.status_code == 403
    db_session.expire_all()
    recargada = db_session.get(Devolucion, dev.id)
    assert recargada is not None and str(recargada.estado) == "pendiente"
    assert _eventos(db_session, dev, "devolucion_aprobada") == []


@pytest.mark.parametrize("estado", ["aprobada", "rechazada", "ejecutada"])
def test_aprobar_resuelta_409_sin_evento_borde(
    auth_client: TestClient, db_session: Session, estado: str
) -> None:
    """Borde: aprobar una devolución ya resuelta → 409, sin evento."""
    od_a = _sembrar_odontologo(db_session, f"a-{estado}")
    rec = _sembrar_usuario(db_session, "recepcionista")
    dev = _sembrar_devolucion(
        db_session, od_a, estado=estado, actor_id=uuid.UUID(str(rec.id))
    )
    antes = str(dev.estado)

    r = auth_client.post(
        f"/api/devoluciones/{dev.id}/aprobar",
        json={"monto_confirmado": "6000.00"},
        headers=_headers("recepcionista", sub=str(rec.id)),
    )

    assert r.status_code == 409, r.text
    assert r.json()["code"] == "TRANSICION_DEVOLUCION_INVALIDA"
    db_session.expire_all()
    recargada = db_session.get(Devolucion, dev.id)
    assert recargada is not None and str(recargada.estado) == antes
    assert _eventos(db_session, dev, "devolucion_aprobada") == []


def test_devolucion_60_sin_accion_sigue_pendiente_borde(
    auth_client: TestClient, db_session: Session
) -> None:
    """Borde (Q4): una 60 % sin acción queda pendiente; no hay auto-aprobación."""
    od_a = _sembrar_odontologo(db_session, "a4")
    rec = _sembrar_usuario(db_session, "recepcionista")
    dev = _sembrar_devolucion(db_session, od_a, porcentaje=60)

    r = auth_client.get(
        "/api/devoluciones", params={"estado": "pendiente"},
        headers=_headers("recepcionista", sub=str(rec.id)),
    )

    assert r.status_code == 200
    assert [i["id"] for i in r.json()] == [str(dev.id)]
    assert _eventos(db_session, dev, "devolucion_aprobada") == []
    assert _eventos(db_session, dev, "devolucion_ejecutada") == []
    db_session.expire_all()
    recargada = db_session.get(Devolucion, dev.id)
    assert recargada is not None and str(recargada.estado) == "pendiente"
