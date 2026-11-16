# Evidencia MCP Context7 — apply de `C-08` (grupo 1: migración 006 + modelos)

- **Fecha**: 2026-11-16
- **MCP**: `context7` (herramientas `resolve-library-id` y `query-docs`), disponible y ejecutado realmente en esta sesión.
- **Versiones del proyecto** (`backend/requirements.txt`): SQLAlchemy 2.0.44, Alembic 1.17.1, FastAPI 0.119.0, Pydantic 2.12.4. Se consultaron los IDs versionados `/sqlalchemy/sqlalchemy/rel_2_0_44` y `/sqlalchemy/alembic/rel_1_17_2`.
- Las consultas posteriores (grupos 2-8: FastAPI/Pydantic) se agregarán en este archivo cuando se ejecuten.

## Consulta 1 — SQLAlchemy: CHECK nombrados e índices parciales

- **Herramientas**: `resolve-library-id(libraryName="SQLAlchemy", query="partial unique index postgresql_where sqlite_where and CheckConstraint in declarative __table_args__ (SQLAlchemy 2.0)")` → `/sqlalchemy/sqlalchemy` (versiones `rel_2_0_44`, `rel_2_1_6`, ...); luego `query-docs(libraryId="/sqlalchemy/sqlalchemy/rel_2_0_44", query="partial unique index with postgresql_where and sqlite_where in __table_args__; CheckConstraint with name")`.
- **Extracto**: firma `CheckConstraint(sqltext, name=None, deferrable=None, initially=None, ...)` y la documentación de `Constraint.ddl_if` / `Index.ddl_if` para emitir DDL solo en un dialecto (ej. `CheckConstraint("num > 5").ddl_if(dialect="postgresql")`); además la convención de nombres `ck_%(table_name)s_%(constraint_name)s`.
- **Decisión / cambio**: los CHECK de `Devolucion` y `Comprobante` se declaran con `name=` explícito (`ck_devolucion_porcentaje_cerrado`, `ck_comprobante_concepto_devolucion_id`, ...) para que modelo y migración 006 coincidan y se puedan reemplazar/descartar por nombre. Los índices únicos parciales de `Comprobante` se declaran con `postgresql_where` **y** `sqlite_where` (tests en SQLite). Archivos: `backend/app/infra/db/models/devolucion.py`, `comprobante.py` (tarea 1.4). La doc consultada no mostró el ejemplo literal de `sqlite_where`; el parámetro se verificó empíricamente (los tests `test_segundo_recibo_de_pago_rechazado_negocio` y `test_recibo_de_devolucion_coexiste_y_es_unico` fallan sin él).

## Consulta 2 — Alembic: reemplazar un CHECK y downgrade

- **Herramientas**: `resolve-library-id(libraryName="Alembic", query="drop and recreate check constraint, create_index partial postgresql_where, op.execute DDL in migration")` → `/sqlalchemy/alembic` (`rel_1_17_2`); luego `query-docs(libraryId="/sqlalchemy/alembic/rel_1_17_2", query="drop_constraint and create_check_constraint to replace a CHECK constraint; create_index with postgresql_where; downgrade")`.
- **Extracto**: `op.drop_constraint("ck1", type_="check")` para descartar un CHECK nombrado; `CreateCheckConstraintOp(constraint_name, table_name, condition)` (equivale a `op.create_check_constraint`); un CHECK nombrado se descarta explícitamente por nombre.
- **Decisión / cambio**: en `backend/alembic/versions/006_devolucion_comprobante.py` el CHECK `ck_evento_pago_tipo_cerrado` se reemplaza con `op.drop_constraint(..., type_="check")` + `op.create_check_constraint(...)` (agrega `devolucion_rechazada`), y el downgrade hace lo inverso con la lista original de C-07, tras abortar si hay eventos `devolucion_rechazada` (tarea 1.3). Cubierto por `test_migration_006.py`.
- **Sin extracto directo**: la consulta no devolvió un ejemplo de `create_index(..., postgresql_where=...)`; esa sintaxis ya está usada en la migración 005 del propio repo y se siguió ese patrón.
