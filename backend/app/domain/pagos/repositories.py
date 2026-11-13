"""Repositorios C-07 pagos — Pago (scopeada por odontólogo) + EventoPago (global).

Siguen el patrón `BaseRepository[T]` + `UnitOfWork` de `infra/db/repository.py`:
- `Pago` tiene `odontologo_id` → scopeada, constructor exige `odontologo_id` (P8);
- `EventoPago` no tiene `odontologo_id` → lecturas globales, sin update/delete
  (append-only, P9: el rol app no tiene UPDATE/DELETE sobre esta tabla).
"""

import uuid
from typing import TypeVar, cast

from sqlalchemy.orm import Session

from app.infra.db.models.pago import EventoPago, Pago
from app.infra.db.repository import BaseRepository

T = TypeVar("T")


class PagoRepository(BaseRepository[Pago]):
    """Repositorio de Pago, scopeado por odontologo_id (P8, fail-closed)."""

    def __init__(self, session: Session, odontologo_id: uuid.UUID | None) -> None:
        super().__init__(session, Pago, odontologo_id=odontologo_id)

    def get_by_idempotency_key(self, idempotency_key: str) -> Pago | None:
        """Busca pago por idempotency_key dentro del scope (P4)."""
        return cast(
            Pago | None,
            self._base_query().where(
                Pago.idempotency_key == idempotency_key  # type: ignore[attr-defined]
            ).first(),
        )

    def get_by_mp_payment_id(self, mp_payment_id: str) -> Pago | None:
        """Busca pago por mp_payment_id dentro del scope (idempotencia webhook)."""
        return cast(
            Pago | None,
            self._base_query().where(
                Pago.mp_payment_id == mp_payment_id  # type: ignore[attr-defined]
            ).first(),
        )


class EventoPagoRepository(BaseRepository[EventoPago]):
    """Repositorio de EventoPago, lecturas globales, append-only (P9).

    Sin `odontologo_id` en el modelo: no es scopeada. Sin métodos de
    escritura pública (add/heredada se usa solo internamente); sin update/delete.
    """

    def __init__(self, session: Session) -> None:
        super().__init__(session, EventoPago, odontologo_id=None)

    def get_by_pago(self, pago_id: object) -> list[EventoPago]:
        """Lista eventos de un pago, ordenados por created_at."""
        return list(
            self._session.query(EventoPago)
            .filter(EventoPago.pago_id == pago_id)  # type: ignore[attr-defined]
            .order_by(EventoPago.created_at)  # type: ignore[attr-defined]
            .all()
        )

    def add_evento(self, pago_id: object, tipo_evento: str,
                   payload_json: dict, actor: str) -> EventoPago:
        """Inserta un evento append-only (solo INSERT, nunca UPDATE/DELETE)."""
        ev = EventoPago(pago_id=pago_id, tipo_evento=tipo_evento,
                        payload_json=payload_json, actor=actor)
        self._session.add(ev)
        self._session.flush()
        return ev
