"""Repositorio de Comprobante C-08 (design D6/D8) - scope P8 forzado."""

import uuid

from sqlalchemy.orm import Query, Session

from app.core.security.dependencies import Identity, scoped_odontologo_id
from app.infra.db.models import Comprobante, Turno


class ComprobanteFueraDeScope(Exception):
    """Existe pero pertenece a otro profesional -> 403 (fail-closed, P8)."""


class ComprobanteRepository:
    """Lectura de comprobantes con el alcance del rol ya aplicado."""

    def __init__(self, session: Session, *, odontologo_id: uuid.UUID | None) -> None:
        self._session = session
        self._odontologo_id = odontologo_id

    @classmethod
    def scoped(cls, session: Session, ident: Identity) -> "ComprobanteRepository":
        """Scope forzado por rol: odontologo propio, recepcionista/admin global."""
        if ident.rol == "odontologo":
            return cls(session, odontologo_id=scoped_odontologo_id(ident))
        return cls(session, odontologo_id=None)

    def _base_query(self) -> Query[Comprobante]:
        consulta = (
            self._session.query(Comprobante)
            .join(Turno, Turno.id == Comprobante.turno_id)
            .filter(Turno.is_active.is_(True))
        )
        if self._odontologo_id is not None:
            consulta = consulta.filter(Turno.odontologo_id == self._odontologo_id)
        return consulta

    def get(self, comprobante_id: uuid.UUID) -> Comprobante | None:
        """Detalle por id: inexistente -> None; existe pero ajeno -> 403.

        La consulta scopeada es la principal; el fallback global SOLO distingue
        404 (no existe) de 403 (existe fuera de alcance), sin devolver datos.
        """
        visible = (
            self._base_query()
            .filter(Comprobante.id == comprobante_id)
            .first()
        )
        if visible is not None:
            return visible
        existe = (
            self._session.query(Comprobante)
            .filter(Comprobante.id == comprobante_id)
            .first()
        )
        if existe is not None and self._odontologo_id is not None:
            raise ComprobanteFueraDeScope("comprobante de otro profesional")
        return None
