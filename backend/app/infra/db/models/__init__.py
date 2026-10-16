"""Modelos C-02 — persistencia fundacional (spec `core-models-usuarios-pacientes`).

Se amplía en 1.4 (`Odontologo`), 1.6 (`Paciente`) y 3.1 (tablas v2-off):
cada entidad vive en su módulo y se re-exporta aquí para Alembic/tests.
"""

from app.infra.db.base import Base
from app.infra.db.mixins import AuditMixin  # noqa: F401 (re-export para Alembic/tests)
from app.infra.db.models.bloqueo import Bloqueo  # noqa: F401
from app.infra.db.models.disponibilidad import Disponibilidad  # noqa: F401
from app.infra.db.models.odontologo import Odontologo  # noqa: F401
from app.infra.db.models.paciente import Paciente  # noqa: F401
from app.infra.db.models.usuario import Usuario  # noqa: F401
from app.infra.db.models.v2_off import (  # noqa: F401
    ListaEspera,
    NotificacionWhatsapp,
)

__all__ = [
    "AuditMixin",
    "Base",
    "Bloqueo",
    "Disponibilidad",
    "ListaEspera",
    "NotificacionWhatsapp",
    "Odontologo",
    "Paciente",
    "Usuario",
]
