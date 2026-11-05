"""Métricas de entrega C-09.

`contar_por_estado` devuelve conteos agrupados por estado para las 6 claves
cerradas, con ceros por defecto cuando no hay filas. Opcionalmente filtra por
período (`created_at` entre `desde` y `hasta`).
"""

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.infra.db.models import RecordatorioMail

ESTADOS = (
    "encolado",
    "enviado",
    "reintentando",
    "fallido",
    "confirmado_desde_mail",
    "cancelado_desde_mail",
)


def contar_por_estado(
    session: Session, desde: datetime | None = None, hasta: datetime | None = None,
) -> dict[str, int]:
    """Conteos por estado (las 6 claves, siempre presentes, 0 por defecto)."""
    resultado: dict[str, int] = {estado: 0 for estado in ESTADOS}
    agregado = (
        session.query(
            RecordatorioMail.estado, func.count(RecordatorioMail.id)
        )
        .filter(RecordatorioMail.is_active.is_(True))
    )
    if desde is not None:
        agregado = agregado.filter(RecordatorioMail.created_at >= desde)
    if hasta is not None:
        agregado = agregado.filter(RecordatorioMail.created_at <= hasta)
    for estado, cnt in agregado.group_by(RecordatorioMail.estado).all():
        resultado[str(estado)] = int(cnt)
    return resultado
