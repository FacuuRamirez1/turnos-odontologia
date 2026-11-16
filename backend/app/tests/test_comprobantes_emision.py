"""Tests C-08 task 5.1 - emision de comprobantes (RED primero).

Escenarios (U2 feliz / error-negocio / borde) segun tasks.md 5.1 y spec
comprobantes:
- feliz: aprobacion del webhook emite el recibo (concepto `pago`, design D6);
- error: rechazo/expiracion del webhook no emiten recibo;
- error: devolucion rechazada no emite recibo de devolucion; cancelacion con
  cotizacion 0 por ciento tampoco (RN-SENIA-0, sin fila de devolucion);
- borde: replay de webhook y reintento de ejecucion no duplican el recibo;
- borde: dos emisiones correlativas reciben numeros distintos (`RI-000001`).

El hook de emision vive en la rama `aprobado` de `_procesar_webhook_pago` y
en la rama devolucion del mismo handler (design D6).
"""

import hashlib
import hmac
import uuid
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security.jwt import create_access_token
from app.core.settings import get_settings
from app.infra.db.models import Comprobante, Devolucion, Odontologo, Paciente, Pago, Turno, Usuario
from app.tests.conftest import TEST_AUTH_SECRET

RUTA_WEBHOOK = "/api/webhooks/mercadopago"
RUTA_DEVOLUCION_RECHAZAR = "/api/devoluciones/{devolucion_id}/rechazar"
RUTA_DEVOLUCION_EJECUTAR = "/api/devoluciones/{devolucion_id}/ejecutar"
CORDOBA = ZoneInfo("America/Argentina/Cordoba")


def _firmar(payload: str, secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256,
    ).hexdigest()


def _headers_staff_con(db_session: Session) -> dict[str, str]:
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        email=f"staff-em-{suf}@clinica-ficticia.example.ar",
        password_hash="$2b$04$" + "b" * 53, rol="recepcionista",
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    token = create_access_token(
        sub=str(uuid.UUID(str(u.id))), rol="recepcionista", secret=TEST_AUTH_SECRET,
    )
    return {"Authorization": f"Bearer {token}"}


