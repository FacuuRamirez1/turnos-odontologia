"""Tests C-07 task 1.2 — repositorios Pago/EventoPago (RED primero).

Escenarios:
- feliz: PagoRepository.get devuelve pago por id; list filtra por odontologo_id (scope P8);
- negocio: get con id inexistente → None;
- borde: evento_pago no expone métodos de modificación (append-only, P9).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import update as sa_update
from sqlalchemy.orm import Session

from app.domain.pagos.repositories import EventoPagoRepository, PagoRepository


def _sembrar_odonto_paciente_turno(db_session: Session) -> tuple[uuid.UUID, uuid.UUID]:
    from app.infra.db.models import Odontologo, Paciente, Turno, Usuario

    h = "$2b$04$" + "r" * 53
    suf = uuid.uuid4().hex[:8]
    u = Usuario(email=f"od-r-{suf}@clinica-ficticia.example.ar",
                password_hash=h, rol="odontologo")
    db_session.add(u)
    db_session.commit()
    od = Odontologo(user_id=u.id, monto_turno=70000, monto_senia=65000)
    db_session.add(od)
    db_session.commit()
    od_id = uuid.UUID(str(od.id))
    pac = Paciente(dni=f"99{uuid.uuid4().int % 90000000 + 10000000:08d}",
                   nombre="Ana", apellido="Ficticia",
                   consentimiento_datos=True,
                   consentimiento_fecha=datetime(2026, 10, 1, 9, 0, tzinfo=UTC))
    db_session.add(pac)
    db_session.commit()
    t = Turno(paciente_id=pac.id, odontologo_id=od_id,
              inicio=datetime(2026, 10, 5, 9, 0, tzinfo=UTC),
              fin=datetime(2026, 10, 5, 9, 30, tzinfo=UTC),
              estado="creado", canal="web",
              idempotency_key=f"key-r-{uuid.uuid4().hex[:12]}")
    db_session.add(t)
    db_session.commit()
    return od_id, uuid.UUID(str(t.id))


def _crear_pago(db_session: Session, od_id: uuid.UUID, turno_id: uuid.UUID,
                estado: str = "pendiente") -> uuid.UUID:
    from app.infra.db.models.pago import Pago

    p = Pago(turno_id=turno_id, odontologo_id=od_id, monto=65000,
             proveedor="simulado", mp_payment_id=f"sim_pay_{uuid.uuid4()}",
             estado=estado, idempotency_key=f"idem-{uuid.uuid4().hex[:12]}")
    db_session.add(p)
    db_session.flush()
    return uuid.UUID(str(p.id))


def test_pago_repository_get_por_id_feliz(db_session: Session) -> None:
    """Feliz: PagoRepository.get devuelve el pago por id."""
    od_id, turno_id = _sembrar_odonto_paciente_turno(db_session)
    pago_id = _crear_pago(db_session, od_id, turno_id)
    repo = PagoRepository(db_session, odontologo_id=od_id)
    pago = repo.get(pago_id)
    assert pago is not None
    assert uuid.UUID(str(pago.id)) == pago_id
    assert pago.estado == "pendiente"


def test_pago_repository_get_inexistente_none(db_session: Session) -> None:
    """Negocio: get con id inexistente → None."""
    repo = PagoRepository(db_session, odontologo_id=uuid.uuid4())
    assert repo.get(uuid.uuid4()) is None


def test_pago_repository_scope_por_odontologo(db_session: Session) -> None:
    """Borde: list filtra por odontologo_id del constructor (P8, fail-closed)."""
    od_id, turno_id = _sembrar_odonto_paciente_turno(db_session)
    _crear_pago(db_session, od_id, turno_id)
    repo = PagoRepository(db_session, odontologo_id=od_id)
    pagos = repo.list()
    assert len(pagos) == 1


def test_pago_repository_get_by_idempotency_key_triangulate(db_session: Session) -> None:
    """Triangulate: get_by_idempotency_key encuentra el pago por su key."""
    from app.infra.db.models.pago import Pago

    od_id, turno_id = _sembrar_odonto_paciente_turno(db_session)
    key = f"idem-{uuid.uuid4().hex[:12]}"
    pago_id = _crear_pago(db_session, od_id, turno_id)
    # Sobreescribimos la idempotency_key creada por _crear_pago
    from sqlalchemy import update as sa_update

    db_session.execute(
        sa_update(Pago).where(Pago.id == pago_id).values(idempotency_key=key)
    )
    db_session.flush()
    repo = PagoRepository(db_session, odontologo_id=od_id)
    encontrado = repo.get_by_idempotency_key(key)
    assert encontrado is not None
    assert uuid.UUID(str(encontrado.id)) == pago_id


def test_pago_repository_get_by_mp_payment_id_triangulate(db_session: Session) -> None:
    """Triangulate: get_by_mp_payment_id encuentra el pago por mp_payment_id."""
    from app.infra.db.models.pago import Pago

    od_id, turno_id = _sembrar_odonto_paciente_turno(db_session)
    mp_id = f"sim_pay_{uuid.uuid4()}"
    pago_id = _crear_pago(db_session, od_id, turno_id)
    db_session.execute(
        sa_update(Pago).where(Pago.id == pago_id).values(mp_payment_id=mp_id)
    )
    db_session.flush()
    repo = PagoRepository(db_session, odontologo_id=od_id)
    encontrado = repo.get_by_mp_payment_id(mp_id)
    assert encontrado is not None
    assert uuid.UUID(str(encontrado.id)) == pago_id


def test_evento_pago_repository_get_by_pago_triangulate(db_session: Session) -> None:
    """Triangulate: get_by_pago lista los eventos de un pago ordenados."""
    od_id, turno_id = _sembrar_odonto_paciente_turno(db_session)
    pago_id = _crear_pago(db_session, od_id, turno_id)
    repo = EventoPagoRepository(db_session)
    repo.add_evento(pago_id, "creado", {"monto": 65000}, "sistema")
    repo.add_evento(pago_id, "webhook_recibido", {"status": "approved"}, "sistema")
    eventos = repo.get_by_pago(pago_id)
    assert len(eventos) == 2
    assert eventos[0].tipo_evento == "creado"
    assert eventos[1].tipo_evento == "webhook_recibido"


def test_evento_pago_repository_sin_update_delete(db_session: Session) -> None:
    """Borde: EventoPagoRepository no expone métodos de actualización (append-only, P9)."""
    repo = EventoPagoRepository(db_session)
    assert not hasattr(repo, "update")
    assert not hasattr(repo, "delete")
