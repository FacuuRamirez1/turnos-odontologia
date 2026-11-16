"""Tests C-08 task 1.4 — modelos Devolucion/Comprobante (RED primero).

Inserciones adversas directas a la DB (SQLite en memoria: CHECK/UNIQUE reales).
Las barreras que son exclusivas de PostgreSQL (triggers de transición y de
`monto <= pago.monto`, REVOKE UPDATE/DELETE) se verifican contra un PG
descartable con `app/tests/sql/migration_006_adversarial.sql` (ver evidencia
del apply) y estáticamente en `test_migration_006.py`.

Escenarios (U2 feliz / negocio / borde) por restricción.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infra.db.models import Comprobante, Devolucion, EventoPago, Pago
from app.infra.db.models.pago import TIPOS_EVENTO_PAGO
from app.tests.test_pagos_modelos import _sembrar_turno


def _pago(db: Session, monto: str = "10000.00") -> Pago:
    turno_id, od_id = _sembrar_turno(db)
    p = Pago(
        turno_id=turno_id, odontologo_id=od_id, monto=Decimal(monto),
        proveedor="simulado", mp_payment_id=f"sim_pay_{uuid.uuid4()}",
        estado="aprobado", idempotency_key=f"idem-{uuid.uuid4().hex[:12]}",
    )
    db.add(p)
    db.flush()
    return p


def _usuario_id(db: Session) -> uuid.UUID:
    from app.infra.db.models import Usuario

    u = Usuario(email=f"rec-{uuid.uuid4().hex[:8]}@clinica-ficticia.example.ar",
                password_hash="$2b$04$" + "p" * 53, rol="recepcionista")
    db.add(u)
    db.flush()
    return uuid.UUID(str(u.id))


def _dev(pago: Pago, *, monto: str = "6000.00", porcentaje: int = 60, **kw: object) -> Devolucion:
    return Devolucion(
        pago_id=pago.id, turno_id=pago.turno_id, monto=Decimal(monto),
        porcentaje=porcentaje, idempotency_key=f"dev_{pago.id}", **kw,
    )


def test_devolucion_60_y_100_validas_feliz(db_session: Session) -> None:
    """Feliz: 60 % y 100 % se persisten como `pendiente` con defaults."""
    p1, p2 = _pago(db_session), _pago(db_session)
    d1 = _dev(p1)
    d2 = _dev(p2, monto="10000.00", porcentaje=100)
    db_session.add_all([d1, d2])
    db_session.flush()
    assert d1.estado == "pendiente" and d1.mp_refund_id is None
    assert d2.porcentaje == 100 and d2.monto == Decimal("10000.00")


def test_segunda_devolucion_por_pago_rechazada_negocio(db_session: Session) -> None:
    """Negocio: UNIQUE(pago_id) — un pago, una devolución (P4/P6)."""
    p = _pago(db_session)
    db_session.add(_dev(p))
    db_session.flush()
    db_session.add(Devolucion(
        pago_id=p.id, turno_id=p.turno_id, monto=Decimal("1.00"),
        porcentaje=60, idempotency_key="otra-key",
    ))
    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize("porcentaje", [0, 50, 101, -60])
def test_porcentaje_fuera_de_100_60_rechazado_negocio(
    db_session: Session, porcentaje: int
) -> None:
    """Negocio/borde: la cotización 0 % NO se persiste; 50 u otros tampoco."""
    p = _pago(db_session)
    db_session.add(_dev(p, porcentaje=porcentaje))
    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize("monto", ["0.00", "-1.00"])
def test_monto_cero_o_negativo_rechazado_borde(db_session: Session, monto: str) -> None:
    """Borde: CHECK monto > 0."""
    p = _pago(db_session)
    db_session.add(_dev(p, monto=monto))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_estado_fuera_de_la_lista_cerrada_rechazado(db_session: Session) -> None:
    """Negocio: estados cerrados pendiente|aprobada|rechazada|ejecutada."""
    p = _pago(db_session)
    db_session.add(_dev(p, estado="devuelta"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_ejecutada_sin_mp_refund_id_rechazada_negocio(db_session: Session) -> None:
    """Negocio: CHECK estado='ejecutada' => mp_refund_id NOT NULL."""
    p = _pago(db_session)
    uid = _usuario_id(db_session)
    now = datetime.now(UTC)
    db_session.add(_dev(p, estado="ejecutada", aprobada_por=uid, aprobada_at=now,
                        ejecutada_por=uid, ejecutada_at=now))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_ejecutada_completa_con_refund_y_actores_feliz(db_session: Session) -> None:
    """Feliz: ejecutada con mp_refund_id + actor/fecha de aprobación y ejecución."""
    p = _pago(db_session)
    uid = _usuario_id(db_session)
    now = datetime.now(UTC)
    d = _dev(p, estado="ejecutada", mp_refund_id="sim_refund_x", aprobada_por=uid,
             aprobada_at=now, ejecutada_por=uid, ejecutada_at=now)
    db_session.add(d)
    db_session.flush()
    assert d.estado == "ejecutada"


def test_aprobada_sin_actor_ni_fecha_rechazada_borde(db_session: Session) -> None:
    """Borde: aprobada exige aprobada_por/at."""
    p = _pago(db_session)
    db_session.add(_dev(p, estado="aprobada"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_rechazada_exige_actor_fecha_y_motivo(db_session: Session) -> None:
    """Borde: rechazada exige rechazada_por/at + motivo_rechazo; completa es válida."""
    p1, p2 = _pago(db_session), _pago(db_session)
    uid = _usuario_id(db_session)
    db_session.add(_dev(p1, estado="rechazada", rechazada_por=uid,
                        rechazada_at=datetime.now(UTC)))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()
    p2 = _pago(db_session)
    uid = _usuario_id(db_session)
    ok = _dev(p2, estado="rechazada", rechazada_por=uid,
              rechazada_at=datetime.now(UTC), motivo_rechazo="fuera de política")
    db_session.add(ok)
    db_session.flush()
    assert ok.estado == "rechazada"


def test_idempotency_key_y_mp_refund_id_unicos(db_session: Session) -> None:
    """Negocio: UNIQUE(idempotency_key) y UNIQUE(mp_refund_id) (P4)."""
    p1, p2 = _pago(db_session), _pago(db_session)
    uid = _usuario_id(db_session)
    now = datetime.now(UTC)
    db_session.add(_dev(p1))
    db_session.flush()
    dup = _dev(p2)
    dup.idempotency_key = f"dev_{p1.id}"
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()

    q1, q2 = _pago(db_session), _pago(db_session)
    uid = _usuario_id(db_session)
    for q in (q1, q2):
        d = _dev(q, estado="ejecutada", mp_refund_id="sim_refund_dup", aprobada_por=uid,
                 aprobada_at=now, ejecutada_por=uid, ejecutada_at=now)
        db_session.add(d)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_evento_devolucion_rechazada_aceptado_feliz(db_session: Session) -> None:
    """Feliz: `devolucion_rechazada` entra en la lista cerrada de evento_pago."""
    assert "devolucion_rechazada" in TIPOS_EVENTO_PAGO
    p = _pago(db_session)
    db_session.add(EventoPago(pago_id=p.id, tipo_evento="devolucion_rechazada",
                              actor="recepcionista", payload_json={"motivo": "x"}))
    db_session.flush()


def test_evento_tipo_inventado_sigue_rechazado(db_session: Session) -> None:
    """Error: la lista sigue cerrada."""
    p = _pago(db_session)
    db_session.add(EventoPago(pago_id=p.id, tipo_evento="inventado", actor="sistema"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def _comprobante(p: Pago, concepto: str = "pago", devolucion_id: uuid.UUID | None = None,
                 monto: str = "10000.00") -> Comprobante:
    return Comprobante(
        pago_id=p.id, turno_id=p.turno_id, devolucion_id=devolucion_id,
        concepto=concepto, monto=Decimal(monto), simulado=True,
        payload_json={"paciente": "Ana Ficticia"},
    )


def test_comprobante_pago_feliz_con_numero_y_defaults(db_session: Session) -> None:
    """Feliz: recibo_interno, ARS, cae null, número RI-NNNNNN correlativo distinto."""
    p1, p2 = _pago(db_session), _pago(db_session)
    c1, c2 = _comprobante(p1), _comprobante(p2)
    db_session.add_all([c1, c2])
    db_session.flush()
    assert c1.tipo == "recibo_interno" and c1.moneda == "ARS" and c1.cae is None
    assert c1.numero.startswith("RI-") and len(c1.numero) == 9
    assert c1.numero != c2.numero


def test_segundo_recibo_de_pago_rechazado_negocio(db_session: Session) -> None:
    """Negocio: UNIQUE parcial por pago con concepto 'pago'."""
    p = _pago(db_session)
    db_session.add(_comprobante(p))
    db_session.flush()
    db_session.add(_comprobante(p))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_recibo_de_devolucion_coexiste_y_es_unico(db_session: Session) -> None:
    """Borde: pago y devolución conviven (2 recibos); el de devolución no se duplica."""
    p = _pago(db_session)
    d = _dev(p)
    db_session.add(d)
    db_session.flush()
    db_session.add_all([_comprobante(p), _comprobante(p, "devolucion", d.id, "6000.00")])
    db_session.flush()
    db_session.add(_comprobante(p, "devolucion", d.id, "6000.00"))
    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize("concepto,con_devolucion", [("devolucion", False), ("pago", True)])
def test_concepto_incoherente_con_devolucion_id_rechazado(
    db_session: Session, concepto: str, con_devolucion: bool
) -> None:
    """Negocio: concepto='devolucion' <=> devolucion_id NOT NULL."""
    p = _pago(db_session)
    d = _dev(p)
    db_session.add(d)
    db_session.flush()
    db_session.add(_comprobante(p, concepto, d.id if con_devolucion else None))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_comprobante_tipo_y_concepto_cerrados(db_session: Session) -> None:
    """Negocio: tipo y concepto fuera de lista cerrada se rechazan."""
    p = _pago(db_session)
    c = _comprobante(p)
    c.tipo = "factura_z"
    db_session.add(c)
    with pytest.raises(IntegrityError):
        db_session.flush()
