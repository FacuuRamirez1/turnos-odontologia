"""Test E2E F2 (C-08 8.2): reserva -> pago simulado -> devolucion 60% -> conciliacion."""

import uuid
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security.jwt import create_access_token
from app.infra.db.models import (
    Comprobante,
    Devolucion,
    Disponibilidad,
    Odontologo,
    Pago,
    RecordatorioMail,
    Turno,
    Usuario,
)
from app.tests.conftest import TEST_AUTH_SECRET
from app.workers.conciliacion import conciliar_devoluciones, conciliar_pagos

CORDOBA = ZoneInfo("America/Argentina/Cordoba")


def _staff_headers(rol: str = "recepcionista") -> dict[str, str]:
    token = create_access_token(
        sub=str(uuid.uuid4()), rol=rol, secret=TEST_AUTH_SECRET
    )
    return {"Authorization": f"Bearer {token}"}


def _sembrar_contexto(db_session: Session) -> tuple[uuid.UUID, str, datetime]:
    suf = uuid.uuid4().hex[:8]
    dni = f"99.888.{uuid.uuid4().int % 900 + 100:03d}"  # ficticio P11
    usuario = Usuario(
        email=f"od-e2e-{suf}@clinica-ficticia.example.ar",
        password_hash="$2b$04$" + "e" * 53,
        rol="odontologo",
    )
    db_session.add(usuario)
    db_session.commit()
    odonto = Odontologo(
        user_id=usuario.id,
        monto_turno=Decimal("70000.00"),
        monto_senia=Decimal("65000.00"),
    )
    db_session.add(odonto)
    db_session.commit()

    objetivo = (datetime.now(CORDOBA) + timedelta(days=30)).replace(
        hour=9, minute=0, second=0, microsecond=0
    )
    db_session.add(
        Disponibilidad(
            odontologo_id=odonto.id,
            dia_semana=objetivo.weekday(),
            hora_inicio=time(9, 0),
            hora_fin=time(12, 0),
            duracion_min=30,
            tope_dia=14,
        )
    )
    db_session.commit()
    return uuid.UUID(str(odonto.id)), dni, objetivo