def _sembrar_turno_con_pago(
    db_session: Session, dni: str = "99999811",
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Odontologo + paciente + turno (`creado`) + pago (`pendiente`, simulado)."""
    from app.infra.db.models import Disponibilidad

    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        email=f"od-em-{suf}@clinica-ficticia.example.ar",
        password_hash="$2b$04$" + "m" * 53, rol="odontologo",
    )
    db_session.add(u)
    db_session.commit()
    od = Odontologo(user_id=u.id, monto_turno=Decimal("70000"), monto_senia=Decimal("65000"))
    db_session.add(od)
    db_session.commit()
    od_id = uuid.UUID(str(od.id))
    objetivo = datetime.now(CORDOBA) + timedelta(days=35)
    objetivo = objetivo.replace(hour=9, minute=0, second=0, microsecond=0)
    db_session.add(Disponibilidad(
        odontologo_id=od_id, dia_semana=objetivo.weekday(),
        hora_inicio=time(9, 0), hora_fin=time(12, 0), duracion_min=30, tope_dia=14,
    ))
    db_session.commit()
    pac = Paciente(
        dni=dni, nombre="Ana", apellido="Ficticia", consentimiento_datos=True,
        consentimiento_fecha=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
    )
    db_session.add(pac)
    db_session.commit()
    turno = Turno(
        paciente_id=pac.id, odontologo_id=od_id, inicio=objetivo,
        fin=objetivo + timedelta(minutes=30), estado="creado", canal="web",
        idempotency_key=f"key-em-{suf}",
    )
    db_session.add(turno)
    db_session.flush()
    pago = Pago(
        turno_id=turno.id, odontologo_id=od_id, monto=Decimal("65000.00"),
        moneda="ARS", proveedor="simulado", mp_payment_id=f"sim_pay_{uuid.uuid4()}",
        estado="pendiente", idempotency_key=f"idem-em-{suf}",
    )
    db_session.add(pago)
    db_session.flush()
    return uuid.UUID(str(turno.id)), uuid.UUID(str(pago.id)), od_id


def _sembrar_devolucion(
    db_session: Session, *, estado: str = "aprobada", porcentaje: int = 60,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, str]:
    """Turno `cancelado` + pago `aprobado` + devolucion (D3/D4)."""
    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        email=f"od-dev-em-{suf}@clinica-ficticia.example.ar",
        password_hash="$2b$04$" + "d" * 53, rol="odontologo",
    )
    db_session.add(u)
    db_session.commit()
    od = Odontologo(user_id=u.id, monto_turno=Decimal("70000"), monto_senia=Decimal("65000"))
    db_session.add(od)
    db_session.commit()
    od_id = uuid.UUID(str(od.id))
    pac = Paciente(
        dni=f"66{uuid.uuid4().int % 90000000 + 10000000:08d}", nombre="Ana", apellido="Ficticia",
        consentimiento_datos=True, consentimiento_fecha=datetime(2026, 10, 1, 9, 0, tzinfo=UTC),
    )
    db_session.add(pac)
    db_session.commit()
    inicio = datetime(2026, 12, 1, 9, 0, tzinfo=UTC) + timedelta(
        minutes=(uuid.uuid4().int % 5000) * 30,
    )
    turno = Turno(
        paciente_id=pac.id, odontologo_id=od_id, inicio=inicio,
        fin=inicio + timedelta(minutes=30), estado="cancelado", canal="web",
        idempotency_key=f"key-devem-{suf}",
    )
    db_session.add(turno)
    db_session.commit()
    pago = Pago(
        turno_id=turno.id, odontologo_id=od_id, monto=Decimal("10000.00"), moneda="ARS",
        proveedor="simulado", mp_payment_id=f"sim_pay_{uuid.uuid4()}", estado="aprobado",
        idempotency_key=f"idem-devem-{suf}",
    )
    db_session.add(pago)
    db_session.commit()
    turno.pago_id = pago.id
    db_session.add(turno)
    db_session.commit()
    actor = Usuario(
        email=f"staff-devem-{suf}@clinica-ficticia.example.ar",
        password_hash="$2b$04$" + "a" * 53, rol="recepcionista",
    )
    db_session.add(actor)
    db_session.commit()
    monto = Decimal("10000.00") if porcentaje == 100 else Decimal("6000.00")
    dev = Devolucion(
        pago_id=pago.id, turno_id=turno.id, monto=monto, porcentaje=porcentaje,
        motivo="cancelacion", estado=estado, idempotency_key=f"dev_{pago.id}",
        aprobada_por=actor.id if estado == "aprobada" else None,
        aprobada_at=datetime(2026, 11, 1, 10, 0, tzinfo=UTC) if estado == "aprobada" else None,
        ejecutada_por=actor.id if estado == "ejecutada" else None,
        ejecutada_at=datetime(2026, 11, 1, 10, 5, tzinfo=UTC) if estado == "ejecutada" else None,
    )
    db_session.add(dev)
    db_session.commit()
    db_session.refresh(dev)
    return (
        uuid.UUID(str(dev.id)), uuid.UUID(str(pago.id)),
        uuid.UUID(str(turno.id)), str(pago.mp_payment_id),
    )

def test_webhook_aprobacion_emite_recibo_pago_feliz(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Feliz D6: aprobacion -> un recibo con concepto `pago` se emite (mismo txn)."""
    from app.infra.db.models import Pago

    turno_id, pago_id, _ = _sembrar_turno_con_pago(db_session, "99999811")
    pago = db_session.query(Pago).get(uuid.UUID(str(pago_id)))
    assert pago is not None
    payload = f'{{"mp_payment_id": "{pago.mp_payment_id}", "status": "approved"}}'
    firma = _firmar(payload, get_settings().mp_webhook_secret)
    r = auth_client.post(
        RUTA_WEBHOOK, content=payload,
        headers={"x-signature": firma, "content-type": "application/json"},
    )
    assert r.status_code == 200, r.text

    db_session.expire_all()
    comprobantes = db_session.query(Comprobante).filter(
        Comprobante.pago_id == uuid.UUID(str(pago_id)),
    ).all()
    assert len(comprobantes) == 1
    recibo = comprobantes[0]
    assert recibo.concepto == "pago"
    assert recibo.tipo == "recibo_interno"
    assert recibo.cae is None
    assert recibo.simulado is True
    assert recibo.devolucion_id is None
    assert recibo.turno_id == uuid.UUID(str(turno_id))
    assert recibo.monto == Decimal("65000.00")
    assert recibo.numero.startswith("RI-") and len(recibo.numero) == 9


@pytest.mark.parametrize("status_mp,estado", [
    ("rejected", "rechazado"),
    ("expired", "expirado"),
])
def test_webhook_rechazo_o_expiracion_no_emite_recibo_error(
    auth_client: TestClient, db_session: Session, status_mp: str, estado: str,
) -> None:
    """Error de negocio: rechazo/expiracion no emiten recibo (spec § pago)."""
    from app.infra.db.models import Pago

    _, pago_id, _ = _sembrar_turno_con_pago(db_session, "999998" + estado[:3])
    pago = db_session.query(Pago).get(uuid.UUID(str(pago_id)))
    assert pago is not None
    payload = f'{{"mp_payment_id": "{pago.mp_payment_id}", "status": "{status_mp}"}}'
    firma = _firmar(payload, get_settings().mp_webhook_secret)
    r = auth_client.post(
        RUTA_WEBHOOK, content=payload,
        headers={"x-signature": firma, "content-type": "application/json"},
    )
    assert r.status_code == 200, r.text

    db_session.expire_all()
    assert db_session.query(Comprobante).filter(
        Comprobante.pago_id == uuid.UUID(str(pago_id)),
    ).count() == 0


def test_devolucion_rechazada_no_emite_recibo_devolucion_error(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Error: devolucion `rechazada` no emite recibo de devolucion (D6)."""
    dev_id, _, _, _ = _sembrar_devolucion(db_session, estado="pendiente")

    r = auth_client.post(
        RUTA_DEVOLUCION_RECHAZAR.format(devolucion_id=dev_id),
        json={"motivo": "senal no abonada"},
        headers=_headers_staff_con(db_session),
    )
    assert r.status_code == 200, r.text

    db_session.expire_all()
    dev = db_session.query(Devolucion).get(dev_id)
    assert dev is not None and str(dev.estado) == "rechazada"
    assert db_session.query(Comprobante).filter(
        Comprobante.concepto == "devolucion",
    ).count() == 0


def test_cancelacion_cero_no_emite_recibo_devolucion_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Borde RN-SENIA-0: cotizacion 0 por ciento -> no hay devolucion ni recibo."""
    from app.tests.test_reservas_cancelacion import _sembrar as _sembrar_cancel

    ctx = _sembrar_cancel(db_session, con_pago=True, inicio_pasado=True)

    r = auth_client.post(
        f"/api/reservas/{ctx['turno_id']}/cancelar",
        params={"dni": ctx["dni"], "token": ctx["token"]},
        json={},
    )
    assert r.status_code == 200, r.text
    assert r.json()["devolucion"] is None

    db_session.expire_all()
    assert db_session.query(Comprobante).filter(
        Comprobante.concepto == "devolucion",
    ).count() == 0


def test_webhook_replay_aprobacion_no_duplica_recibo_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Borde D6/P4: replay del approval no emite un segundo recibo."""
    from app.infra.db.models import Pago

    _, pago_id, _ = _sembrar_turno_con_pago(db_session, "99999812")
    pago = db_session.query(Pago).get(uuid.UUID(str(pago_id)))
    assert pago is not None
    payload = f'{{"mp_payment_id": "{pago.mp_payment_id}", "status": "approved"}}'
    firma = _firmar(payload, get_settings().mp_webhook_secret)
    headers = {"x-signature": firma, "content-type": "application/json"}

    r1 = auth_client.post(RUTA_WEBHOOK, content=payload, headers=headers)
    assert r1.status_code == 200, r1.text
    r2 = auth_client.post(RUTA_WEBHOOK, content=payload, headers=headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["idempotente"] is True

    db_session.expire_all()
    assert db_session.query(Comprobante).filter(
        Comprobante.pago_id == uuid.UUID(str(pago_id)),
    ).count() == 1


def test_reintento_ejecucion_no_duplica_recibo_devolucion_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Borde D6/P4: reintento de la ejecucion no duplica el recibo devolucion."""
    dev_id, _, _, _ = _sembrar_devolucion(db_session, estado="aprobada")

    r1 = auth_client.post(
        RUTA_DEVOLUCION_EJECUTAR.format(devolucion_id=dev_id),
        headers=_headers_staff_con(db_session),
    )
    assert r1.status_code == 200, r1.text
    r2 = auth_client.post(
        RUTA_DEVOLUCION_EJECUTAR.format(devolucion_id=dev_id),
        headers=_headers_staff_con(db_session),
    )
    assert r2.status_code == 200, r2.text

    db_session.expire_all()
    assert db_session.query(Comprobante).filter(
        Comprobante.concepto == "devolucion",
    ).count() == 1


def test_dos_recibos_emitidos_numeros_distintos_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Borde D6: dos emisiones correlativas reciben numeros distintos."""
    from app.infra.db.models import Pago

    ids: list[uuid.UUID] = []
    for dni in ("99999821", "99999822"):
        _, pago_id, _ = _sembrar_turno_con_pago(db_session, dni)
        pago = db_session.query(Pago).get(pago_id)
        assert pago is not None
        payload = f'{{"mp_payment_id": "{pago.mp_payment_id}", "status": "approved"}}'
        firma = _firmar(payload, get_settings().mp_webhook_secret)
        r = auth_client.post(
            RUTA_WEBHOOK, content=payload,
            headers={"x-signature": firma, "content-type": "application/json"},
        )
        assert r.status_code == 200, r.text
        ids.append(pago_id)

    db_session.expire_all()
    comprobantes = db_session.query(Comprobante).filter(
        Comprobante.pago_id.in_(ids),
    ).all()
    assert len(comprobantes) == 2
    numeros = sorted(str(c.numero) for c in comprobantes)
    assert numeros[0] != numeros[1]
    assert all(n.startswith("RI-") and len(n) == 9 for n in numeros)
