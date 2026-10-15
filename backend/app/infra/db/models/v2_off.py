"""Tablas **[v2] modeladas apagadas** C-02 (design D-v2-off, P13).

`lista_espera` y `notificacion_whatsapp` existen SOLO como DDL: no hay
repositorio de escritura ni seed que las toque en v1. Con
`WHATSAPP_ENABLED=false` la aplicación hace cero inserts en ambas
(verificado en `test_p3_v2off.py`). Se activan en v2.
"""

import uuid

from sqlalchemy import CheckConstraint, Index, String, Text, text
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base
from app.infra.db.mixins import AuditMixin


class ListaEspera(AuditMixin, Base):
    """[v2-off] Espera de turnos: DDL sin escrituras en v1."""

    __tablename__ = "lista_espera"

    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    contacto: Mapped[str] = mapped_column(String(255), nullable=False)
    odontologo_id: Mapped[uuid.UUID | None] = mapped_column(
        SAUuid, nullable=True, default=None
    )
    nota: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)


class NotificacionWhatsapp(AuditMixin, Base):
    """[v2-off] Cola WhatsApp: DDL sin escrituras con `WHATSAPP_ENABLED=false`."""

    __tablename__ = "notificacion_whatsapp"

    destino: Mapped[str] = mapped_column(String(50), nullable=False)
    mensaje: Mapped[str] = mapped_column(String(1000), nullable=False)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, default="pendiente")

    __table_args__ = (
        CheckConstraint(
            "estado IN ('pendiente', 'enviada', 'fallida')",
            name="ck_whatsapp_estado_cerrado",
        ),
    )


Index(
    "ix_lista_espera_activos",
    ListaEspera.created_at,
    postgresql_where=text("is_active"),
)
Index(
    "ix_whatsapp_activos",
    NotificacionWhatsapp.created_at,
    postgresql_where=text("is_active"),
)
