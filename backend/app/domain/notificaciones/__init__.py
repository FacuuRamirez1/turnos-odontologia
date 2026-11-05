"""Dominio de notificaciones C-09 — outbox de mails transaccional.

Exporta `RecordatorioMail` y los servicios `encolar_*`, `publicar_pendientes`,
`republicar_reintentando`, `encolar_recordatorios_ventana`, `contar_por_estado`,
emisión/consumo de tokens de acción, plantillas v1 y adaptador SMTP.
"""

from app.domain.notificaciones.metricas import contar_por_estado
from app.domain.notificaciones.outbox import (
    encolar_aviso_devolucion,
    encolar_confirmacion,
    encolar_recordatorio,
    encolar_recordatorios_ventana,
    publicar_pendientes,
    republicar_reintentando,
)
from app.domain.notificaciones.tokens import (
    consumir_token_db,
    emitir_token_para_recordatorio,
    token_hash_raw,
)

__all__ = [
    "contar_por_estado",
    "encolar_aviso_devolucion",
    "encolar_confirmacion",
    "encolar_recordatorio",
    "encolar_recordatorios_ventana",
    "publicar_pendientes",
    "republicar_reintentando",
    "consumir_token_db",
    "emitir_token_para_recordatorio",
    "token_hash_raw",
]
