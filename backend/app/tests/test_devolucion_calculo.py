"""Tests C-08 task 2.1 — cálculo del monto de devolución (RED primero).

Escenarios (U2 feliz / negocio / borde):
- feliz: 100 % de 10000.00 = 10000.00 (RN-SENIA-100);
- negocio: porcentaje 0 o 50 → error de dominio (el 0 % se filtra ANTES:
  no se crea devolución con 0, así que nunca llega al cálculo);
- borde: 60 % de 3333.33 = 2000.00 con redondeo half-up (1999.998 → 2000.00).

Valores esperados desde la spec (`specs/devoluciones`, RN-SENIA-60), no
recomputados con la misma fórmula del código.
"""

from decimal import Decimal

import pytest

from app.domain.devoluciones.calculo import (
    PorcentajeDevolucionInvalido,
    calcular_monto_devolucion,
)


def test_100_por_ciento_devuelve_el_total_feliz() -> None:
    """Feliz: devolución total devuelve exactamente el monto del pago."""
    assert calcular_monto_devolucion(Decimal("10000.00"), 100) == Decimal("10000.00")


def test_60_por_ciento_redondea_half_up_a_centavos_borde() -> None:
    """Borde: 1999.998 se redondea half-up a 2000.00 (nunca float)."""
    monto = calcular_monto_devolucion(Decimal("3333.33"), 60)
    assert monto == Decimal("2000.00")
    assert isinstance(monto, Decimal)


@pytest.mark.parametrize("porcentaje", [0, 50])
def test_porcentaje_fuera_de_100_60_es_error_de_dominio_negocio(
    porcentaje: int,
) -> None:
    """Negocio: solo 100 y 60 son válidos; 0 % se filtra antes de calcular."""
    with pytest.raises(PorcentajeDevolucionInvalido):
        calcular_monto_devolucion(Decimal("10000.00"), porcentaje)
