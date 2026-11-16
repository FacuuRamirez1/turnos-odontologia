"""Tests C-08 task 3.2 — bandeja de devoluciones con RBAC y marca (RED primero).

Escenarios (U2 feliz / negocio / borde):
- feliz: recepcionista lista las pendientes de TODOS los profesionales y cada
  item trae `marca = "(simulado)"` (P10/P15);
- negocio: odontólogo A no ve ni accede al detalle de una devolución de B
  (lista filtrada + detalle 403, sin datos);
- borde: sin JWT → 401, token de paciente → 403, odontólogo sin
  `odontologo_id` → 403 (P8/P12).
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security.jwt import create_access_token
from app.infra.db.models import (
    Devolucion,
    Odontologo,
    Paciente,
    Pago,
    Turno,
    Usuario,
)
from app.tests.conftest import TEST_AUTH_SECRET


def _sembrar_odontologo(db_session: Session, sufijo: str) -> uuid.UUID:
    u = Usuario(
        email=f"od-ban-{sufijo}@clinica-ficticia.example.ar",
        password_hash="$2b$04$" + "b" * 53,
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


def _sembrar_devolucion(
    db_session: Session, od_id: uuid.UUID, *, estado: str = "pendiente"
) -> Devolucion:
    suf = uuid.uuid4().hex[:8]
    pac = Paciente(
        dni=f"76{uuid.uuid4().int % 90000000 + 10000000:08d}",
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
        idempotency_key=f"key-ban-{suf}",
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
        idempotency_key=f"idem-ban-{suf}",
    )
    db_session.add(pago)
    db_session.commit()
    dev = Devolucion(
        pago_id=pago.id,
        turno_id=turno.id,
        monto=Decimal("6000.00"),
        porcentaje=60,
        motivo="cancelación",
        estado=estado,
        idempotency_key=f"dev_{pago.id}",
    )
    db_session.add(dev)
    db_session.commit()
    db_session.refresh(dev)
    return dev


def _headers(rol: str, odontologo_id: uuid.UUID | None = None) -> dict[str, str]:
    token = create_access_token(
        sub=f"user-{uuid.uuid4().hex[:8]}",
        rol=rol,
        secret=TEST_AUTH_SECRET,
        odontologo_id=str(odontologo_id) if odontologo_id else None,
    )
    return {"Authorization": f"Bearer {token}"}


def test_recepcionista_ve_todas_pendientes_con_marca_feliz(
    auth_client: TestClient, db_session: Session
) -> None:
    """Feliz: recepcionista lista pendientes de A y B, todas con marca simulada."""
    od_a = _sembrar_odontologo(db_session, "a")
    od_b = _sembrar_odontologo(db_session, "b")
    dev_a = _sembrar_devolucion(db_session, od_a)
    dev_b = _sembrar_devolucion(db_session, od_b)

    r = auth_client.get(
        "/api/devoluciones", params={"estado": "pendiente"},
        headers=_headers("recepcionista"),
    )

    assert r.status_code == 200, r.text
    cuerpo = r.json()
    ids = {item["id"] for item in cuerpo}
    assert ids == {str(dev_a.id), str(dev_b.id)}
    assert all(item["marca"] == "(simulado)" for item in cuerpo)
    item_a = next(i for i in cuerpo if i["id"] == str(dev_a.id))
    assert item_a["estado"] == "pendiente"
    assert item_a["porcentaje"] == 60
    assert item_a["monto"] == 6000.0

    r_det = auth_client.get(f"/api/devoluciones/{dev_a.id}", headers=_headers("recepcionista"))
    assert r_det.status_code == 200, r_det.text
    assert r_det.json()["id"] == str(dev_a.id)
    assert r_det.json()["marca"] == "(simulado)"


def test_odontologo_no_accede_a_devolucion_ajena_negocio(
    auth_client: TestClient, db_session: Session
) -> None:
    """Negocio (P8): odontólogo A no lista ni lee la devolución de B."""
    od_a = _sembrar_odontologo(db_session, "a2")
    od_b = _sembrar_odontologo(db_session, "b2")
    dev_a = _sembrar_devolucion(db_session, od_a)
    dev_b = _sembrar_devolucion(db_session, od_b)

    r_lista = auth_client.get("/api/devoluciones", headers=_headers("odontologo", od_a))
    assert r_lista.status_code == 200
    assert [i["id"] for i in r_lista.json()] == [str(dev_a.id)]

    r_ajena = auth_client.get(
        f"/api/devoluciones/{dev_b.id}", headers=_headers("odontologo", od_a)
    )
    assert r_ajena.status_code == 403
    assert "monto" not in r_ajena.text


def test_acceso_sin_jwt_paciente_y_odontologo_sin_perfil_borde(
    auth_client: TestClient, db_session: Session
) -> None:
    """Borde (P8/P12): 401 sin JWT, 403 paciente y 403 odontólogo sin perfil."""
    od_a = _sembrar_odontologo(db_session, "a3")
    dev = _sembrar_devolucion(db_session, od_a)

    assert auth_client.get("/api/devoluciones").status_code == 401
    assert auth_client.get(f"/api/devoluciones/{dev.id}").status_code == 401

    paciente = _headers("paciente")
    assert auth_client.get("/api/devoluciones", headers=paciente).status_code == 403

    sin_perfil = _headers("odontologo", None)
    assert auth_client.get("/api/devoluciones", headers=sin_perfil).status_code == 403
    assert auth_client.get(
        f"/api/devoluciones/{dev.id}", headers=sin_perfil
    ).status_code == 403
