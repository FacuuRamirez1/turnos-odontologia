"""Ocupados del motor C-04 cableados a `turno` C-05 (design D7, delta spec).

`ocupados_rango()`: turnos del profesional que solapan `[desde, hasta)` en
estado `confirmado` o `creado` no-vencido (computado — el job solo formaliza).
`cancelado`, `reprogramado` (origen), `atendido`, `no_show`, `devuelto`
liberan; `creado` vencido cuenta libre aunque siga en ese estado.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.turnos.expiracion import esta_vencido
from app.infra.db.models import Turno


def ocupados_rango(
    session: Session,
    odontologo_id: UUID,
    desde: datetime,
    hasta: datetime,
    ttl_min: int = 15,
    ahora: datetime | None = None,
) -> list[tuple[datetime, datetime]]:
    """Pares (inicio, fin) que restan del motor en el rango (design D7)."""
    filas = (
        session.query(Turno)
        .filter(
            Turno.odontologo_id == odontologo_id,
            Turno.is_active.is_(True),
            Turno.estado.in_(["creado", "confirmado"]),
            Turno.inicio < hasta,
            Turno.fin > desde,
        )
        .all()
    )
    referencia = ahora
    salida: list[tuple[datetime, datetime]] = []
    for fila in filas:
        if str(fila.estado) == "creado" and esta_vencido(fila, ttl_min, referencia):
            continue
        salida.append((fila.inicio, fila.fin))
    return salida


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def hay_solape(
    session: Session,
    odontologo_id: UUID,
    inicio: datetime,
    fin: datetime,
    ttl_min: int = 15,
    ahora: datetime | None = None,
    excluir_turno_id: UUID | None = None,
) -> bool:
    """True si el rango choca con un turno activo (app-level, pre-INSERT).

    La DB (UNIQUE/EXCLUDE en 003) es el árbitro final bajo carrera; esto
    evita el INSERT inválido en el caso común para responder 409/422.
    """
    candidatos = ocupados_rango(session, odontologo_id, inicio, fin, ttl_min, ahora)
    if excluir_turno_id is not None:
        filas = (
            session.query(Turno)
            .filter(Turno.odontologo_id == odontologo_id,
                    Turno.is_active.is_(True),
                    Turno.id == excluir_turno_id)
            .all()
        )
        propios = {(f.inicio, f.fin) for f in filas}
        candidatos = [c for c in candidatos if c not in propios]
    ini, fin_ = _utc(inicio), _utc(fin)
    for o_ini, o_fin in candidatos:
        o_ini, o_fin = _utc(o_ini), _utc(o_fin)
        if ini < o_fin and o_ini < fin_:
            return True
    return False
