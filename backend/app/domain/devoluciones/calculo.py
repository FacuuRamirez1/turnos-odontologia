"""Cálculo del monto de devolución C-08 (design D2).

- `calcular_monto_devolucion(monto_pago, porcentaje)` es pura: `Decimal` y
  `ROUND_HALF_UP` a centavos, nunca `float` (evita 1999.9999… en el 60 %).
- Solo acepta 100 o 60 (RN-SENIA-100/60). La cotización 0 % (RN-SENIA-0) no
  llega acá: `registrar_por_cancelacion` la filtra antes de persistir, porque
  el CHECK de la DB es `porcentaje IN (100, 60)`.
"""

from decimal import ROUND_HALF_UP, Decimal

CENTAVOS = Decimal("0.01")
PORCENTAJES_VALIDOS = (100, 60)


class PorcentajeDevolucionInvalido(ValueError):
    """Porcentaje fuera de la política 100/60 → error de dominio."""


def calcular_monto_devolucion(monto_pago: Decimal, porcentaje: int) -> Decimal:
    """Monto de la devolución redondeado half-up a centavos (D2)."""
    if porcentaje not in PORCENTAJES_VALIDOS:
        raise PorcentajeDevolucionInvalido(
            f"porcentaje {porcentaje} inválido: solo 100 o 60 (RN-SENIA-100/60)"
        )
    monto = Decimal(monto_pago) * Decimal(porcentaje) / Decimal(100)
    return monto.quantize(CENTAVOS, rounding=ROUND_HALF_UP)
