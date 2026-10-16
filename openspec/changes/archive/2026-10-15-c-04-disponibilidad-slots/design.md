# Design — c-04-disponibilidad-slots

## Context

See proposal.md (Why) and `specs/disponibilidad-slots/spec.md` (behavior contract).
Estado actual verificado en código: `BaseRepository` falla cerrado sin `odontologo_id`
para entidades con esa columna (`repository.py:33-47`); `require_role()` +
`scoped_repository()` son los seams a reutilizar (`dependencies.py:98-129`);
`PUBLIC_ROUTES` ya reserva `GET /disponibilidad` como ruta 03 §3.1
(`api/__init__.py`); rate-limit fixed-window 5/60s con fallback memoria existe
para login (`rate_limit.py`); `Odontologo` tiene `monto_turno/monto_senia`
`NUMERIC(10,2)` no negativos (`odontologo.py:28-35`); settings solo por env
(`settings.py`); no existe tabla `turno` (llega en C-05), por lo que el motor
recibe `ocupados` como parámetro (vacío en v1 de este change).

## Goals / Non-Goals

**Goals:** motor de slots puro y testeable; CRUD staff con RBAC backend;
constraints de dominio también en Postgres (P6); endpoint público con
rate-limit sin fuga de datos; montos por odontólogo (D1); migración 002
reversible; decisiones no-obvias explicitadas (governance MEDIO).

**Non-Goals:** reserva/pre-reserva/TTL y máquina de estados (C-05); pagos MP
(C-07); mails/workers (C-09); frontend (C-10/C-11); multi-sede, sobre-turnos,
lista de espera con escrituras (P13); timezone por sede.

## Decisions

- **D-SLOT — motor puro sin I/O.** `generar_slots(disponibilidad, bloqueos,
  ocupados, fecha, ahora, anticipacion_hs) -> list[Slot(inicio, fin)]` en
  `backend/app/domain/disponibilidad/motor.py`: función pura (sin DB/clock
  inyectado por parámetros), testeable sin fixtures. `ocupados: list[interval]`
  vacío en C-04; C-05 lo conectará a `turno` sin cambiar la firma.
  Alternativa (query directa a turnos) rechazada: no existe la tabla y acoplaría
  el motor a infraestructura.
- **D-BLOQ — `bloqueo.odontologo_id` NOT NULL; feriados = N filas.**
  Un feriado nacional se carga una fila por profesional. Alternativa (fila
  global con NULL) rechazada: rompería el fail-closed de `BaseRepository`
  (entidad con columna `odontologo_id` exige scope) y abriría fugas de agenda
  (P8). Costo aceptado: seed/carga crean 2 filas en vez de 1.
- **D-OVERLAP — exclusión solo (profesional, día, rango horario).**
  `EXCLUDE USING gist (odontologo_id =, dia_semana =, rango-minutos &&)` donde
  el rango es `int4range()` sobre una función SQL IMMUTABLE
  `minutos(TIME)->INT`. Requiere `CREATE EXTENSION IF NOT EXISTS btree_gist`
  en la migración 002 (misma imagen PG que ya provee `pgcrypto`).
  `vigente_desde/hasta` solo filtran qué fila aplica, no participan en la
  exclusión: dos filas del mismo día con horarios solapados se rechazan aunque
  sus vigencias no se crucen (simplificación v1 documentada; el caso
  invierno/verano se modela editando la fila, no duplicándola).
- **D-RATE — generalizar el limitador existente.**
  Parametrizar `LoginRateLimiter` (límite/ventana por constructor) en vez de
  duplicarlo: login usa (5, 60s), `GET /disponibilidad` usa (30, 60s) por IP
  (`disponibilidad_key(ip)` con el mismo patrón `auth:ratelimit:`-like bajo
  prefijo `disponibilidad:ratelimit:`). 30/min porque el flujo de reserva
  re-consulta al cambiar de fecha. Misma caída a memoria si Redis cae.
- **D-MONTOS — `PATCH /api/odontologos/montos`, solo rol odontologo.**
  Lee el `odontologo_id` del claim (nunca del body) y actualiza solo su fila;
  recepcionista/admin → 403 (matriz 03 §2 fila montos). Sin endpoint por-id
  para no abrir IDOR por diseño.
- **D-ANT — `ANTICIPACION_MIN_HS=24` en `.env.example` + `Settings`.**
  Env-overridable, leída por el endpoint y pasada al motor como parámetro
  (no leída por el motor directamente → testeabilidad). Comparación
  `slot.inicio - ahora >= anticipacion`, borde inclusivo.
