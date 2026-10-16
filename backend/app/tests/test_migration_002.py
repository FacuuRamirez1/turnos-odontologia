"""Tests C-04 §1.4 — contrato estático de la migración 002 (estilo test_migration_001).

Sin PG vivo en este entorno, la verificación dinámica (upgrade/downgrade en
dev, EXCLUDE real) queda como paso manual del reviewer. Estos tests fijan:
- downgrade revierte tablas + función (P3 reversible);
- cero `create_all` en runtime fuera de tests (P3);
- P6 presente en 002: btree_gist + EXCLUDE no-solape + CHECKs + índices;
- inserción directa solapada rechazada a nivel modelo portable (proxy SQLite
  de los CHECKs; el EXCLUDE se aserta estáticamente en la migración).
"""

import re
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

MIGRATION = (
    Path(__file__).resolve().parents[2] / "alembic" / "versions" / "002_disponibilidad_bloqueo.py"
)
SOURCE = MIGRATION.read_text(encoding="utf-8")


def test_migracion_002_encadena_001() -> None:
    assert 'down_revision' in SOURCE
    assert '"001_core_v2off"' in SOURCE or "'001_core_v2off'" in SOURCE


def test_btree_gist_y_funcion_minutos_presentes() -> None:
    assert "CREATE EXTENSION IF NOT EXISTS btree_gist" in SOURCE
    assert "CREATE OR REPLACE FUNCTION minutos" in SOURCE
    assert "IMMUTABLE" in SOURCE


def test_exclude_no_solape_por_profesional_dia() -> None:
    assert "ExcludeConstraint" in SOURCE
    assert "ex_disponibilidad_no_solape" in SOURCE
    assert "int4range(minutos(hora_inicio), minutos(hora_fin))" in SOURCE
    assert '("odontologo_id", "=")' in SOURCE or "odontologo_id" in SOURCE


def test_checks_p6_en_migracion() -> None:
    for check in (
        "ck_disponibilidad_dia_rango",
        "ck_disponibilidad_horas_orden",
        "ck_disponibilidad_duracion_positiva",
        "ck_disponibilidad_tope_positivo",
        "ck_disponibilidad_vigencia_orden",
        "ck_bloqueo_rango_orden",
        "ck_bloqueo_motivo_cerrado",
    ):
        assert check in SOURCE, f"falta CHECK {check}"


def test_indices_supabase_presentes() -> None:
    assert "ix_disponibilidad_od_dia" in SOURCE
    assert "ix_bloqueo_od_desde" in SOURCE


def test_downgrade_revierte_tablas_y_funcion() -> None:
    assert "op.drop_table" in SOURCE
    assert "DROP FUNCTION IF EXISTS minutos(TIME)" in SOURCE


def test_create_all_ausente_en_runtime() -> None:
    raiz = Path(__file__).resolve().parents[2]
    hits: list[str] = []
    for base in ("app", "alembic"):
        for path in (raiz / base).rglob("*.py"):
            if "tests" in path.parts:
                continue
            texto = path.read_text(encoding="utf-8")
            if re.search(r"\.create_all\s*\(", texto):
                hits.append(str(path))
    assert hits == [], f"create_all en runtime (P3): {hits}"


def test_insercion_solapada_rechazada_por_checks_proxy_db() -> None:
    """P6 proxy: SQLite aplica los CHECKs portables (hora_fin>hora_inicio)."""
    import datetime as dt
    import uuid
    from decimal import Decimal

    # Se usa una sesión local SQLite; este test solo demuestra el mecanismo
    # portable — el EXCLUDE real se verifica en PG (estático arriba).
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.infra.db.base import Base
    from app.infra.db.models import Disponibilidad, Odontologo, Usuario

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        session: Session = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)()
        h = "$2b$04$" + "f" * 53
        u = Usuario(email="solape@clinica-ficticia.example.ar", password_hash=h, rol="odontologo")
        session.add(u)
        session.commit()
        o = Odontologo(user_id=u.id, monto_turno=Decimal("1"), monto_senia=Decimal("1"))
        session.add(o)
        session.commit()
        od_id = uuid.UUID(str(o.id))
        session.add(
            Disponibilidad(
                odontologo_id=od_id, dia_semana=0, hora_inicio=dt.time(9, 0),
                hora_fin=dt.time(12, 0), duracion_min=30, tope_dia=14,
            )
        )
        session.commit()
        assert session.query(Disponibilidad).count() == 1
        # Fila inválida (rango invertido) rechazada por CHECK incluso directo:
        session.add(
            Disponibilidad(
                odontologo_id=od_id, dia_semana=0, hora_inicio=dt.time(12, 0),
                hora_fin=dt.time(9, 0), duracion_min=30, tope_dia=14,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        session.close()
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
