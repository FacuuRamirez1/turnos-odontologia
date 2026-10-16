"""Máquina de estados C-05 — seam único `transition()` (design D2, spec § cerrada).

- `TRANSICIONES: dict[(origen, destino)] → (actores_permitidos, guarda)`:
  único camino de código; cualquier otro par → `TransicionInvalida` (→422).
- `transition()`: valida par (422), actor-tipo (403), guarda temporal
  `no_show` exige `fin <= ahora` (422), lock optimista por `version`
  (mismatch → `VersionConflict`, →409), escribe `TurnoHistorial` en el
  mismo flush (mismo commit del caller, C-02 UnitOfWork).
- Ownership fino (paciente dueño / odontólogo propio) se exige en la capa
  API con `require_role()` + scoped (P8); aquí solo el tipo de actor.
- `IntegrityError` en flush → `VersionConflict` (la DB arbitra la carrera,
  la app traduce, design D3).
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infra.db.models import Turno, TurnoHistorial


class TransicionInvalida(Exception):
    """Par (origen, destino) fuera de la máquina cerrada → 422."""


class ActorNoAutorizado(Exception):
    """Tipo de actor no permitido para la transición → 403."""


class GuardaTemporalRechazada(Exception):
    """Guarda temporal incumplida (`no_show` pre-`fin`) → 422."""


class VersionConflict(Exception):
    """Lock optimista: otro escritor ganó la carrera → 409 reintentable."""


# (origen, destino) → (actores permitidos, exige fin <= ahora)
TRANSICIONES: dict[tuple[str, str], tuple[frozenset[str], bool]] = {
    ("creado", "confirmado"): (frozenset({"sistema"}), False),
    # Expiración TTL / pago rechazado (proposal § job; C-07 `rechazado→cancelado`):
    # solo el sistema puede sacar un turno de `creado` sin confirmarlo.
    ("creado", "cancelado"): (frozenset({"sistema"}), False),
    ("confirmado", "cancelado"): (
        frozenset({"paciente", "odontologo", "recepcionista", "admin"}), False),
    ("confirmado", "reprogramado"): (
        frozenset({"paciente", "odontologo", "recepcionista", "admin"}), False),
    ("confirmado", "atendido"): (
        frozenset({"odontologo", "recepcionista", "admin"}), False),
    ("confirmado", "no_show"): (
        frozenset({"odontologo", "recepcionista", "admin"}), True),
    ("cancelado", "devuelto"): (frozenset({"sistema"}), False),
}


def transition(
    session: Session,
    turno_id: UUID,
    destino: str,
    *,
    actor_tipo: str,
    actor_id: str,
    motivo: str | None = None,
    version_esperada: int | None = None,
    ahora: datetime | None = None,
) -> Turno:
    """Mueve el turno a `destino` + historial en el mismo flush.

    No hace commit: el caller (endpoint/UoW) confirma la transacción.
    """
    turno = session.query(Turno).filter(
        Turno.id == turno_id, Turno.is_active.is_(True)).first()
    if turno is None:
        raise TransicionInvalida("turno inexistente")
    origen = str(turno.estado)
    regla = TRANSICIONES.get((origen, destino))
    if regla is None:
        raise TransicionInvalida(f"transición {origen}→{destino} no permitida")
    actores, exige_fin_pasado = regla
    if actor_tipo not in actores:
        raise ActorNoAutorizado(f"actor {actor_tipo} no autorizado para {origen}→{destino}")
    if not actor_id:
        raise ActorNoAutorizado("actor sin identidad")
    referencia = ahora or datetime.now(UTC)
    fin = turno.fin
    if fin.tzinfo is None:
        fin = fin.replace(tzinfo=UTC)
    if exige_fin_pasado and fin > referencia:
        raise GuardaTemporalRechazada("no_show solo posterior al fin del turno")
    if version_esperada is not None and int(turno.version) != version_esperada:
        raise VersionConflict("el turno cambió; reintentar con la versión vigente")
    turno.estado = destino
    turno.version = int(turno.version) + 1
    session.add(TurnoHistorial(
        turno_id=turno_id, estado_anterior=origen, estado_nuevo=destino,
        actor_tipo=actor_tipo, actor_id=actor_id,
        fecha=referencia if referencia.tzinfo else referencia.replace(tzinfo=UTC),
        motivo=motivo,
    ))
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise VersionConflict("carrera concurrente; reintentar") from exc
    return turno