- **D-TZ — día en `America/Argentina_Cordoba`, instantes en UTC.**
  Nuevo setting `TIMEZONE` (default `America/Argentina_Cordoba`, stdlib
  `zoneinfo`, sin dependencia nueva). `fecha` YYYY-MM-DD = día en esa zona;
  `ahora` UTC convertido a local para comparar; respuesta ISO con offset.
  Alternativa (todo UTC) rechazada: desplaza el día 3h y ofrece slots del día
  equivocado en horario nocturno.
- **D-PUB — path canónico `/api/disponibilidad`.**
  Montado como los routers existentes (`/api` + router); la entrada lógica
  `GET /disponibilidad` de `PUBLIC_ROUTES` no se renombra en este change
  (el test `test_public_routes.py:16` aserta el tuple exacto). **Checkpoint
  para apply:** si el guard de rutas compara path literal con `/api/...`,
  actualizar registro + test juntos en el mismo commit; nunca solo uno.
- **D-SCOPE — recepcionista pasa `odontologo_id` explícito.**
  `scoped_repository()` con identidad odontologo deriva el scope del claim;
  con recepcionista/admin la entidad es scopeada pero el claim no trae
  `odontologo_id` → el endpoint construye `BaseRepository(session, Model,
  odontologo_id=<del query/body validado>)`. Falla 422 si falta, nunca
  lectura global (P8). Requiere test que lo demuestre (aislamiento invertido:
  recepcionista sin filtro explícito no existe como camino).
- **D-ERR — 422 validación, 403 scope, 404 odontólogo inexistente.**
  `GET /disponibilidad` con `odontologo_id` desconocido o inactivo → 404
  (no 200 vacío: distingue "sin huecos" de "profesional inválido" para el
  frontend). Fecha pasada o malformada → 422.

## Risks / Trade-offs

- [Risk] `btree_gist` no disponible en un PG gestionado sin permiso de
  extensiones → Mitigación: migración con `IF NOT EXISTS` + mensaje explícito;
  fallback documentado (trigger `BEFORE INSERT/UPDATE` con la misma
  condición); dev/CI usan la imagen stock con contrib.
- [Risk] Exclusión sin vigencia impide horarios estacionales superpuestos →
  Mitigación: simplificación v1 aceptada y documentada (D-OVERLAP); C-05+ no
  la necesita; revisitar solo si producto pide multi-vigencia.
- [Risk] Tope/día sin tabla `turno` no descuenta reservas reales en C-04 →
  Mitigación: el endpoint resta `ocupados=[]` y el contrato queda probado con
  ocupados inyectados; C-05 conecta la query real (dependencia declarada en
  CHANGES).
- [Risk] Rate-limit en memoria por instancia si Redis cae (ventana por réplica)
  → Mitigación: mismo comportamiento ya aceptado en login (C-03); documentado,
  no nuevo.
- [Risk] Colisión con C-06 (propuesta concurrente): solo comparten la tabla
  `odontologo` (C-04: montos; C-06: nada previsto sobre ella) → Mitigación:
  nota en proposal; en apply, rebase sobre `main` y si C-06 tocó `Odontologo`,
  coordinar migración (números 002 vs suyo) antes de mergear.

## Migration Plan

1. `alembic revision --autogenerate` NO — migración 002 escrita a mano
   (`backend/alembic/versions/002_disponibilidad_bloqueo.py`): extensión,
   función `minutos()`, tablas + constraints + índices
   (`ix_disponibilidad_od_dia`, `ix_bloqueo_od_desde`).
2. `upgrade` en dev → `alembic current` = `002`; `downgrade` revierte
   (DROP TABLE + FUNCTION), probado en CI como en `test_migration_001.py`.
3. Datos: seed dev extendido (disponibilidad L–V 9–17 por odontólogo + 1
   feriado (2 filas) + 1 bloqueo ejemplo) — seed, no schema (P3 intacto).
4. Rollback de deploy: `alembic downgrade -1`; el código nuevo nunca se
   despliega sin la migración (mismo release, orden migración-primero).
5. Sin backfill: tablas nuevas, cero filas existentes.

## Open Questions

- Ninguna que cambie specs, enfoque o tasks. Defaults ya cerrados por KB:
  anticipación 24h (10 §3.7 propuesta), tope 14/día solo como seed dev
  (04 §5), TTL pre-reserva 15min (ya en env, lo consume C-05).
