"""Base declarativa SQLAlchemy 2.0 — sin tablas en C-01 (migracion 001 llega en C-02)."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base de la que heredaran todos los modelos de dominio (C-02+)."""
