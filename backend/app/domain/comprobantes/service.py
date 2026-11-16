"""Servicio de comprobantes C-08 (design D6) - recibo interno por pago/devolucion.

`emitir_recibo_pago` y `emitir_recibo_devolucion` son idempotentes: si ya existe
el comprobante (UNIQUE parcial por pago/devolucion), devuelven el existente.
`simulado` se fija al emitir (`pago.proveedor == 'simulado'`) y no se recalcula.
`tipo` es `recibo_interno` y `cae` queda null en v1 (P13).
"""

from decimal import Decimal
from typing import cast

from sqlalchemy.orm import Session

from app.infra.db.models import Comprobante, Devolucion, Odontologo, Paciente, Pago, Turno, Usuario

CONCEPTO_PAGO = "pago"
CONCEPTO_DEVOLUCION = "devolucion"


def emitir_recibo_pago(session: Session, pago: Pago) -> Comprobante:
    """Emite el recibo del pago (concepto `pago`) si todavia no existe (D6)."""
    existente = (
        session.query(Comprobante)
        .filter(Comprobante.pago_id == pago.id, Comprobante.concepto == CONCEPTO_PAGO)
        .first()
    )
    if existente is not None:
        return existente
    return _emitir(
        session, pago=pago, devolucion=None, concepto=CONCEPTO_PAGO, monto=pago.monto,
    )


def emitir_recibo_devolucion(session: Session, devolucion: Devolucion) -> Comprobante | None:
    """Emite el recibo de la devolucion (concepto `devolucion`) si no existe (D6)."""
    existente = (
        session.query(Comprobante)
        .filter(
            Comprobante.devolucion_id == devolucion.id,
            Comprobante.concepto == CONCEPTO_DEVOLUCION,
        )
        .first()
    )
    if existente is not None:
        return existente
    pago = cast(Pago | None, session.get(Pago, devolucion.pago_id))
    if pago is None:
        return None
    return _emitir(
        session, pago=pago, devolucion=devolucion, concepto=CONCEPTO_DEVOLUCION,
        monto=devolucion.monto,
    )


def _emitir(
    session: Session, *, pago: Pago, devolucion: Devolucion | None, concepto: str, monto: Decimal,
) -> Comprobante:
    comprobante = Comprobante(
        pago_id=pago.id,
        devolucion_id=devolucion.id if devolucion is not None else None,
        turno_id=pago.turno_id,
        tipo="recibo_interno",
        concepto=concepto,
        monto=monto,
        moneda=str(pago.moneda),
        cae=None,
        simulado=str(pago.proveedor) == "simulado",
        payload_json=_snapshot(
            session, pago=pago, devolucion=devolucion, concepto=concepto, monto=monto,
        ),
    )
    session.add(comprobante)
    return comprobante


def _snapshot(
    session: Session, *, pago: Pago, devolucion: Devolucion | None, concepto: str, monto: Decimal,
) -> dict[str, object]:
    turno = (
        cast(Turno | None, session.get(Turno, pago.turno_id))
        if pago.turno_id is not None
        else None
    )
    paciente = (
        cast(Paciente | None, session.get(Paciente, turno.paciente_id))
        if turno is not None
        else None
    )
    odontologo = (
        cast(Odontologo | None, session.get(Odontologo, pago.odontologo_id))
        if pago.odontologo_id is not None
        else None
    )
    usuario = (
        cast(Usuario | None, session.get(Usuario, odontologo.user_id))
        if odontologo is not None
        else None
    )
    return {
        "concepto": concepto,
        "paciente_nombre": str(paciente.nombre) if paciente is not None else "",
        "paciente_apellido": str(paciente.apellido) if paciente is not None else "",
        "odontologo": str(usuario.email) if usuario is not None else "",
        "fecha_turno": turno.inicio.isoformat() if turno is not None else "",
        "porcentaje": int(devolucion.porcentaje) if devolucion is not None else None,
        "monto": str(monto),
    }
