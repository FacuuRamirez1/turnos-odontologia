"""Alta de devolución por cancelación C-08 (design D1).

`registrar_por_cancelacion()` es el ÚNICO punto de alta: la invoca el hook de
`domain/turnos/estados.py::transition()` para toda transición
`confirmado→cancelado` (staff, paciente por token, cancelación desde mail).

Reglas:
- solo con pago `aprobado` (no se devuelve lo que no se cobró);
- porcentaje desde `cotizar_devolucion()` con el MISMO `ahora` de la
  transición (el borde exacto coincide con la cotización previa);
- cotización 0 % → no escribe NADA (ni devolución, ni evento, ni recibo, ni
  aviso): el pago sigue `aprobado` y el turno queda `cancelado` (RN-SENIA-0);
- devolución `pendiente` + `evento_pago(devolucion_solicitada)` con actor en
  el mismo flush de la transición: si falla, el caller hace rollback y la
  cancelación no se persiste (atomicidad).

No encola el `aviso_devolucion`: eso ocurre al ejecutar/rechazar (grupo 6).
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.domain.devoluciones.calculo import calcular_monto_devolucion
from app.domain.pagos.repositories import resolver_pago_de_turno
from app.domain.turnos.cancelacion import cotizar_devolucion
from app.infra.db.models import Turno
from app.infra.db.models.devolucion import Devolucion
from app.infra.db.models.pago import EventoPago


def registrar_por_cancelacion(
    session: Session,
    turno: Turno,
    *,
    actor_tipo: str,
    actor_id: str,
    ahora: datetime,
    motivo: str | None = None,
    anticipacion_hs: int | None = None,
) -> Devolucion | None:
    """Crea `devolucion(pendiente)` + evento si hay pago aprobado y cuota > 0 %.

    No hace commit ni flush propio: la transición que lo invoca hace el flush
    único, de modo que un fallo revierte también el cambio de estado del turno.
    """
    pago = resolver_pago_de_turno(session, turno)
    if pago is None or str(pago.estado) != "aprobado":
        return None
    anticipacion = (
        anticipacion_hs if anticipacion_hs is not None
        else get_settings().anticipacion_min_hs
    )
    porcentaje = cotizar_devolucion(turno.inicio, anticipacion, ahora=ahora)
    if porcentaje <= 0:
        return None
    monto = calcular_monto_devolucion(pago.monto, porcentaje)
    devolucion = Devolucion(
        pago_id=pago.id,
        turno_id=turno.id,
        monto=monto,
        porcentaje=porcentaje,
        motivo=motivo,
        estado="pendiente",
        idempotency_key=f"dev_{pago.id}",
    )
    session.add(devolucion)
    session.add(EventoPago(
        pago_id=pago.id,
        tipo_evento="devolucion_solicitada",
        payload_json={
            "actor_id": actor_id,
            "porcentaje": porcentaje,
            "monto": str(monto),
        },
        actor=actor_tipo,
    ))
    return devolucion
