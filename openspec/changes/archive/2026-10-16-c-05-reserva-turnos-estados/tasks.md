# Tasks — c-05-reserva-turnos-estados

> TDD (U2) en cada grupo: RED → GREEN → TRIANGULATE con 3 escenarios (feliz / error de negocio / borde). Tests conviven con su grupo, no al final. Assumptions de diseño abiertas (rate-limit 10/min/IP, job 60 s) solo-tuning: se implementan como env-tuneables.

## 1. Migración 003 + modelos Turno/TurnoHistorial

- [x] 1.1 Crear migración Alembic `003` (btree_gist, tablas turno/turno_historial, UNIQUE/EXCLUDE/CHECK, índices, REVOKE UPDATE/DELETE a app_role) y verificar en DB fresca que `alembic current` reporta head `003` y cero `create_all` en runtime
- [x] 1.2 Implementar modelos SQLAlchemy `Turno`/`TurnoHistorial` + repositorio scoped (`odontologo_id` forzado, falla cerrado sin scope) y verificar con tests adversos directos a DB: doble inserto rechazado, solape rechazado, `inicio<=now()` rechazado, UPDATE/DELETE historial denegado
- [x] 1.3 Añadir trigger/check que rechaza historial sin actor y verificar que un insert sin `actor_tipo/actor_id` falla en DB

## 2. Máquina de estados + historial (seam único `transition()`)

- [x] 2.1 Implementar tabla `TRANSICIONES` + `transition()` (validación par/actor/guardas, lock optimista por `version`, historial en mismo UnitOfWork, IntegrityError→409/422 del envelope) con tests: feliz (`confirmado→atendido` propio), error (`creado→atendido`→422, `no_show` pre-`fin`→422), borde (carrera mismo turno con `version` vieja→409)
- [x] 2.2 Implementar job de expiración TTL (`SELECT FOR UPDATE SKIP LOCKED`, `creado` expirado→`cancelado` sistema/`ttl_expirado` + historial, idempotente) con tests: feliz (expira), error-negocio (confirmado intacto), borde (creado expirado por cómputo ya libre aunque el job no haya corrido)

## 3. Reserva pública POST /reservas + pre-reserva TTL

- [x] 3.1 Implementar schemas Pydantic v2 (`extra='forbid'`) + `POST /reservas` (normalización DNI, seam C-06 reconocimiento/alta-implícita, validación slot vs motor+ocupados+anticipación, `Idempotency-Key`→replay devuelve original, rate-limit Redis `ratelimit:reservas:{ip}`) con tests: feliz (DNI reconocido→201 `creado`), error (`CONSENTIMIENTO_REQUERIDO`→422 sin filas, campo extra→422), borde (DNI `30.123.456` normaliza; replay misma key no duplica; carrera misma key-distinta→exactamente 1 turno + 409)
- [x] 3.2 Verificar ráfaga sobre `POST /reservas` responde 429 pasado el umbral y que la ruta sigue sin exigir JWT

## 4. Cancelación (cotizar→confirmar) + reprogramación atómica

- [x] 4.1 Implementar cotización previa (100/60/0 desde `ANTICIPACION_MIN_HS`) + `POST .../cancelar` (mismo commit cancela+libera, registro devolución `pendiente` con porcentaje para la bandeja C-08) con tests: feliz (en término→100 %), error (slot ya liberado no se retiene), borde (fuera de término→60 %; paciente con token ajeno→403)
- [x] 4.2 Implementar reprogramación atómica (origen→`reprogramado` + nuevo `confirmado` con `pago_id`/`reprogramado_de_id` heredados, validación nuevo slot, seña original ante diferencia) con tests: feliz (hereda pago), error (slot objetivo ocupado→rollback total, origen sigue `confirmado`), borde (nuevo slot en pasado→422 sin cambios)

## 5. Staff + self-service + cableado disponibilidad

- [x] 5.1 Implementar agenda del día staff (`GET /agenda?fecha&odontologo_id`, `confirmado→atendido/no_show` con `require_role()` + scoped, `POST /reservas/telefonica` solo recepcionista/admin `canal='recepcion'`) con tests: feliz (odontólogo ve los suyos), error (odontólogo ruta telefónica→403), borde (odontólogo no ve turnos ajenos aunque haya seed cruzado)
- [x] 5.2 Implementar `GET /mis-turnos?dni&token` (solo mail-action JWT propio, nunca DNI solo) con tests: feliz (token propio→solo sus turnos), error (DNI solo→401, token ajeno→403)
- [x] 5.3 Cablear ocupados al motor C-04 (`creado` no-expirado + `confirmado` restan; cancelado/reprogramado-origen/atendido/no_show/devuelto liberan) con tests: feliz (confirmado resta), error-negocio (doble-reserva vía API→409 `SLOT_OCUPADO`), borde (creado expirado cuenta libre por cómputo)

## 6. Integración y cierre del change

- [x] 6.1 Pasar suite completa (backend pytest + mypy + ruff, `alembic current`=003 en DB fresca, inserciones adversas rechazadas) y verificar `openspec validate --change c-05-reserva-turnos-estados` en verde
- [x] 6.2 Registrar renumeración de migraciones derivada del diseño (C-07→004, C-08→005, C-09→006) como nota en CHANGES.md al archivar y verificar que ningún spec archivado contradice el nuevo head

## Workflow follow-up

- Proponer/confirmar ajuste de CHANGES.md (migraciones C-07/C-08/C-09) antes o durante el apply — el apply no inventa alcance fuera de lo aprobado (P14).
- Archiviar el change tras revisión (`/opsx:archive c-05-reserva-turnos-estados`) y marcar `[x]` C-05 en CHANGES.md.
