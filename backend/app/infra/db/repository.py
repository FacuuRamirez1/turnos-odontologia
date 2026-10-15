"""`BaseRepository[T]` + `UnitOfWork` C-02 — aislamiento forzado (P8) y atomicidad.

Regla de scope (design D-aislamiento): toda entidad con columna `odontologo_id`
es scopeada — el filtro se aplica en el método base de lectura desde el
`odontologo_id` del constructor, imposible de omitir por accidente (fail-closed:
sin scope en el constructor → `ValueError`). Entidades sin esa columna
(`Paciente`, `Odontologo` en v1 single-sede D8) leen global.
Las lecturas estándar excluyen soft-deleted salvo `include_inactive=True`.
"""

from collections.abc import Callable
from types import TracebackType
from typing import Generic, TypeVar, cast
from uuid import UUID

from sqlalchemy.orm import Session

T = TypeVar("T")


def _es_scopeada(model: type[T]) -> bool:
    return hasattr(model, "odontologo_id")


class BaseRepository(Generic[T]):
    """Repositorio genérico con filtro `odontologo_id` forzado (RN-AISLAMIENTO)."""

    def __init__(
        self,
        session: Session,
        model: type[T],
        odontologo_id: UUID | None = None,
    ) -> None:
        if _es_scopeada(model) and odontologo_id is None:
            raise ValueError(
                f"{model.__name__} es scopeada por odontologo_id: "
                "el constructor exige odontologo_id (P8, fail-closed)."
            )
        self._session = session
        self._model = model
        self._odontologo_id = odontologo_id

    def _base_query(self, include_inactive: bool = False):  # type: ignore[no-untyped-def]
        query = self._session.query(self._model)
        if not include_inactive and hasattr(self._model, "is_active"):
            query = query.where(self._model.is_active.is_(True))  # type: ignore[attr-defined]
        if _es_scopeada(self._model):
            query = query.where(
                self._model.odontologo_id == self._odontologo_id  # type: ignore[attr-defined]
            )
        return query

    def list(self, include_inactive: bool = False) -> list[T]:
        """Lectura estándar: scopeada + solo activos salvo pedido explícito."""
        return list(self._base_query(include_inactive).all())

    def get(self, entity_id: object, include_inactive: bool = False) -> T | None:
        """Lectura por id, también bajo filtro de scope (P8)."""
        return cast(T | None, self._base_query(include_inactive).where(self._model.id == entity_id).first())  # type: ignore[attr-defined]

    def add(self, entity: T) -> T:
        """Agrega para commit del caller o del `UnitOfWork` (sin flush implícito)."""
        self._session.add(entity)
        return entity


class UnitOfWork:
    """Context manager atómico: commit al salir limpio, rollback ante cualquier fallo."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._factory = session_factory
        self._session: Session | None = None

    @property
    def session(self) -> Session:
        """Sesión activa; falla si se usa fuera del `with` (mypy-safe)."""
        assert self._session is not None, "UnitOfWork fuera de contexto"
        return self._session

    def __enter__(self) -> "UnitOfWork":
        self._session = self._factory()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        assert self._session is not None
        try:
            if exc_type is None:
                self._session.commit()
            else:
                self._session.rollback()
        finally:
            self._session.close()
            self._session = None
