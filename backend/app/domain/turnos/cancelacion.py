"""Cotización de cancelación C-05 (design D5, spec § cotización).

Regla única desde `ANTICIPACION_MIN_HS` (setting C-04, default 24 h):
- dentro de término (`inicio - ahora >= anticipación`) → 100 (RN-SENIA-100);
- fuera de término pero futuro → 60 (RN-SENIA-60);
- inicio ya pasado → 0 (RN-SENIA-0; p. ej. `no_show` post-`fin`).
Pura y testeable sin I/O (la UI la muestra ANTES del POST, B2).
"""

from datetime import UTC, datetime, timedelta


def cotizar_devolucion(
    inicio: datetime,
    anticipacion_hs: int | float,
    ahora: datetime | None = None,
) -> int:
    """Porcentaje de seña a devolver (100 | 60 | 0)."""
    referencia = ahora if ahora is not None else datetime.now(UTC)
    ini = inicio if inicio.tzinfo is not None else inicio.replace(tzinfo=UTC)
    ref = referencia if referencia.tzinfo is not None else referencia.replace(tzinfo=UTC)
    if ini <= ref:
        return 0
    if ini - ref >= timedelta(hours=float(anticipacion_hs)):
        return 100
    return 60
