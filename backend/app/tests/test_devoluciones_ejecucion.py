"""Tests C-08 task 4.4 — POST /api/devoluciones/{id}/ejecutar (RED primero).

Escenarios (U2 feliz / negocio / borde):
- feliz: ejecución de una `aprobada` → `ejecutada` + `sim_refund_`, pago
  `reembolsado_parcial`, turno `devuelto` y `marca = "(simulado)"`;
- negocio: `pendiente` → 409 sin invocar al proveedor; odontólogo ajeno → 403
  sin invocar al proveedor;
- borde: reintento devuelve el mismo `mp_refund_id` sin segundo evento;
  `PAGO_MODO=mercadopago` → 503 `PROVEEDOR_NO_DISPONIBLE` y sigue `aprobada`.

`with_for_update()` es no-op en SQLite: el test de "dos ejecuciones" verifica
la INVARIANTE observable (una sola ejecución/evento/id) de forma secuencial.
El bloqueo físico se validará contra PostgreSQL en las tasks 8.2/8.3.
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
    Odontologo,
    Paciente,
    Pago,
    Turno,
    Usuario,
)
from app.tests.conftest import TEST_AUTH_SECRET

RUTA = "/api/devoluciones/{devolucion_id}/ejecutar"


def _sembrar(
    db_session: Session, *, estado: str = "aprobada", porcentaje: int = 60,
    pago_estado: str = "aprobado", odontologo: uuid.UUID | None = None,
    con_ejecutor: bool = False,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """Turno cancelado + pago aprobado + devolución en `estado` (D4).

    `con_ejecutor` simula el webhook externo del proveedor preparado por el
    endpoint (D4: `ejecutada_por/at` se registran antes de llamar al puerto).
    """
    suf = uuid.uuid4().hex[:8]
    if odontologo is None:
        u = Usuario(
            email=f"od-ejec-{suf}@clinica-ficticia.example.ar",
            password_hash="$2b$04$" + "e" * 53, rol="odontologo",
        )
        db_session.add(u)
        db_session.commit()
        od = Odontologo(user_id=u.id, monto_turno=Decimal("70000"),
                        monto_senia=Decimal("10000"))
        db_session.add(od)
        db_session.commit()
        odontologo = uuid.UUID(str(od.id))

    pac = Paciente(
        dni=f"77{uuid.uuid4().int % 90000000 + 10000000:08d}",
        nombre="Ana", apellido="Ficticia", consentimiento_datos=True,
        consentimiento_fecha=datetime(2026, 10, 1, 9, 0, tzinfo=UTC),
    )
    db_session.add(pac)
    db_session.commit()

    inicio = datetime(2026, 12, 1, 9, 0, tzinfo=UTC) + timedelta(
        minutes=(uuid.uuid4().int % 5000) * 30
    )
    turno = Turno(
        paciente_id=pac.id, odontologo_id=odontologo, inicio=inicio,
        fin=inicio + timedelta(minutes=30), estado="cancelado", canal="web",
        idempotency_key=f"key-ejec-{suf}",
    )
    db_session.add(turno)
    db_session.commit()

    pago = Pago(
        turno_id=turno.id, odontologo_id=odontologo, monto=Decimal("10000.00"),
        moneda="ARS", proveedor="simulado",
        mp_payment_id=f"sim_pay_{uuid.uuid4()}", estado=pago_estado,
        idempotency_key=f"idem-ejec-{suf}",
    )
    db_session.add(pago)
    db_session.commit()
    turno.pago_id = pago.id
    db_session.add(turno)
    db_session.commit()

    ejecutor = Usuario(
        email=f"staff-ejec-{suf}@clinica-ficticia.example.ar",
        password_hash="$2b$04$" + "x" * 53, rol="recepcionista",
    )
    db_session.add(ejecutor)
    db_session.commit()

    monto = Decimal("10000.00") if porcentaje == 100 else Decimal("6000.00")
    dev = Devolucion(
        pago_id=pago.id, turno_id=turno.id, monto=monto, porcentaje=porcentaje,
        motivo="cancelación", estado=estado, idempotency_key=f"dev_{pago.id}",
        aprobada_por=ejecutor.id if estado != "pendiente" else None,
        aprobada_at=(
            datetime(2026, 11, 1, 10, 0, tzinfo=UTC)
            if estado != "pendiente" else None
        ),
        ejecutada_por=ejecutor.id if con_ejecutor else None,
        ejecutada_at=(
            datetime(2026, 11, 1, 10, 5, tzinfo=UTC) if con_ejecutor else None
        ),
    )
    db_session.add(dev)
    db_session.commit()
    db_session.refresh(dev)
    return (
        uuid.UUID(str(dev.id)), uuid.UUID(str(pago.id)),
        uuid.UUID(str(turno.id)), uuid.UUID(str(ejecutor.id)), odontologo,
    )


def _headers(
    rol: str = "recepcionista", *, sub: uuid.UUID,
    odontologo_id: uuid.UUID | None = None,
) -> dict[str, str]:
    token = create_access_token(
        sub=str(sub), rol=rol, secret=TEST_AUTH_SECRET,
        odontologo_id=str(odontologo_id) if odontologo_id else None,
    )
    return {"Authorization": f"Bearer {token}"}


def _proveedor_prohibido(*_args: object, **_kwargs: object) -> object:
    raise AssertionError("el proveedor no debe invocarse en este caso")


def test_ejecucion_feliz_marca_simulado(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Feliz: aprueba→ejecuta; estado, pago parcial, turno devuelto y marca."""
    dev_id, pago_id, turno_id, ejecutor_id, _ = _sembrar(db_session)

    r = auth_client.post(
        RUTA.format(devolucion_id=dev_id),
        headers=_headers(sub=ejecutor_id),
    )
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["estado"] == "ejecutada"
    assert str(cuerpo["mp_refund_id"]).startswith("sim_refund_")
    assert cuerpo["marca"] == "(simulado)"
    assert cuerpo["pago_estado"] == "reembolsado_parcial"

    from app.infra.db.models import EventoPago, TurnoHistorial
    db_session.expire_all()
    dev = db_session.query(Devolucion).get(dev_id)
    assert dev is not None
    assert dev.estado == "ejecutada"
    assert dev.ejecutada_por == ejecutor_id
    assert dev.ejecutada_at is not None
    assert dev.mp_refund_id == cuerpo["mp_refund_id"]

    pago = db_session.query(Pago).get(pago_id)
    assert pago is not None
    assert pago.estado == "reembolsado_parcial"
    assert pago.monto == Decimal("10000.00")

    turno = db_session.query(Turno).get(turno_id)
    assert turno is not None
    assert turno.estado == "devuelto"
    assert db_session.query(TurnoHistorial).filter_by(
        turno_id=turno_id, estado_nuevo="devuelto", actor_tipo="sistema",
    ).count() == 1

    eventos = db_session.query(EventoPago).filter_by(pago_id=pago_id).all()
    ejecutados = [e for e in eventos if e.tipo_evento == "devolucion_ejecutada"]
    assert len(ejecutados) == 1
    assert ejecutados[0].payload_json["solicitado_por"] == str(ejecutor_id)


