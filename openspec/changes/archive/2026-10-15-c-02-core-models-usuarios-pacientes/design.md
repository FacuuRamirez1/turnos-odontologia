# Design — c-02-core-models-usuarios-pacientes

## Context

C-01 dejó `Base` vacía, `env.py` cableado a `DATABASE_URL` y `session.py` con sesión-por-request (ver `proposal.md — Why`). Este change añade la primera migración con datos. Constraints relevantes: P2 (`extra='forbid'`, aplica a futuros schemas; modelos SQLAlchemy usan tipos estrictos), P3 (solo Alembic), P5 (secretos solo env — el seed usa password hasheada de `JWT_SECRET`-independiente: hash fijo de demo, nunca plaintext), P6 (constraints también en Postgres), P8 (aislamiento en repositorio), P9 (append-only), P11 (DNI ficticios), P13 (v2 apagado). Ver requisitos en `specs/core-models-usuarios-pacientes/spec.md`.

## Goals / Non-Goals

**Goals:**

- Persistencia fundacional migrable y testeable que C-03 consume sin cambios (columnas `password_hash`, `rol`, `odontologo_id` listas para JWT/RBAC).
- Aislamiento `odontologo_id` imposible de omitir por accidente (forzado en `BaseRepository`, no convención).
- Auditoría día uno: soft-delete + rol DB sin UPDATE/DELETE en append-only.

**Non-Goals:**

- Tablas de `disponibilidad/bloqueo` (C-04), `turno/turno_historial` (C-05), `pago/evento_pago` (C-07), `recordatorio_mail` (C-09) — solo se deja el rol DB y el mecanismo, no las tablas.
- Endpoints, schemas Pydantic de API, hashing real de passwords (C-03), JWT (C-03).
- RLS por fila en esta migración (ver Decisiones): el aislamiento v1 es a nivel repositorio + rol least-privilege; RLS se evalúa en C-13 si el threat model lo exige.

## Decisions

- **UUID PK vía `pgcrypto` `gen_random_uuid()` + `timestamptz` + `NUMERIC(10,2)` para montos.** Tipos right-sized desde el día uno (supabase-postgres-best-practices / Schema). Alternativa (BIGINT autoincremental + FLOAT): descartada — expone conteos y pierde precisión monetaria. `init-pgcrypto.sql` de C-01 ya habilita la extensión.
- **CHECK constraints en DB para rol cerrado, hash mínimo, montos ≥ 0 y consentimiento bloqueante** (`CHECK (consentimiento_datos = false OR consentimiento_fecha IS NOT NULL)` + NOT NULL sobre el flag). Cumple P6/P11 sin depender de la app. Alternativa (solo validación Pydantic): descartada, viola P6.
- **`AuditMixin` con soft-delete + índice parcial `WHERE is_active`** en las tres entidades. Las lecturas estándar excluyen inactivos; el índice parcial mantiene las queries calientes pequeñas. Alternativa (borrado físico): descartada, rompe RN-AUDIT/RN-CONSENTIMIENTO (hay que conservar evidencia del consentimiento).
- **`BaseRepository[T]` genérico con `odontologo_id` obligatorio en el constructor para entidades scopeadas + `UnitOfWork` con context manager (commit/rollback).** El filtro se aplica en el método base de lectura, no en cada llamada (P8). `Paciente` (sin `odontologo_id`, single-sede D8) usa el repositorio sin filtro de profesional pero con el mismo UoW. Alternativa (filtros ad-hoc por query): descartada — un olvido filtra la agenda ajena (RN-AISLAMIENTO).
- **Aislamiento app-enforced (repositorio) como mecanismo primario, NO RLS en 001.** Fundamento: single-sede v1 con un solo rol de app + `require_role()` en C-03; RLS con `SET ROLE`/session-vars añade superficie operativa sin threat model que lo pida aún. Lo que sí se crea ahora: rol DB least-privilege + `REVOKE UPDATE, DELETE` preparado para `turno_historial`/`evento_pago` (GRANTs efectivos cuando C-05/C-07 creen las tablas; migración 001 deja el rol y revokes sobre esquema futuro documentados). C-13 re-evalúa RLS en hardening. Alternativa (RLS desde 001): descartada por costo/beneficio en v1 académico.
- **Previsión P6 documentada, no implementada:** UNIQUE `(odontologo_id, inicio)` + `EXCLUDE USING gist` anti-solape + `CHECK (inicio > now())` se definen en C-05 sobre `turno` (la tabla no existe aún); 001 no crea stubs de tablas ajenas. Evita migraciones fantasma y respeta atomicidad del change.
- **Tablas v2 (`lista_espera`, `notificacion_whatsapp`) creadas por 001 sin repositorio de escritura ni seed.** Solo DDL + test que afirma cero filas con flags off (P13). Alternativa (no crearlas): descartada — D4 exige diseño futuro visible y evita refactorizar el ERD en v2.
- **Seed idempotente por email/DNI natural-key (`INSERT … ON CONFLICT DO NOTHING`) con DNI ficticios patrón `99.999.9xx`** y password demo hasheada con bcrypt costo mínimo (solo dev). Montos distintos por odontólogo (ej. seña $65.000 vs $70.000 — valores de demo, el default comercial se cierra en C-07/Q1). Sin turnos/pagos (pertenecen a C-05/C-07/C-13). Alternativa (seed con Faker aleatorio): descartada — rompe idempotencia y dificulta tests.

## Risks / Trade-offs

- [Riesgo] `odontologo_id` nullable en `Usuario` permite staff sin perfil vinculado → Mitigación: CHECK (`rol = 'odontologo' ⇒ odontologo_id IS NOT NULL` diferido: se aplica como validación de seed/tests en C-02 y como FK-hard en C-03 cuando el flujo de alta exista; documentado en tasks).
- [Riesgo] Email case-sensitive duplica `Admin@x` vs `admin@x` → Mitigación: `UNIQUE` sobre `lower(email)` (índice funcional) + normalización en escritura.
- [Riesgo] Migración 001 gigante acoplada a v2-off → Mitigación: 001 en dos secciones comentadas (core / v2-off) para que el diff sea revisable por governance CRÍTICO.
- [Trade-off] Sin RLS en 001: aceptado, re-evaluación explícita en C-13 (threat model + test de visibilidad por rol).
- [Trade-off] Un solo spec para modelos+repo+seed: aceptado, capacidad cohesiva (persistencia fundacional), igual que C-01.

## Migration Plan

- Apply: `alembic upgrade head` (001) en dev → seed dev → `pytest` verde. Rollback: `alembic downgrade -1` (001 reversible, `down` dropea v2-off + core en orden inverso).
- Sin datos productivos (base vacía); sin downtime.
- Verificación post-apply: `alembic current` = 001; grep `create_all` = 0 hits; seed idempotente (2 corridas); tablas v2 vacías con flags off.

## Open Questions

- Ninguna bloquea el change. Las Alta de `10_preguntas_abiertas.md` (Q1 monto default seña, Q2 credenciales MP, Q7 defaults TTL/ventana) se consumen en C-04/C-05/C-07/C-09, no aquí; los valores usados en seed/design son demo y están marcados como tales.