def test_f2_devolucion_e2e_fuera_de_termino_sin_alertas(
    auth_client: TestClient, db_session: Session
) -> None:
    odonto_id, dni, objetivo = _sembrar_contexto(db_session)
    inicio_iso = objetivo.isoformat()

    r_reserva = auth_client.post(
        "/api/reservas",
        json={
            "odontologo_id": str(odonto_id),
            "inicio": inicio_iso,
            "dni": dni,
            "nombre": "Ana",
            "apellido": "Ficticia",
            "email": f"ana.{uuid.uuid4().hex[:6]}@ficticio.example.ar",
            "consentimiento_datos": True,
            "consentimiento_fecha": "2026-01-01T09:00:00+00:00",
        },
        headers={"Idempotency-Key": f"e2e-f2-{uuid.uuid4().hex[:12]}"},
    )
    assert r_reserva.status_code == 201, r_reserva.text
    reserva = r_reserva.json()
    turno_id = uuid.UUID(reserva["id"])
    checkout_token = reserva["checkout_token"]
    assert "(simulado)" not in str(reserva)  # payload operativo; marca via servicio

    pago = db_session.query(Pago).filter(Pago.turno_id == turno_id).one()
    r_sim = auth_client.post(
        f"/api/pagos/{pago.id}/simular",
        json={"accion": "aprobar"},
        headers={"checkout_token": checkout_token},
    )
    assert r_sim.status_code == 200, r_sim.text
    assert r_sim.json()["marca"] == "(simulado)"

    db_session.expire_all()
    pago = db_session.query(Pago).filter(Pago.turno_id == turno_id).one()
    assert pago.estado == "aprobado"
    turno = db_session.get(Turno, turno_id)
    assert turno is not None and turno.estado == "confirmado"

    recibos_pago = (
        db_session.query(Comprobante)
        .filter(Comprobante.pago_id == pago.id, Comprobante.concepto == "pago")
        .all()
    )
    assert len(recibos_pago) == 1
    assert recibos_pago[0].simulado is True

    # Simula paso del tiempo: queda confirmado pero fuera de termino (60%).
    ahora = datetime.now(UTC)
    turno.inicio = ahora + timedelta(hours=2)
    turno.fin = turno.inicio + timedelta(minutes=30)
    db_session.add(turno)
    db_session.commit()

    r_cancel = auth_client.post(
        f"/api/reservas/{turno_id}/cancelar",
        headers=_staff_headers(),
        json={"motivo": "cancelacion fuera de termino e2e"},
    )
    assert r_cancel.status_code == 200, r_cancel.text
    devolucion_json = r_cancel.json()["devolucion"]
    assert devolucion_json is not None
    assert devolucion_json["porcentaje"] == 60
    assert devolucion_json["estado"] == "pendiente"

    db_session.expire_all()
    devolucion = (
        db_session.query(Devolucion).filter(Devolucion.turno_id == turno_id).one()
    )
    assert devolucion.estado == "pendiente"

    r_aprobar = auth_client.post(
        f"/api/devoluciones/{devolucion.id}/aprobar",
        headers=_staff_headers(),
        json={"monto_confirmado": "39000.00"},
    )
    assert r_aprobar.status_code == 200, r_aprobar.text
    assert r_aprobar.json()["marca"] == "(simulado)"

    r_ejecutar = auth_client.post(
        f"/api/devoluciones/{devolucion.id}/ejecutar",
        headers=_staff_headers(),
    )
    assert r_ejecutar.status_code == 200, r_ejecutar.text
    cuerpo_ejec = r_ejecutar.json()
    assert cuerpo_ejec["estado"] == "ejecutada"
    assert cuerpo_ejec["pago_estado"] == "reembolsado_parcial"
    assert str(cuerpo_ejec["mp_refund_id"]).startswith("sim_refund_")
    assert cuerpo_ejec["marca"] == "(simulado)"

    db_session.expire_all()
    turno_db = db_session.get(Turno, turno_id)
    pago_db = db_session.get(Pago, pago.id)
    devolucion_db = db_session.get(Devolucion, devolucion.id)
    assert turno_db is not None and turno_db.estado == "devuelto"
    assert pago_db is not None and pago_db.estado == "reembolsado_parcial"
    assert devolucion_db is not None and devolucion_db.estado == "ejecutada"

    comprobantes = (
        db_session.query(Comprobante)
        .filter(Comprobante.pago_id == pago_db.id)
        .order_by(Comprobante.emitida_at, Comprobante.id)
        .all()
    )
    assert len(comprobantes) == 2
    assert {c.concepto for c in comprobantes} == {"pago", "devolucion"}
    assert all(c.simulado is True for c in comprobantes)

    avisos = (
        db_session.query(RecordatorioMail)
        .filter(
            RecordatorioMail.turno_id == turno_id,
            RecordatorioMail.tipo == "aviso_devolucion",
        )
        .all()
    )
    assert len(avisos) == 1
    assert avisos[0].plantilla_version == "v2"
    assert avisos[0].contexto_json["resultado"] == "ejecutada"
    assert avisos[0].contexto_json["porcentaje"] == 60

    r_traza = auth_client.get(
        f"/api/turnos/{turno_id}/trazabilidad", headers=_staff_headers()
    )
    assert r_traza.status_code == 200, r_traza.text
    traza = r_traza.json()
    assert traza["marca"] == "(simulado)"
    assert traza["turno"]["estado"] == "devuelto"
    assert traza["pago"]["id"] == str(pago_db.id)
    assert traza["pago"]["estado"] == "reembolsado_parcial"
    assert traza["devolucion"]["id"] == str(devolucion_db.id)
    assert traza["devolucion"]["estado"] == "ejecutada"
    assert {c["concepto"] for c in traza["comprobantes"]} == {"pago", "devolucion"}
    assert len(traza["comprobantes"]) == 2
    eventos = traza["eventos_pago"]
    tipos = [e["tipo_evento"] for e in eventos]
    assert tipos.count("webhook_recibido") == 2
    assert set(tipos) == {
        "creado",
        "webhook_recibido",
        "devolucion_solicitada",
        "devolucion_aprobada",
        "devolucion_ejecutada",
    }
    assert "devolucion_solicitada" in tipos
    assert "devolucion_aprobada" in tipos
    assert "devolucion_ejecutada" in tipos
    assert all(e["actor"] and e["fecha"] for e in eventos)
    assert [e["fecha"] for e in eventos] == sorted(e["fecha"] for e in eventos)
    kinds = [
        e.get("payload_json", {}).get("kind")
        for e in eventos
        if e["tipo_evento"] == "webhook_recibido"
    ]
    assert sorted([k for k in kinds if k]) == ["devolucion", "pago"]
    assert [h["estado_nuevo"] for h in traza["historial"]] == [
        "confirmado",
        "cancelado",
        "devuelto",
    ]
    assert all(h["actor_tipo"] and h["fecha"] for h in traza["historial"])

    assert conciliar_pagos(db_session) == []
    assert conciliar_devoluciones(db_session) == []
