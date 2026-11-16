"""Tests C-08 task 2.2 — `resolver_pago_de_turno` (RED primero).

Extrae la resolución inline de `POST /reservas/{id}/reprogramar` (design
Context): el turno nuevo hereda `pago_id`, pero `Pago.turno_id` sigue
apuntando al turno original. Resolver "pago del turno" = `turno.pago_id` o,
si es null, `Pago.turno_id == turno.id`.

Escenarios (U2 feliz / negocio / borde):
- feliz: turno con `pago_id` → ese pago (aunque haya otro pago del turno);
- negocio: turno sin `pago_id` → se resuelve por `Pago.turno_id`;
- borde: turno sin pago → `None` (no revienta).
"""

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.pagos.repositories import resolver_pago_de_turno
from app.infra.db.models import Pago, Turno
from app.tests.test_pagos_modelos import _sembrar_turno


def _pago(db_session: Session, turno_id: uuid.UUID, od_id: uuid.UUID) -> Pago:
    pago = Pago(
        turno_id=turno_id, odontologo_id=od_id, monto=Decimal("10000.00"),
        moneda="ARS", proveedor="simulado",
        mp_payment_id=f"sim_pay_{uuid.uuid4()}",
        estado="aprobado", idempotency_key=f"idem-{uuid.uuid4().hex[:12]}",
    )
    db_session.add(pago)
    db_session.commit()
    return pago


def test_turno_con_pago_id_resuelve_ese_pago_feliz(db_session: Session) -> None:
    """Feliz: `turno.pago_id` manda sobre cualquier otro pago del turno."""
    turno_id, od_id = _sembrar_turno(db_session)
    elegido = _pago(db_session, turno_id, od_id)
    _pago(db_session, turno_id, od_id)  # señuelo: mismo turno, otro id
    turno = db_session.get(Turno, turno_id)
    assert turno is not None
    turno.pago_id = elegido.id
    db_session.commit()

    resuelto = resolver_pago_de_turno(db_session, turno)

    assert resuelto is not None and resuelto.id == elegido.id


def test_turno_sin_pago_id_resuelve_por_turno_id_negocio(db_session: Session) -> None:
    """Negocio: sin `pago_id` (p. ej. turno original) se busca por `Pago.turno_id`."""
    turno_id, od_id = _sembrar_turno(db_session)
    pago = _pago(db_session, turno_id, od_id)
    turno = db_session.get(Turno, turno_id)
    assert turno is not None and turno.pago_id is None

    resuelto = resolver_pago_de_turno(db_session, turno)

    assert resuelto is not None and resuelto.id == pago.id


def test_turno_sin_pago_resuelve_none_borde(db_session: Session) -> None:
    """Borde: turno sin `pago_id` ni fila `pago` → `None`, sin excepción."""
    turno_id, _od_id = _sembrar_turno(db_session)
    turno = db_session.get(Turno, turno_id)
    assert turno is not None

    assert resolver_pago_de_turno(db_session, turno) is None
