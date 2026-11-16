"""Repositorio de `Devolucion` C-08 — scope P8 forzado en el repositorio.

`Devolucion` no tiene `odontologo_id`: el dueño se resuelve por el turno
(`JOIN turno … WHERE turno.odontologo_id = :propio`). El filtro se construye
ACÁ, nunca en el endpoint: odontólogo solo ve/actúa sobre lo propio;
recepcionista/admin ven todo. Identidad odontólogo sin perfil → 403
fail-closed (`scoped_odontologo_id`, P8).
"""

import uuid

from sqlalchemy.orm import Query, Session

from app.core.security.dependencies import Identity, scoped_odontologo_id
from app.infra.db.models import Devolucion, Turno


class DevolucionFueraDeScope(Exception):
    """Existe pero pertenece a otro profesional → 403 (sin exponer datos)."""


class DevolucionRepository:
    """Lectura de devoluciones con el alcance del rol ya aplicado."""

    def __init__(self, session: Session, *, odontologo_id: uuid.UUID | None) -> None:
        self._session = session
        self._odontologo_id = odontologo_id

    @classmethod
    def scoped(cls, session: Session, ident: Identity) -> "DevolucionRepository":
        """Scope forzado por rol: odontólogo propio, recepcionista/admin global."""
        if ident.rol == "odontologo":
            return cls(session, odontologo_id=scoped_odontologo_id(ident))
        return cls(session, odontologo_id=None)

    def _base_query(self) -> Query[Devolucion]:
        consulta = (
            self._session.query(Devolucion)
            .join(Turno, Turno.id == Devolucion.turno_id)
            .filter(Devolucion.is_active.is_(True), Turno.is_active.is_(True))
        )
        if self._odontologo_id is not None:
            consulta = consulta.filter(Turno.odontologo_id == self._odontologo_id)
        return consulta

    def list(self, estado: str | None = None) -> list[Devolucion]:
        """Devoluciones visibles para el rol, opcionalmente filtradas por estado."""
        consulta = self._base_query()
        if estado is not None:
            consulta = consulta.filter(Devolucion.estado == estado)
        return list(consulta.order_by(Devolucion.created_at, Devolucion.id).all())

    def get(self, devolucion_id: object) -> Devolucion | None:
        """Detalle por id: inexistente → None; existe pero ajeno → 403.

        La consulta scopeada es la principal; el fallback global SOLO distingue
        404 (no existe) de 403 (existe fuera de alcance), sin devolver datos.
        """
        return self._resolver(devolucion_id)

    def get_for_update(self, devolucion_id: object) -> Devolucion | None:
        """Igual que `get` pero con `SELECT … FOR UPDATE` (design D4, P4).

        Serializa ejecuciones concurrentes de la misma devolución. En SQLite
        `with_for_update()` es no-op (los tests validan la invariante); en
        PostgreSQL bloquea la fila hasta el commit del ganador.
        """
        return self._resolver(devolucion_id, for_update=True)

    def _resolver(
        self, devolucion_id: object, *, for_update: bool = False,
    ) -> Devolucion | None:
        consulta = self._base_query().filter(Devolucion.id == devolucion_id)
        if for_update:
            consulta = consulta.with_for_update()
        visible = consulta.first()
        if visible is not None:
            return visible
        existe = (
            self._session.query(Devolucion)
            .filter(
                Devolucion.id == devolucion_id, Devolucion.is_active.is_(True)
            )
            .first()
        )
        if existe is not None and self._odontologo_id is not None:
            raise DevolucionFueraDeScope(
                "devolución de otro profesional"
            )
        return None
