"""Expiración TTL de pre-reservas C-05 (design D4, spec § pre-reserva).

- `expira_en`: `created_at + RESERVA_TTL_MIN` (default 15, env C-01).
- `slot_libre_por_computo`: expiración computada — `creado` vencido cuenta
  libre aunque el job aún no lo haya formalizado (A5 robusto sin worker).
- `expirar_vencidos`: job intervalar (60 s en worker Compose): `creado`
  vencido → `cancelado` (`sistema`/`ttl_expirado`) vía `transition()` para
  reusar historial + lock; idempotente por guarda de estado; batch con
  `SELECT ... FOR UPDATE SKIP LOCKED` en PG (patrón de colas; en SQLite
  de tests se omite el lock — mismo resultado, sin sintaxis PG).
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.turnos.estados import transition
from app.infra.db.models import Turno

ESTADOS_OCUPAN = frozenset({"creado", "confirmado"})
ESTADOS_LIBERAN = frozenset({"cancelado", "reprogramado", "atendido", "no_show", "devuelto"})


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


def expira_en(turno: Turno, ttl_min: int = 15) -> datetime:
    """Instante en que la pre-reserva vence (creación + TTL)."""
    return _utc(turno.created_at) + timedelta(minutes=ttl_min)


def esta_vencido(turno: Turno, ttl_min: int = 15,
                 ahora: datetime | None = None) -> bool:
    """Solo `creado` puede vencer; el resto de estados es inmune al TTL."""
    if str(turno.estado) != "creado":
        return False
    referencia = _utc(ahora or datetime.now(UTC))
    return expira_en(turno, ttl_min) <= referencia


def slot_libre_por_computo(turno: Turno, ttl_min: int = 15,
                           ahora: datetime | None = None) -> bool:
    """El hueco está ofrecible: estado liberador o `creado` ya vencido."""
    if str(turno.estado) in ESTADOS_LIBERAN:
        return True
    if str(turno.estado) == "creado" and esta_vencido(turno, ttl_min, ahora):
        return True
    return False


def expirar_vencidos(session: Session, ttl_min: int = 15,
                     ahora: datetime | None = None,
                     limite: int = 100) -> int:
    """Formaliza `creado` vencidos → `cancelado`; retorna cuántos (idempotente)."""
    referencia = _utc(ahora or datetime.now(UTC))
    corte = referencia - timedelta(minutes=ttl_min)
    query = session.query(Turno).filter(
        Turno.estado == "creado",
        Turno.is_active.is_(True),
    ).order_by(Turno.created_at.asc()).limit(limite)
    bind = session.get_bind()
    dialecto = bind.dialect.name if bind is not None else "sqlite"
    if dialecto == "postgresql":
        query = query.with_for_update(skip_locked=True)
    candidatos = list(query.all())
    vencidos = [t for t in candidatos if _utc(t.created_at) <= _utc(corte)]
    for turno in vencidos:
        transition(session, UUID(str(turno.id)), "cancelado",
                   actor_tipo="sistema", actor_id="sistema",
                   motivo="ttl_expirado", ahora=referencia)
    session.flush()
    return len(vencidos)
