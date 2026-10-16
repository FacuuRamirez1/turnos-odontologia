# Design — c-05-reserva-turnos-estados

## Context

Ver `proposal.md` (Why) y `specs/` (behavior contract). Estado actual verificado en repo: C-04 deja el seam explícito de "booked input vacío que C-05 cablea"; C-03 aporta `require_role()`, `scoped_repository()`, mail-action JWTs de 1 uso y rate-limit fixed-window en Redis; C-06 aporta el contrato `CONSENTIMIENTO_REQUERIDO` (falla total sin persistir); C-02 prepara el rol DB app sin UPDATE/DELETE sobre tablas append-only. La tabla `pago` aún NO existe (llega en C-07).

## Goals / Non-Goals

**Goals:**
- Reserva pública que nunca duplica ni solapa (árbitro final = DB, no la app).
- Máquina de estados imposible de violar: un solo camino de código + backstop en DB.
- Expiración TTL que libera aunque el job aún no haya corrido (expiración computada).
- Reprogramación atómica que no pierde la seña aunque `pago` llegue en C-07.

**Non-Goals:**
- Cobro/webhook MP (C-07 consume los seams `creado→confirmado` que aquí se dejan listos).
- Bandeja de devoluciones y `cancelado→devuelto` ejecutado (C-08; aquí solo el contrato + `devolucion pendiente` lógica si se confirma cancelación — ver Decisión 7).
- Mails y tokens de acción nuevos (se reutilizan los JWT C-03; las rutas `/mail/*` llegan en C-09).
- Frontend (C-10/C-11).

## Decisions

### 1. Modelo `Turno`: timestamptz + EXCLUDE anti-solape + lock optimista

- `inicio/fin timestamptz NOT NULL`; `estado TEXT CHECK (estado IN (...7 estados...))`; `canal TEXT CHECK (canal IN ('web','recepcion','mail'))`; `idempotency_key TEXT UNIQUE NOT NULL`; `version INTEGER NOT NULL DEFAULT 1`; `reprogramado_de_id UUID NULLABLE → turno.id` (trazabilidad F3); `pago_id UUID NULLABLE **sin FK**` (seam C-07, ver Decisión 7).
- `UNIQUE (odontologo_id, inicio)` (RN-DOBLE) + `EXCLUDE USING gist (odontologo_id WITH =, tstzrange(inicio, fin) WITH &&)` (RN-SOLAPE) + `CHECK (fin > inicio)` + `CHECK (inicio > now())` (RN-PASADO).
- Índices: `CREATE INDEX ON turno (odontologo_id, inicio)` (agenda del día + resta de ocupados; postgres-skill: indexar WHERE/JOIN/ORDER BY) y `CREATE INDEX ON turno (estado, created_at)` (job de expiración).
- Alternativa descartada: validar solape solo en servicio → pierde bajo carrera; la DB es el árbitro (P6). `EXCLUDE` exige extensión `btree_gist`: la migración `003` hace `CREATE EXTENSION IF NOT EXISTS btree_gist` (igual que Compose ya trae `pgcrypto` en C-01).
- `TurnoHistorial`: `id, turno_id FK, estado_anterior/nuevo, actor_tipo CHECK IN ('paciente','odontologo','recepcionista','admin','sistema'), actor_id, fecha timestamptz DEFAULT now(), motivo TEXT`; índice `(turno_id, fecha)`; `REVOKE UPDATE, DELETE ON turno_historial FROM app_role` en la misma migración (P9).

### 2. Máquina de estados: tabla de transiciones + función única + backstop DB

- Tabla en código `TRANSICIONES: dict[(origen, destino)] → (actores_permitidos, guarda_temporal)`; **única** función de dominio `transition(turno, destino, actor, motivo)` que: valida par permitido (422 `TRANSICION_INVALIDA`), valida actor/ownership, chequea guarda (`no_show` exige `fin <= now()`), hace `UPDATE turno SET estado, version=version+1 WHERE id AND version` (lock optimista → 409 en carrera staff), inserta historial **en el mismo `UnitOfWork`** (C-02).
- Backstop DB: trigger `BEFORE INSERT ON turno_historial` que rechaza `actor_tipo IS NULL OR actor_id IS NULL` (RN-ESTADOS) → aunque un futuro código olvide el actor, la DB lo frena.
- Alternativa descartada: máquina en múltiples endpoints ad-hoc → deriva y transiciones fantasma; un solo seam testeable (tdd-skill: behavior por interfaz pública).

### 3. Concurrencia: la DB decide, la app traduce

- `POST /reservas`: transacción corta (postgres-skill: transacciones cortas) → valida slot libre contra motor C-04 + ocupados → `INSERT`; ante `IntegrityError` (UNIQUE/EXCLUDE) responde **409 `SLOT_OCUPADO`**, nunca 500. Replay con misma `Idempotency-Key` → 200/201 con el turno original (P4).
- Mutaciones staff concurrentes (`atendido`, reprogramar): `version` optimista → mismatch = 409 con reintento del cliente.
- Job expiración: batch con `SELECT ... FOR UPDATE SKIP LOCKED LIMIT N` (postgres-skill: patrón de colas) para no pisarse entre workers.

### 4. TTL con expiración computada (no solo job)

- `expira_en = created_at + RESERVA_TTL_MIN` (default 15, env existente C-01). El motor de slots y `GET /disponibilidad` tratan `creado` expirado como **libre por cómputo**, aunque el job aún no lo haya formalizado a `cancelado` → A5 se cumple incluso con el worker caído.
- Job intervalar (60 s, en el `worker` de Compose C-01): formaliza `creado` expirado → `cancelado` (`sistema`/`ttl_expirado`) + historial. Idempotente por guarda de estado.