def test_pendiente_409_sin_invocar_proveedor_negocio(
    auth_client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Error de negocio: `pendiente` → 409 antes de tocar el proveedor."""
    dev_id, _, _, ejecutor_id, _ = _sembrar(db_session, estado="pendiente")

    import app.api.devoluciones as modulo

    monkeypatch.setattr(modulo, "get_proveedor_pago", _proveedor_prohibido)

    r = auth_client.post(
        RUTA.format(devolucion_id=dev_id),
        headers=_headers(sub=ejecutor_id),
    )
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "TRANSICION_DEVOLUCION_INVALIDA"

    db_session.expire_all()
    dev = db_session.query(Devolucion).get(dev_id)
    assert dev is not None
    assert dev.estado == "pendiente"


def test_reintento_mismo_refund_sin_segundo_evento_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Borde P4: reintentar devuelve el mismo `mp_refund_id` sin duplicar."""
    dev_id, pago_id, turno_id, ejecutor_id, _ = _sembrar(db_session)
    headers = _headers(sub=ejecutor_id)

    r1 = auth_client.post(RUTA.format(devolucion_id=dev_id), headers=headers)
    assert r1.status_code == 200, r1.text
    r2 = auth_client.post(RUTA.format(devolucion_id=dev_id), headers=headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["mp_refund_id"] == r1.json()["mp_refund_id"]
    assert r2.json()["estado"] == "ejecutada"

    from app.infra.db.models import EventoPago, TurnoHistorial
    db_session.expire_all()
    eventos = db_session.query(EventoPago).filter_by(pago_id=pago_id).all()
    assert len([e for e in eventos if e.tipo_evento == "devolucion_ejecutada"]) == 1
    assert db_session.query(TurnoHistorial).filter_by(
        turno_id=turno_id, estado_nuevo="devuelto").count() == 1


def test_dos_ejecuciones_una_sola_ejecucion_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Invariante de concurrencia: dos ejecuciones → una sola ejecución.

    SQLite ignora `with_for_update()`: se valida la invariante observable
    secuencialmente. El bloqueo físico (`FOR UPDATE`) se prueba en PostgreSQL
    (tasks 8.2/8.3) con dos transacciones reales.
    """
    dev_id, pago_id, turno_id, ejecutor_id, _ = _sembrar(db_session)
    headers = _headers(sub=ejecutor_id)

    primera = auth_client.post(RUTA.format(devolucion_id=dev_id), headers=headers)
    segunda = auth_client.post(RUTA.format(devolucion_id=dev_id), headers=headers)
    assert primera.status_code == 200, primera.text
    assert segunda.status_code == 200, segunda.text
    assert primera.json()["mp_refund_id"] == segunda.json()["mp_refund_id"]

    from app.infra.db.models import EventoPago
    db_session.expire_all()
    dev = db_session.query(Devolucion).get(dev_id)
    assert dev is not None
    assert dev.estado == "ejecutada"
    assert dev.ejecutada_at is not None
    eventos = db_session.query(EventoPago).filter_by(pago_id=pago_id).all()
    assert len([e for e in eventos if e.tipo_evento == "devolucion_ejecutada"]) == 1


def test_pago_modo_mercadopago_503_sin_fallback_borde(
    auth_client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Borde P15: mercadopago no construido → 503 y la devolución sigue aprobada."""
    dev_id, pago_id, turno_id, ejecutor_id, _ = _sembrar(db_session)

    monkeypatch.setenv("PAGO_MODO", "mercadopago")
    monkeypatch.setenv("MP_ACCESS_TOKEN", "TEST-token-ficticio")
    monkeypatch.setenv("MP_PUBLIC_KEY", "TEST-public-ficticio")

    r = auth_client.post(
        RUTA.format(devolucion_id=dev_id),
        headers=_headers(sub=ejecutor_id),
    )
    assert r.status_code == 503, r.text
    assert r.json()["code"] == "PROVEEDOR_NO_DISPONIBLE"

    from app.infra.db.models import EventoPago, TurnoHistorial
    db_session.expire_all()
    dev = db_session.query(Devolucion).get(dev_id)
    assert dev is not None
    assert dev.estado == "aprobada"
    assert dev.mp_refund_id is None
    pago = db_session.query(Pago).get(pago_id)
    assert pago is not None
    assert pago.estado == "aprobado"
    turno = db_session.query(Turno).get(turno_id)
    assert turno is not None
    assert turno.estado == "cancelado"
    eventos = db_session.query(EventoPago).filter_by(pago_id=pago_id).all()
    assert not any(e.tipo_evento == "devolucion_ejecutada" for e in eventos)
    assert db_session.query(TurnoHistorial).filter_by(
        turno_id=turno_id, estado_nuevo="devuelto").count() == 0


def test_odontologo_ajeno_403_sin_invocar_proveedor_negocio(
    auth_client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Error P8: odontólogo ajeno → 403 antes de tocar al proveedor."""
    dev_id, _, _, ejecutor_id, _ = _sembrar(db_session)

    suf = uuid.uuid4().hex[:8]
    u = Usuario(
        email=f"od-ajeno-{suf}@clinica-ficticia.example.ar",
        password_hash="$2b$04$" + "a" * 53, rol="odontologo",
    )
    db_session.add(u)
    db_session.commit()
    od = Odontologo(user_id=u.id, monto_turno=Decimal("70000"),
                    monto_senia=Decimal("10000"))
    db_session.add(od)
    db_session.commit()
    ajeno_id = uuid.UUID(str(od.id))

    import app.api.devoluciones as modulo

    monkeypatch.setattr(modulo, "get_proveedor_pago", _proveedor_prohibido)

    r = auth_client.post(
        RUTA.format(devolucion_id=dev_id),
        headers=_headers("odontologo", sub=uuid.UUID(str(u.id)),
                         odontologo_id=ajeno_id),
    )
    assert r.status_code == 403, r.text

    db_session.expire_all()
    dev = db_session.query(Devolucion).get(dev_id)
    assert dev is not None
    assert dev.estado == "aprobada"
