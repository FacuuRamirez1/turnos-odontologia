"""Tests C-08 task 7.1 — trazabilidad staff turno/pago/devolución/recibos (RED).

Escenarios (U2 feliz / negocio / borde):
- feliz: turno `devuelto` con pago reembolsado, devolución ejecutada, ambos
  recibos y los `evento_pago`/`turno_historial` ordenados con actor y fecha;
- negocio (P8): odontólogo A no navega la trazabilidad de un turno de B → 403;
- borde: turno sin pago → secciones de pago, devolución y recibos vacías
  explícitas, conservando el historial del turno.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security.jwt import create_access_token
from app.infra.db.models import (
    Comprobante,
    Devolucion,
    Odontologo,
    Paciente,
    Pago,
    Turno,
    TurnoHistorial,
    Usuario,
)
from app.infra.db.models.pago import EventoPago
from app.tests.conftest import TEST_AUTH_SECRET

_NUMERO = [910000]


def _numero() -> str:
    _NUMERO[0] += 1
    return f"RI-{_NUMERO[0]:06d}"


def _sembrar_odontologo(db_session: Session, sufijo: str) -> uuid.UUID:
    u = Usuario(
        email=f"od-traza-{sufijo}@clinica-ficticia.example.ar",
        password_hash="$2b$04$" + "t" * 53,
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


def _sembrar_turno(
    db_session: Session, od_id: uuid.UUID, *, estado: str = "devuelto"
) -> Turno:
    suf = uuid.uuid4().hex[:8]
    pac = Paciente(
        dni=f"77{uuid.uuid4().int % 90000000 + 10000000:08d}",
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
        estado=estado,
        canal="web",
        idempotency_key=f"key-traza-{suf}",
    )
    db_session.add(turno)
    db_session.commit()
    db_session.refresh(turno)
    return turno


def _sembrar_traza_completa(db_session: Session, od_id: uuid.UUID) -> dict[str, object]:
    """Turno devuelto + pago reembolsado + devolución ejecutada + 2 recibos."""
    suf = uuid.uuid4().hex[:8]
    turno = _sembrar_turno(db_session, od_id, estado="devuelto")
    pago = Pago(
        turno_id=turno.id,
        odontologo_id=od_id,
        monto=Decimal("10000.00"),
        moneda="ARS",
        proveedor="simulado",
        mp_payment_id=f"sim_pay_{uuid.uuid4()}",
        estado="reembolsado_parcial",
        idempotency_key=f"idem-traza-{suf}",
    )
    db_session.add(pago)
    db_session.commit()
    turno.pago_id = pago.id
    db_session.add(turno)
    db_session.commit()

    actor = Usuario(
        email=f"staff-traza-{suf}@clinica-ficticia.example.ar",
        password_hash="$2b$04$" + "s" * 53,
        rol="recepcionista",
    )
    db_session.add(actor)
    db_session.commit()
    devolucion = Devolucion(
        pago_id=pago.id,
        turno_id=turno.id,
        monto=Decimal("6000.00"),
        porcentaje=60,
        motivo="cancelación fuera de término",
        estado="ejecutada",
        idempotency_key=f"dev_{pago.id}",
        mp_refund_id=f"sim_refund_{uuid.uuid4()}",
        aprobada_por=actor.id,
        aprobada_at=datetime(2026, 11, 1, 10, 0, tzinfo=UTC),
        ejecutada_por=actor.id,
        ejecutada_at=datetime(2026, 11, 1, 10, 5, tzinfo=UTC),
    )
    db_session.add(devolucion)
    db_session.commit()
    db_session.refresh(devolucion)

    base = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
    eventos = [
        ("creado", "paciente", base),
        ("webhook_recibido", "sistema", base + timedelta(minutes=1)),
        ("devolucion_solicitada", "paciente", base + timedelta(minutes=2)),
        ("devolucion_aprobada", "recepcionista", base + timedelta(minutes=3)),
        ("devolucion_ejecutada", "sistema", base + timedelta(minutes=4)),
    ]
    for tipo, actor_tipo, fecha in eventos:
        db_session.add(
            EventoPago(
                pago_id=pago.id,
                tipo_evento=tipo,
                payload_json={"status": "aprobado"} if tipo == "webhook_recibido" else {},
                actor=actor_tipo,
                created_at=fecha,
            )
        )
    historial = [
        ("creado", "confirmado", base + timedelta(minutes=1)),
        ("confirmado", "cancelado", base + timedelta(minutes=2)),
        ("cancelado", "devuelto", base + timedelta(minutes=4)),
    ]
    for anterior, nuevo, fecha in historial:
        db_session.add(
            TurnoHistorial(
                turno_id=turno.id,
                estado_anterior=anterior,
                estado_nuevo=nuevo,
                actor_tipo="sistema",
                actor_id="sistema",
                fecha=fecha,
            )
        )

    comprobante_pago = Comprobante(
        pago_id=pago.id,
        turno_id=turno.id,
        devolucion_id=None,
        tipo="recibo_interno",
        concepto="pago",
        numero=_numero(),
        monto=Decimal("10000.00"),
        moneda="ARS",
        simulado=True,
        payload_json={"concepto": "pago"},
    )
    comprobante_devolucion = Comprobante(
        pago_id=pago.id,
        turno_id=turno.id,
        devolucion_id=devolucion.id,
        tipo="recibo_interno",
        concepto="devolucion",
        numero=_numero(),
        monto=Decimal("6000.00"),
        moneda="ARS",
        simulado=True,
        payload_json={"concepto": "devolucion"},
    )
    db_session.add_all([comprobante_pago, comprobante_devolucion])
    db_session.commit()
    return {
        "turno": turno,
        "pago": pago,
        "devolucion": devolucion,
        "recibos": {str(comprobante_pago.numero), str(comprobante_devolucion.numero)},
    }


def test_trazabilidad_completa_feliz(
    auth_client: TestClient, db_session: Session
) -> None:
    """Feliz: turno devuelto enlaza pago, devoluci��n, ambos recibos y eventos."""
    od = _sembrar_odontologo(db_session, "a")
    ctx = _sembrar_traza_completa(db_session, od)
    turno = cast(Turno, ctx["turno"])
    pago = cast(Pago, ctx["pago"])
    devolucion = cast(Devolucion, ctx["devolucion"])

    r = auth_client.get(
        f"/api/turnos/{turno.id}/trazabilidad",
        headers=_headers("recepcionista"),
    )

    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["turno"]["id"] == str(turno.id)
    assert cuerpo["turno"]["estado"] == "devuelto"
    assert cuerpo["pago"]["id"] == str(pago.id)
    assert cuerpo["pago"]["estado"] == "reembolsado_parcial"
    assert cuerpo["devolucion"]["id"] == str(devolucion.id)
    assert cuerpo["devolucion"]["monto"] == 6000.0
    assert {c["numero"] for c in cuerpo["comprobantes"]} == ctx["recibos"]
    assert [e["tipo_evento"] for e in cuerpo["eventos_pago"]] == [
        "creado",
        "webhook_recibido",
        "devolucion_solicitada",
        "devolucion_aprobada",
        "devolucion_ejecutada",
    ]
    assert all(e["actor"] and e["fecha"] for e in cuerpo["eventos_pago"])
    assert [h["estado_nuevo"] for h in cuerpo["historial"]] == [
        "confirmado",
        "cancelado",
        "devuelto",
    ]
    assert all(h["actor_tipo"] and h["fecha"] for h in cuerpo["historial"])
    assert cuerpo["marca"] == "(simulado)"


def test_odontologo_no_navega_trazabilidad_ajena_negocio(
    auth_client: TestClient, db_session: Session
) -> None:
    """Negocio (P8): odont��logo A recibe 403 en la trazabilidad del turno de B."""
    od_a = _sembrar_odontologo(db_session, "a2")
    od_b = _sembrar_odontologo(db_session, "b2")
    ctx = _sembrar_traza_completa(db_session, od_b)
    turno = cast(Turno, ctx["turno"])

    r = auth_client.get(
        f"/api/turnos/{turno.id}/trazabilidad",
        headers=_headers("odontologo", od_a),
    )

    assert r.status_code == 403
    assert "10000" not in r.text
    assert "devolucion" not in r.text


def test_turno_sin_pago_secciones_vacias_borde(
    auth_client: TestClient, db_session: Session
) -> None:
    """Borde: sin pago, las secciones de pago/devolución/recibos vienen vacías."""
    od = _sembrar_odontologo(db_session, "a3")
    turno = _sembrar_turno(db_session, od, estado="creado")
    db_session.add(
        TurnoHistorial(
            turno_id=turno.id,
            estado_anterior="creado",
            estado_nuevo="creado",
            actor_tipo="paciente",
            actor_id="paciente",
            fecha=datetime(2026, 11, 1, 9, 0, tzinfo=UTC),
        )
    )
    db_session.commit()

    r = auth_client.get(
        f"/api/turnos/{turno.id}/trazabilidad",
        headers=_headers("recepcionista"),
    )

    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["turno"]["id"] == str(turno.id)
    assert cuerpo["pago"] is None
    assert cuerpo["devolucion"] is None
    assert cuerpo["comprobantes"] == []
    assert cuerpo["eventos_pago"] == []
    assert [h["estado_nuevo"] for h in cuerpo["historial"]] == ["creado"]
    assert cuerpo["marca"] == "(simulado)"