### 5. Cancelación en dos pasos: cotizar → confirmar

- `GET /reservas/.../cotizar-cancelacion` (puro, sin escritura): calcula regla desde `ANTICIPACION_MIN_HS` (se **reutiliza** el setting C-04, default 24 h; sin setting nuevo): dentro de término → 100 %, fuera → 60 % (RN-SENIA-100/60). La UI **debe** mostrarla antes del POST (B2).
- `POST .../cancelar`: `confirmado→cancelado` + liberación en el **mismo commit** (RN-LIBERACION) + creación del registro de devolución `pendiente` con porcentaje (entidad lógica que C-08 materializa en tabla; aquí viaja en la respuesta + evento para la bandeja).
- Alternativa descartada: setting separado `ANTICIPACION_CANCEL_HS` → dos relojes que divergen; un solo valor documentado (responde Q3.7 de `10 §3.7` para cancelación).

### 6. Reprogramación atómica sin tabla `pago` (seam C-07)

- `turno.pago_id UUID NULLABLE` **sin constraint FK** en migración `003`; C-07 añade la FK + backfill en su migración. La reprogramación copia `pago_id` (y `reprogramado_de_id = origen.id`) al nuevo turno `confirmado` en el mismo `UnitOfWork`: origen → `reprogramado`, nuevo → `confirmado`. Diferencia de monto → se mantiene seña original (default que cierra Q3 de `10 §1.3` salvo decisión posterior).
- Nuevo slot validado contra RN-PASADO/DOBLE/SOLAPE/ANTICIPACION **antes** del commit; si la carrera lo ocupa, rollback total (origen sigue `confirmado`).

### 7. Cableado del seam C-04 (resta de ocupados)

- El motor puro C-04 recibe `ocupados: list[(inicio, fin)]`; repositorio de turnos provee ocupados = turnos del profesional/día en estado `creado` no-expirado (computado) + `confirmado`. `GET /disponibilidad` compone ambos. Sin cambios a los requirements C-04 salvo el delta declarado (ADDED).

### 8. AuthN/AuthZ y rate-limit (reutilización, P8/P12)

- Público sin JWT: solo `POST /reservas` y `GET /mis-turnos?dni&token` (rutas 03 §3.2/§3.5 ya en `PUBLIC_ROUTES`); rate-limit fixed-window Redis `ratelimit:reservas:{ip}` (mismo patrón C-04; default propuesto 10/min/IP, tunable por env) — claves minúsculas con `:` (redis-skill).
- Paciente opera lo propio solo con mail-action JWT C-03 (tipos de token no intercambiables) + check `token.paciente_id == turno.paciente_id`.
- Staff: `require_role()` + `scoped_repository(odontologo_id)` + `POST /reservas/telefonica` solo `recepcionista|admin` (`canal='recepcion'`, datos mínimos DNI+mail+consentimiento).
- Schemas Pydantic v2 `extra='forbid'` en todo endpoint (P2); envelope de error consistente (fastapi-skill); JWT/MP/SMTP solo env (P5).

## Risks / Trade-offs

- [Risk] Reloj DB vs app en `CHECK (inicio > now())` / expiración → Mitigación: `now()` transaccional de Postgres como referencia; tests congelan tiempo (freezegun) en el borde TTL.
- [Risk] `EXCLUDE USING gist` sin `btree_gist` en un entorno nuevo → Mitigación: `CREATE EXTENSION` en la migración + assert en CI sobre DB fresca.
- [Risk] Numeración de migraciones: CHANGES.md asigna `003` a C-07 (pago+evento_pago), pero C-05 necesita `003` (turno+historial) por orden de dependencias → Mitigación: C-05 toma `003`; C-07 pasa a `004`, C-08 a `005`, C-09 a `006` (renumeración a confirmar en archive/apply; CHANGES.md se actualiza en consecuencia).
- [Risk] `pago_id` sin FK temporalmente huérfano → Mitigación: columna documentada como seam, tipos UUID estrictos, C-07 la constriñe; ningún flujo v1 la escribe salvo reprogramación (copia del valor que C-07 haya puesto).
- [Risk] Doble-clic / doble-submit en reserva → Mitigación: `Idempotency-Key` obligatoria en cliente público (generada por frontend C-10) + 409 con cuerpo reintentable.
- Trade-off: expiración computada vs solo-job → lecturas con una condición más, a cambio de A5 robusto ante caída del worker.

## Migration Plan

1. Migración `003`: extensión `btree_gist` → `CREATE TABLE turno, turno_historial` → constraints/índices → `REVOKE UPDATE,DELETE` a `app_role` → sin datos iniciales (seeds de turnos mínimos solo dev/test).
2. Deploy: migration-first (Alembic upgrade head) y luego API+worker; rollback = `downgrade -1` (tablas nuevas, sin pérdida si C-07 aún no corrió).
3. Verificación: `alembic current` = `003`; inserciones adversas (doble/solape/pasado/sin-actor) rechazadas en DB fresca; suite TDD en verde.

## Open Questions

- Umbral exacto de rate-limit en `POST /reservas` (propuesto: 10/min/IP; solo tuning, no cambia specs/tasks).
- Intervalo del job de expiración (propuesto 60 s; solo tuning).
- Q3 (`10 §1.3`) cerrada por default (mantener seña original); si el negocio exige cobrar diferencias, será change posterior (C-07/C-08), no este.
