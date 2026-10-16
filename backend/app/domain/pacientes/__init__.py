"""Ficha mínima de paciente C-06 — gate RN-CONSENTIMIENTO en servicio (design D1)."""

from app.domain.pacientes.service import (
    ConsentimientoRequerido,
    PacienteDuplicado,
    PacienteService,
    normalizar_dni,
)

__all__ = [
    "ConsentimientoRequerido",
    "PacienteDuplicado",
    "PacienteService",
    "normalizar_dni",
]
