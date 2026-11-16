"""Tests C-08 task 3.1 — tabla de transiciones de la devolución (RED primero).

Escenarios (U2 feliz / negocio / borde):
- feliz: `pendiente→aprobada`, `pendiente→rechazada`, `aprobada→ejecutada`;
- negocio: ejecutar sin aprobar (`pendiente→ejecutada`) es inválido;
- borde: estados terminales (`rechazada`, `ejecutada`) y auto-transición no
  admiten movimientos.

La DB replica el ciclo con triggers (migración 006); esta tabla es la barrera
de app que responde 409 `TRANSICION_DEVOLUCION_INVALIDA` antes de tocarla.
"""

import pytest

from app.domain.devoluciones.estados import (
    TransicionDevolucionInvalida,
    validar_transicion,
)


@pytest.mark.parametrize(
    ("origen", "destino"),
    [("pendiente", "aprobada"), ("pendiente", "rechazada"), ("aprobada", "ejecutada")],
)
def test_transiciones_permitidas_feliz(origen: str, destino: str) -> None:
    """Feliz: el ciclo cerrado admite exactamente estos tres movimientos."""
    validar_transicion(origen, destino)


def test_ejecutar_sin_aprobar_invalido_negocio() -> None:
    """Negocio: `pendiente→ejecutada` no existe en la máquina."""
    with pytest.raises(TransicionDevolucionInvalida):
        validar_transicion("pendiente", "ejecutada")


@pytest.mark.parametrize(
    ("origen", "destino"),
    [
        ("rechazada", "aprobada"),
        ("rechazada", "pendiente"),
        ("ejecutada", "pendiente"),
        ("aprobada", "rechazada"),
        ("pendiente", "pendiente"),
    ],
)
def test_estados_terminales_y_auto_transicion_invalidos_borde(
    origen: str, destino: str
) -> None:
    """Borde: terminales y auto-transiciones rechazadas con error de dominio."""
    with pytest.raises(TransicionDevolucionInvalida):
        validar_transicion(origen, destino)
