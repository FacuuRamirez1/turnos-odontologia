# Tasks — c-04-disponibilidad-slots

> TDD (U2) en cada grupo: test en rojo → implementación → triangulación
> feliz / error de negocio / borde. P2 (`extra='forbid'`), P3 (migración
> versionada, cero `create_all`), P5 (env-only), P6 (constraints en DB),
> P8 (RBAC + scope), P12 (rate-limit pública). U1: no commitear sin pedido.

## 1. Modelos + migración 002 (base de todo)

- [ ] 1.1 Escribir tests RED de modelos/constraints (feliz: fila válida persiste; negocio: `hora_fin<=hora_inicio`/`duracion<=0`/`tope<=0`/`motivo` inválido/`dia_semana` fuera de 0..6 rechazados; borde: `vigente_desde>vigente_hasta` rechazado) y verificar que fallan sin tablas
- [ ] 1.2 Implementar modelos `Disponibilidad` y `Bloqueo` (`backend/app/infra/db/models/`) con `AuditMixin` + columna `odontologo_id` (scopeada P8) y verificar que los tests del 1.1 compilan contra ellos
- [ ] 1.3 Escribir migración `002_disponibilidad_bloqueo` (extensión `btree_gist`, función `minutos()`, tablas, `EXCLUDE` no-solape por (`odontologo_id`, `dia_semana`), `CHECK`s, índices `ix_disponibilidad_od_dia` / `ix_bloqueo_od_desde`, `downgrade` completo) y verificar `alembic upgrade head` + `alembic current` = `002` en DB vacía
- [ ] 1.4 Añadir tests de migración estilo `test_migration_001.py` (downgrade revierte tablas+función; `create_all` ausente en runtime; inserción directa solapada rechazada por DB — P6) y verificar `pytest backend/app/tests/test_migration_002.py` en verde

## 2. Motor puro de slots (sin I/O, seam de C-05)

- [ ] 2.1 Escribir tests RED del motor (feliz: grilla 09:00–10:00/30min → 2 slots; negocio: pausa mediodía y feriado día completo restan; borde: resto parcial 09:00–09:50/30min → solo 1 slot; solape parcial bloque-slot lo elimina; `tope_dia=2` corta en 2; anticipación 23h ausente / 24h exactas presente con `ahora` fijo) y verificar que fallan sin `motor.py`
- [ ] 2.2 Implementar `generar_slots()` en `backend/app/domain/disponibilidad/motor.py` (múltiplos exactos desde `hora_inicio`, tope, resta de bloqueos + `ocupados`, anticipación inclusiva, zona `TIMEZONE`) y verificar `pytest` del 2.1 en verde
- [ ] 2.3 Añadir tests de ocupados inyectados (feliz: slot ocupado ausente; borde: `tope` cuenta ocupados+libres; ocupados de otro profesional no restan) y verificar en verde — deja el seam documentado para C-05

## 3. CRUD staff disponibilidad/bloqueos con RBAC (P8)

- [ ] 3.1 Escribir tests RED de endpoints staff (feliz: odontólogo crea la propia 201 / recepcionista crea cualquiera; negocio: odontólogo sobre `odontologo_id` ajeno → 403 sin cambios, payload con campo extra → 422 P2; borde: recepcionista sin `odontologo_id` explícito → 422, nunca lectura global) y verificar que fallan sin router
- [ ] 3.2 Implementar schemas Pydantic (`extra='forbid'`) + router CRUD con `require_role("odontologo","recepcionista","admin")` y scope (`scoped_repository` para odontólogo; `odontologo_id` explícito validado para recepcionista/admin — D-SCOPE) y verificar tests del 3.1 en verde
- [ ] 3.3 Escribir tests RED de aislamiento en lectura (feliz: odontólogo lista solo lo propio con 2 profesionales seedados; negocio: `GET` por id ajeno → 404; borde: `BaseRepository(Disponibilidad)` sin scope levanta en vez de filtrar) y verificar en verde

## 4. Montos turno/seña por odontólogo (D1)

- [ ] 4.1 Escribir tests RED de `PATCH /api/odontologos/montos` (feliz: odontólogo actualiza los propios 200; negocio: recepcionista/admin → 403 sin cambios; borde: monto negativo → 422, `monto_senia > monto_turno` permitido — sin regla de proporción en v1) y verificar que fallan sin endpoint
- [ ] 4.2 Implementar el endpoint (claim `odontologo_id`, nunca body; `NUMERIC(10,2)` no negativos) y verificar tests del 4.1 en verde

## 5. Endpoint público `GET /disponibilidad` (P12, 03 §3.1)

- [ ] 5.1 Escribir tests RED del endpoint (feliz: día con 3 huecos → 200 con 3 pares `inicio/fin` y cero campos de paciente; negocio: `odontologo_id` desconocido → 404, `fecha` pasada/malformada o params ausentes → 422; borde: día totalmente bloqueado → 200 lista vacía; slot dentro de anticipación ausente) y verificar que fallan sin ruta
- [ ] 5.2 Implementar `GET /api/disponibilidad` (schemas `extra='forbid'`, filtra vigencia, resta bloqueos, aplica anticipación `ANTICIPACION_MIN_HS`, serializa ISO con offset; D-PUB: resolver checkpoint registro-vs-path junto al test `test_public_routes.py`) y verificar tests del 5.1 en verde
- [ ] 5.3 Generalizar el limitador (parámetros límite/ventana) + tests RED de rate-limit público (feliz: 30 req/min pasan; negocio: req 31 → 429; borde: IP distinta no afectada; caída de Redis → fallback memoria sin 500) y verificar en verde

## 6. Settings, seed y verificación integral

- [ ] 6.1 Añadir `ANTICIPACION_MIN_HS=24` y `TIMEZONE=America/Argentina_Cordoba` a `Settings` + `.env.example` con tests de contrato env (defaults presentes, override por env, P5 sin hardcode) y verificar `pytest test_env_contract.py` + nuevo test en verde
- [ ] 6.2 Extender `seed_dev.py` (disponibilidad L–V 9–17 por odontólogo, tope 14/día, montos distintos; 1 feriado = 2 filas + 1 bloqueo ejemplo; DNIs ficticios P11) con test de idempotencia y verificar doble corrida sin duplicados
- [ ] 6.3 Verificación integral: `pytest backend/` completo en verde, `mypy`/`ruff` limpios, `alembic upgrade/downgrade` cíclico OK, y `GET /api/disponibilidad` manual contra seed muestra huecos menos pausa/feriado

## Workflow follow-up

- Marcar C-04 `[x]` en CHANGES.md solo tras `/opsx:archive`.
- Avisar a C-05: consumir `generar_slots(..., ocupados=<slots de turno>)`; a C-06: migración 002 ocupa su número — coordinar si toca `Odontologo`.
