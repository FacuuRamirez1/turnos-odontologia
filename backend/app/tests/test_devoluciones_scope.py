"""Tests C-08 task 3.1 — scope P8 del repositorio de devoluciones (RED primero).

Escenarios (U2 feliz / negocio / borde):
- feliz: recepcionista lista devoluciones de TODOS los profesionales;
- negocio: odontólogo A solo ve las propias y `get` de una de B devuelve None
  (no filtra existencia ajena);
- borde: odontólogo sin `odontologo_id` en la identidad → 403 fail-closed.

El filtro vive en el repositorio (JOIN turno), nunca en el endpoint (P8).
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.security.dependencies import Identity
from app.domain.devoluciones.repositories import (
    DevolucionFueraDeScope,
    DevolucionRepository,
)
from app.infra.db.models import (
    Devolucion,
    Odontologo,
    Paciente,
    Pago,
    Turno,
    Usuario,
)


def _sembrar_odontologo(db_session: Session, sufijo: str) -> uuid.UUID:
    u = Usuario(
        email=f"od-scope-{sufijo}@clinica-ficticia.example.ar",
        password_hash="$2b$04$" + "s" * 53,
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


def _sembrar_devolucion(db_session: Session, od_id: uuid.UUID) -> Devolucion:
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
        minutes=(uuid.uuid4().int % 2000) * 30
    )
    turno = Turno(
        paciente_id=pac.id,
        odontologo_id=od_id,
        inicio=inicio,
        fin=inicio + timedelta(minutes=30),
        estado="cancelado",
        canal="web",
        idempotency_key=f"key-scope-{suf}",
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
        idempotency_key=f"idem-scope-{suf}",
    )
    db_session.add(pago)
    db_session.commit()
    dev = Devolucion(
        pago_id=pago.id,
        turno_id=turno.id,
        monto=Decimal("6000.00"),
        porcentaje=60,
        motivo="cancelación",
        estado="pendiente",
        idempotency_key=f"dev_{pago.id}",
    )
    db_session.add(dev)
    db_session.commit()
    db_session.refresh(dev)
    return dev


def _ident(rol: str, odontologo_id: str | None = None) -> Identity:
    return Identity(
        sub=f"user-{uuid.uuid4().hex[:8]}",
        rol=rol,
        odontologo_id=odontologo_id,
        jti=f"jti-{uuid.uuid4().hex[:8]}",
    )


def test_recepcionista_lista_todas_feliz(db_session: Session) -> None:
    """Feliz: recepcionista (sin scope) ve devoluciones de todos los profesionales."""
    od_a = _sembrar_odontologo(db_session, "a")
    od_b = _sembrar_odontologo(db_session, "b")
    dev_a = _sembrar_devolucion(db_session, od_a)
    dev_b = _sembrar_devolucion(db_session, od_b)

    repo = DevolucionRepository.scoped(db_session, _ident("recepcionista"))
    ids = {uuid.UUID(str(d.id)) for d in repo.list()}

    assert ids == {uuid.UUID(str(dev_a.id)), uuid.UUID(str(dev_b.id))}


def test_odontologo_solo_ve_las_propias_y_get_ajena_403_negocio(
    db_session: Session,
) -> None:
    """Negocio: odontólogo A lista solo lo propio; get de B → 403 (sin datos)."""
    od_a = _sembrar_odontologo(db_session, "a2")
    od_b = _sembrar_odontologo(db_session, "b2")
    dev_a = _sembrar_devolucion(db_session, od_a)
    dev_b = _sembrar_devolucion(db_session, od_b)

    repo = DevolucionRepository.scoped(db_session, _ident("odontologo", str(od_a)))

    assert [uuid.UUID(str(d.id)) for d in repo.list()] == [uuid.UUID(str(dev_a.id))]
    with pytest.raises(DevolucionFueraDeScope):
        repo.get(dev_b.id)
    assert repo.get(dev_a.id) is not None


def test_odontologo_sin_perfil_denegado_403_borde(db_session: Session) -> None:
    """Borde (P8 fail-closed): identidad odontólogo sin odontologo_id → 403."""
    with pytest.raises(HTTPException) as excinfo:
        DevolucionRepository.scoped(db_session, _ident("odontologo", None))

    assert excinfo.value.status_code == 403
