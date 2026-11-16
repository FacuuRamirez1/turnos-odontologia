"""Tests C-08 task 7.3 — alertas de conciliación en la bandeja (RED).

Escenarios (U2 feliz / negocio / borde):
- feliz (P8): recepcionista ve las alertas de todos y el odontólogo dueño la
  propia; cada alerta lleva `marca = "(simulado)"` (P10/P15);
- negocio (P8/P12): el odontólogo ajeno no ve la alerta; sin JWT → 401 y token
  de paciente → 403 sin datos;
- borde: sin discrepancias la lista es vacía.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security.jwt import create_access_token
from app.infra.db.models import Odontologo, Paciente, Pago, Turno, Usuario
from app.infra.db.models.pago import EventoPago
from app.tests.conftest import TEST_AUTH_SECRET


def _sembrar_odontologo(db_session: Session, sufijo: str) -> uuid.UUID:
    u = Usuario(
        email=f"od-alerta-{sufijo}@clinica-ficticia.example.ar",
        password_hash="$2b$04$" + "l" * 53,
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


def _headers(rol: str, odontologo_id: uuid.UUID | None = None) -> dict[str, str]:
    token = create_access_token(
        sub=f"user-{uuid.uuid4().hex[:8]}",
        rol=rol,
        secret=TEST_AUTH_SECRET,
        odontologo_id=str(odontologo_id) if odontologo_id else None,
    )
    return {"Authorization": f"Bearer {token}"}


def _sembrar_alerta(
    db_session: Session,
    od_id: uuid.UUID,
    *,
    estado_pago: str = "pendiente",
    discrepancia: bool = True,
) -> EventoPago:
    suf = uuid.uuid4().hex[:8]
    pac = Paciente(
        dni=f"78{uuid.uuid4().int % 90000000 + 10000000:08d}",
        nombre="Ana",
        apellido="Ficticia",
        consentimiento_datos=True,
        consentimiento_fecha=datetime(2026, 10, 1, 9, 0, tzinfo=UTC),
    )
    db_session.add(pac)
    db_session.commit()
    inicio = datetime(2026, 12, 1, 9, 0, tzinfo=UTC) + timedelta(
        minutes=(uuid.uuid4().int % 5000) * 30
    )
    turno = Turno(
        paciente_id=pac.id,
        odontologo_id=od_id,
        inicio=inicio,
        fin=inicio + timedelta(minutes=30),
        estado="creado",
        canal="web",
        idempotency_key=f"key-alerta-{suf}",
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
        estado=estado_pago,
        idempotency_key=f"idem-alerta-{suf}",
    )
    db_session.add(pago)
    db_session.commit()
    evento = EventoPago(
        pago_id=pago.id,
        tipo_evento="conciliado",
        payload_json={
            "estado_pago": estado_pago,
            "estado_esperado": "aprobado",
            "discrepancia": discrepancia,
        },
        actor="sistema",
        created_at=datetime(2026, 11, 1, 9, 0, tzinfo=UTC),
    )
    db_session.add(evento)
    db_session.commit()
    db_session.refresh(evento)
    return evento


def test_recepcionista_y_odontologo_dueno_ven_alertas_feliz(
    auth_client: TestClient, db_session: Session
) -> None:
    """Feliz (P8): recepcionista ve todas; odontólogo dueño solo la propia."""
    od_a = _sembrar_odontologo(db_session, "a")
    od_b = _sembrar_odontologo(db_session, "b")
    alerta_a = _sembrar_alerta(db_session, od_a)
    alerta_b = _sembrar_alerta(db_session, od_b)

    r_recepcion = auth_client.get(
        "/api/devoluciones/alertas", headers=_headers("recepcionista")
    )
    assert r_recepcion.status_code == 200, r_recepcion.text
    cuerpo = r_recepcion.json()
    assert {a["id"] for a in cuerpo} == {str(alerta_a.id), str(alerta_b.id)}
    assert all(a["marca"] == "(simulado)" for a in cuerpo)
    assert all(a["tipo"] == "pago" for a in cuerpo)
    assert all(a["discrepancia"] is True for a in cuerpo)

    r_a = auth_client.get(
        "/api/devoluciones/alertas", headers=_headers("odontologo", od_a)
    )
    assert r_a.status_code == 200, r_a.text
    assert [a["id"] for a in r_a.json()] == [str(alerta_a.id)]
    assert r_a.json()[0]["pago_id"] == str(alerta_a.pago_id)

    r_b = auth_client.get(
        "/api/devoluciones/alertas", headers=_headers("odontologo", od_b)
    )
    assert [a["id"] for a in r_b.json()] == [str(alerta_b.id)]


def test_alertas_sin_jwt_y_paciente_denegado_negocio(
    auth_client: TestClient, db_session: Session
) -> None:
    """Negocio (P8/P12): sin JWT → 401; token de paciente → 403 sin datos."""
    od = _sembrar_odontologo(db_session, "a2")
    _sembrar_alerta(db_session, od)

    r_anon = auth_client.get("/api/devoluciones/alertas")
    assert r_anon.status_code == 401
    assert "discrepancia" not in r_anon.text

    r_pac = auth_client.get(
        "/api/devoluciones/alertas", headers=_headers("paciente")
    )
    assert r_pac.status_code == 403
    assert "discrepancia" not in r_pac.text


def test_alertas_sin_discrepancias_lista_vacia_borde(
    auth_client: TestClient, db_session: Session
) -> None:
    """Borde: sin eventos `conciliado` con discrepancia la bandeja viene vacía."""
    od = _sembrar_odontologo(db_session, "a3")
    _sembrar_alerta(db_session, od, discrepancia=False)

    r = auth_client.get(
        "/api/devoluciones/alertas", headers=_headers("recepcionista")
    )
    assert r.status_code == 200, r.text
    assert r.json() == []
