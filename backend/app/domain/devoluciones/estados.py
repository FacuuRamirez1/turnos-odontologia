"""Ciclo cerrado de estados de la devolución C-08 (design D3, spec § cerrado).

La app replica la tabla que la DB garantiza con triggers (migración 006):
`pendiente→aprobada`, `pendiente→rechazada` y `aprobada→ejecutada`. Cualquier
otro movimiento (incluidos terminales y auto-transiciones) es un error de
dominio que el endpoint traduce a 409 `TRANSICION_DEVOLUCION_INVALIDA` antes
de tocar la base (P6/P9).
"""

TRANSICIONES_DEVOLUCION: dict[str, frozenset[str]] = {
    "pendiente": frozenset({"aprobada", "rechazada"}),
    "aprobada": frozenset({"ejecutada"}),
    "rechazada": frozenset(),
    "ejecutada": frozenset(),
}


class TransicionDevolucionInvalida(Exception):
    """Movimiento de estado fuera del ciclo cerrado → 409."""


def transicion_permitida(origen: str, destino: str) -> bool:
    """True solo si el par existe en la tabla cerrada."""
    return destino in TRANSICIONES_DEVOLUCION.get(origen, frozenset())


def validar_transicion(origen: str, destino: str) -> None:
    """Levanta `TransicionDevolucionInvalida` si el par no está permitido."""
    if not transicion_permitida(origen, destino):
        raise TransicionDevolucionInvalida(
            f"transición de devolución {origen}→{destino} no permitida"
        )
