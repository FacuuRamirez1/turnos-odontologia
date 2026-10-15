# Tasks — c-02-core-models-usuarios-pacientes

## 1. Modelos core + AuditMixin (TDD)

- [x] 1.1 Escribir tests rojos de `Usuario` con 3 escenarios (feliz: crea con email/rol válido; negocio: email duplicado case-insensitive rechazado; borde: `password_hash` < 60 chars rechazado) y verificar que fallan antes de implementar
- [x] 1.2 Implementar `AuditMixin` + `Usuario` (`email` UNIQUE sobre `lower(email)`, `password_hash`, `rol` CHECK cerrado, `odontologo_id` nullable, `activo`) con tipos `UUID`/`timestamptz` y verificar con `pytest backend/app/tests/test_usuarios.py` en verde
- [x] 1.3 Escribir tests rojos de `Odontologo` con 3 escenarios (feliz: crea con montos válidos; negocio: monto negativo rechazado; borde: segundo perfil con mismo `user_id` rechazado) y verificar que fallan antes de implementar
- [x] 1.4 Implementar `Odontologo` (`user_id` FK única → usuario, `monto_turno`/`monto_senia` `NUMERIC(10,2)` ≥ 0, `activo`) + FK con acción explícita `ON DELETE RESTRICT` y verificar con `pytest` en verde
- [x] 1.5 Escribir tests rojos de `Paciente` + consentimiento con 3 escenarios (feliz: crea con DNI + consentimiento + fecha; negocio: DNI duplicado rechazado; borde: consentimiento true sin fecha o flag false rechazado) y verificar que fallan antes de implementar
- [x] 1.6 Implementar `Paciente` (`dni` UNIQUE, `consentimiento_datos` NOT NULL + `consentimiento_fecha`, CHECK bloqueante) + soft-delete (`is_active` default true, `deleted_at`, índice parcial `WHERE is_active`) y verificar con `pytest` en verde incluyendo que el borrado no elimina la fila

## 2. BaseRepository con aislamiento forzado + UnitOfWork (TDD)

- [x] 2.1 Escribir tests rojos de aislamiento con 3 escenarios (feliz: query con `odontologo_id=A` devuelve solo filas de A; negocio: query sin filtro explícito del caller sigue filtrada; borde: `Paciente` sin scope profesional lista sin filtro de odontólogo) y verificar que fallan antes de implementar
- [x] 2.2 Implementar `BaseRepository[T]` genérico (`odontologo_id` obligatorio en constructor para entidades scopeadas, filtro aplicado en el método base de lectura) + `UnitOfWork` (context manager con commit/rollback atómico) y verificar con `pytest` en verde incluyendo rollback de escritura parcial

## 3. Migración 001 + rol DB + v2 apagadas

- [x] 3.1 Generar migración Alembic `001_core_v2off` (secciones comentadas core / v2-off: `lista_espera`, `notificacion_whatsapp` solo DDL sin repositorio de escritura) con `downgrade` reversible y verificar con `alembic upgrade head` + `alembic downgrade -1` + `upgrade` en base dev vacía sin errores
- [x] 3.2 Crear rol DB de aplicación least-privilege con `REVOKE UPDATE, DELETE` preparado para `turno_historial`/`evento_pago` (GRANTs efectivos al crearse en C-05/C-07) y verificar con intento de `UPDATE`/`DELETE` denegado sobre tabla append-only de prueba
- [x] 3.3 Escribir test de P3 (cero `create_all` en `backend/` fuera del propio test) + test de v2-off (cero filas en `lista_espera`/`notificacion_whatsapp` con `WHATSAPP_ENABLED=false`) y verificar con `pytest` en verde
- [x] 3.4 Documentar en design la previsión P6 de C-05 (`UNIQUE (odontologo_id, inicio)`, `EXCLUDE USING gist`, `CHECK (inicio > now())`) como pendientes explícitos y verificar que ningún stub de `turno/pago/mail` existe en 001 con `alembic history --verbose`

## 4. Seed dev + verificación de cierre

- [x] 4.1 Implementar seed dev idempotente (`ON CONFLICT DO NOTHING` por email/DNI: 2 odontólogos con montos distintos, 1 recepcionista + 1 admin con hash bcrypt demo, 5 pacientes DNI ficticios patrón `99.999.9xx`, 1 feriado + 1 bloqueo ejemplo; sin turnos/pagos) y verificar con doble corrida sin duplicados y `alembic current` en 001
- [x] 4.2 Correr `openspec validate --change "c-02-core-models-usuarios-pacientes"` y verificar que proposal + specs + design + tasks pasan sin errores, más checklist de reglas duras (P2 forbid, P3 cero create_all, P5 sin secretos, P6 constraints en DB, P8 aislamiento en repo, P9 append-only, P11 DNI ficticios, P13 v2 off) anotado para el reviewer CRÍTICO

## Workflow follow-up

- El implementador (apply) aplicará RED → GREEN → TRIANGULATE con 3 escenarios por test según U2; no escribir tests de implementación en esta fase.
- Tras implementar y revisar (governance CRÍTICO requiere aprobación humana antes de código), archivar con `/opsx:archive c-02-core-models-usuarios-pacientes` y marcar `[x]` C-02 en CHANGES.md.
