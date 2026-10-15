# Proposal — c-02-core-models-usuarios-pacientes

## Why

Sin modelos persistidos no hay auth (C-03) ni dominio (C-04 → C-13): C-01 dejó Alembic inicializado sin tablas y `Base` vacía. Este change crea la capa de persistencia fundacional — Usuario/Odontologo/Paciente + infraestructura de repositorio — con constraints de dominio en Postgres desde el día uno (P6) y tablas v2 modeladas pero apagadas (D4/D7/D9).

## What Changes

- Modelos SQLAlchemy 2.0: `Usuario` (`email` único, `password_hash`, `rol` cerrado odontologo|recepcionista|admin, `odontologo_id` nullable, `activo`), `Odontologo` (`user_id` FK única, `monto_turno`, `monto_senia` NUMERIC, `activo`), `Paciente` (`dni` UNIQUE, `consentimiento_datos` bool + `consentimiento_fecha` nullable).
- `AuditMixin` (`is_active`, `created_at`, `updated_at`, `deleted_at` para soft-delete) aplicado a las tres entidades core.
- `BaseRepository[T]` genérico con filtro forzado `odontologo_id` (aislamiento RN-AISLAMIENTO, P8) + `UnitOfWork` para transacciones atómicas.
- Rol DB de aplicación sin `UPDATE`/`DELETE` sobre tablas append-only futuras (`turno_historial`, `evento_pago` llegan en C-05/C-07; el rol y el mecanismo se crean aquí, se aplican allá) — prepara RN-AUDIT.
- Tablas **[v2] modeladas apagadas**: `lista_espera`, `notificacion_whatsapp` (creadas por migración, sin escrituras en v1 salvo flag off; guardadas por `WHATSAPP_ENABLED=false`, P13).
- Migración Alembic versionada `001` (core + v2 apagadas, `pgcrypto` para UUIDs); cero `create_all` en runtime (P3).
- Seed dev según `04 §5` (solo DNI ficticios, P11): 2 odontólogos (L–V 9–17, 30 min, tope 14/día, montos distintos), 1 recepcionista + 1 admin, 5 pacientes ficticios, 1 feriado + 1 bloqueo ejemplo. Sin turnos/pagos históricos (llegan en C-05/C-07/C-13).
- Previsión de constraints P6 para changes futuros documentada en design (UNIQUE/exclusion/check) sin crear tablas ajenas a este scope.

## Capabilities

### New Capabilities

- `core-models-usuarios-pacientes`: persistencia fundacional — entidades Usuario/Odontologo/Paciente con unicidades y consentimiento, AuditMixin, BaseRepository con aislamiento forzado + UnitOfWork, rol DB append-only, tablas v2 apagadas, migración 001 y seed dev mínimo.

### Modified Capabilities

- Ninguna (no se cambian requisitos de `foundation-setup`; se construye sobre ella).

## Impact

- Afecta: `backend/app/infra/db/` (modelos, base repository, UoW), `backend/alembic/versions/001_*`, seed dev, `backend/app/tests/` (nuevos tests de modelos). Nada del frontend.
- Dependencias desbloqueadas: C-03 (auth consume `Usuario.password_hash` + `rol` + `odontologo_id`); C-04/C-05 (FKs hacia `odontologo`/`paciente`); C-06 (ficha + consentimiento).
- Breaking: ninguno (base vacía, primera migración con datos).
- Riesgo de alcance: modelar tablas de turnos/pagos/mails aquí — se mitiga con Non-Goals explícitos en design (solo Usuario/Odontologo/Paciente + v2 apagadas).
