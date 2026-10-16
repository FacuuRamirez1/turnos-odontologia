# reserva-turnos-estados

## Purpose

Convierte los slots ofrecibles de disponibilidad en turnos con identidad propia: reserva pública con pre-reserva TTL, máquina de estados cerrada con historial auditable por actor, y constraints anti-choque enforced en Postgres además de la app.

## Requirements

### Requirement: Turno persiste con constraints anti-choque en DB

The system SHALL persist each `Turno` with `paciente_id, odontologo_id, inicio/fin (timestamptz), estado, canal (web|recepcion|mail), idempotency_key` unique and `version` for optimistic locking, enforced in Postgres by `UNIQUE (odontologo_id, inicio)`, `EXCLUDE USING gist` anti-overlap per professional, and `CHECK (fin > inicio)` plus `CHECK (inicio > now())`.

#### Scenario: Doble-reserva del mismo slot es rechazada por DB

- **WHEN** two concurrent inserts target the same (`odontologo_id`, `inicio`) bypassing the API
- **THEN** the database rejects the second insert with a uniqueness violation (RN-DOBLE, P6)

#### Scenario: Solape parcial del mismo profesional es rechazado por DB

- **WHEN** a turno overlapping an existing range of the same `odontologo_id` is inserted bypassing the API
- **THEN** the database rejects it via the gist exclusion constraint (RN-SOLAPE, P6)

#### Scenario: Turno en el pasado es rechazado

- **WHEN** a turno with `inicio <= now()` is posted
- **THEN** the system responds 422 and persists nothing (RN-PASADO)

#### Scenario: Mismo inicio con distinto profesional sí se permite

- **WHEN** two turnos share `inicio` with different `odontologo_id`
- **THEN** both persist (borde: el aislamiento es por profesional)

### Requirement: TurnoHistorial append-only con actor obligatorio

The system SHALL write one `TurnoHistorial` row (`turno_id, estado_anterior/nuevo, actor_tipo, actor_id, fecha, motivo`) in the same commit as every state transition, and the application DB role SHALL be denied `UPDATE` and `DELETE` on it so history is insert-only.

#### Scenario: Transición feliz deja rastro con actor y fecha

- **WHEN** a turno moves `confirmado → cancelado` by recepcionista R with motivo
- **THEN** the system persists the new state plus a historial row with `actor_tipo='recepcionista'`, `actor_id=R`, non-null `fecha` and `motivo`

#### Scenario: Transición sin actor es rechazada

- **WHEN** a transition is attempted with no actor (null `actor_tipo`/`actor_id`) bypassing the API
- **THEN** the database rejects it via trigger/check (RN-ESTADOS)

#### Scenario: Rol app no puede reescribir historial

- **WHEN** the application role attempts `UPDATE` or `DELETE` on `turno_historial`
- **THEN** the database denies the statement (P9)

### Requirement: POST /reservas público con reconocimiento por DNI y gate de consentimiento

`POST /reservas` (no JWT, rate-limited) SHALL normalize the DNI (strip spaces/dots, 7–8 digits), reuse the existing patient on exact match (A2 via C-06 seam) or create one implicitly only with recorded consent, else fail the whole reservation with 422 `CONSENTIMIENTO_REQUERIDO` persisting nothing.

#### Scenario: Reserva feliz con DNI reconocido precarga paciente

- **WHEN** an anonymous client posts a valid slot plus an already-registered DNI
- **THEN** the system responds 201 reusing that patient and creates the turno in `creado`

#### Scenario: Reserva sin consentimiento falla sin persistir nada

- **WHEN** `POST /reservas` carries new-patient data with `consentimiento_datos = false` or missing timestamp
- **THEN** the system responds 422 `CONSENTIMIENTO_REQUERIDO` and creates neither patient nor turno (P11, contrato C-06)

#### Scenario: DNI con formato inválido es rechazado

- **WHEN** a reserva is posted with a DNI containing letters or wrong length
- **THEN** the system responds 422 and persists nothing (borde: `30.123.456` normaliza a `30123456` y sí vale)

#### Scenario: Ráfaga pública es limitada

- **WHEN** one IP exceeds the configured threshold on `POST /reservas` within 60 seconds
- **THEN** further requests respond 429 (P12, ruta 03 §3.2)

### Requirement: Pre-reserva con TTL expira liberando el slot

Every `creado` turno SHALL carry an expiry (`created_at + RESERVA_TTL_MIN`, default 15); a scheduled job SHALL move still-`creado` expired turnos to `cancelado` (motivo `ttl_expirado`, actor `sistema`) and the slot SHALL become offerable again.

#### Scenario: Pre-reserva no pagada expira a cancelado

- **WHEN** a `creado` turno passes its TTL with no approved payment
- **THEN** the job marks it `cancelado` with historial (`sistema`, `ttl_expirado`) and the slot reappears in `GET /disponibilidad` (A5, RN-LIBERACION)

#### Scenario: Turno confirmado no es tocado por el job

- **WHEN** the expiry job runs over a `confirmado` turno past TTL age
- **THEN** the turno keeps its state and no historial row is written (borde)

#### Scenario: Pago aprobado antes del TTL confirma en vez de expirar

- **WHEN** the MP webhook approves payment before expiry (seam C-07)
- **THEN** the turno is `confirmado` and the expiry job skips it

### Requirement: Idempotencia por Idempotency-Key en reserva

`POST /reservas` SHALL accept an `Idempotency-Key` header persisted as `UNIQUE(idempotency_key)`; a replay with the same key SHALL return the original result without creating a second turno.

#### Scenario: Replay con misma key no duplica

- **WHEN** the same `Idempotency-Key` is posted twice with identical payload
- **THEN** the second call returns the first turno (same id) and no second row exists (P4)

#### Scenario: Key distinta con mismo slot compite por constraint

- **WHEN** two different keys race for the same slot
- **THEN** exactly one turno persists and the loser receives 409 (concurrencia, RN-DOBLE)

### Requirement: Máquina de estados cerrada con actor por transición

Only these transitions SHALL exist — `creado→confirmado` (sistema/webhook MP), `confirmado→cancelado|reprogramado` (paciente dueño, odontólogo propio, recepcionista), `confirmado→atendido|no_show` (odontólogo propio, recepcionista; `no_show` only after `fin`), `cancelado→devuelto` (sistema tras devolución ejecutada) — and any other pair SHALL be rejected with 422.

#### Scenario: Confirmado a atendido por odontólogo propio

- **WHEN** the owning odontologo marks their `confirmado` turno `atendido`
- **THEN** the system responds 200 and writes historial with that actor

#### Scenario: Transición inválida es rechazada

- **WHEN** a client attempts `creado→atendido` or `atendido→cancelado`
- **THEN** the system responds 422 with an explicit transition error and state is unchanged (error de negocio)

#### Scenario: No-show antes del fin es rechazado

- **WHEN** staff marks `no_show` on a turno whose `fin` is in the future
- **THEN** the system responds 422 (borde temporal, RN-SENIA-0 solo post-`fin`)

#### Scenario: Paciente no cancela turno ajeno

- **WHEN** a mail-action token for patient P attempts to cancel patient Q's turno
- **THEN** the system responds 403 (P8 ownership)

### Requirement: Cotización previa muestra regla de seña antes de confirmar

Before confirming a cancellation, the system SHALL show the applicable rule computed from anticipation: in-term → 100 % (RN-SENIA-100), out-of-term → 60 % (RN-SENIA-60); confirming then moves the turno to `cancelado` and frees the slot in the same commit.

#### Scenario: Cancelación en término cotiza 100 %

- **WHEN** a cancellation is quoted inside the anticipation window
- **THEN** the quote shows 100 % refund before anything is persisted (B2)

#### Scenario: Cancelación fuera de término cotiza 60 %

- **WHEN** a cancellation is quoted outside the anticipation window
- **THEN** the quote shows 60 % and confirming creates the `devolucion` in `pendiente` with that percentage

#### Scenario: Confirmar libera el hueco en el mismo commit

- **WHEN** a cancellation is confirmed
- **THEN** the turno is `cancelado` and the slot is offerable again atomically — never a cancelled turno holding a slot (RN-LIBERACION)

### Requirement: Reprogramación atómica hereda el pago

Reprogramming a `confirmado` turno SHALL, in a single commit, move the origin to `reprogramado` (historial with actor+fecha) and create the new turno as `confirmado` inheriting the original `pago` with no new charge; the new slot SHALL pass RN-PASADO/DOBLE/SOLAPE/ANTICIPACION validation, keeping the original seña on amount differences (default pending Q3).

#### Scenario: Reprogramación feliz hereda pago

- **WHEN** staff reprogrammes a `confirmado` turno to a free slot
- **THEN** the origin is `reprogramado`, the new turno is `confirmado` linked to the same pago, and one historial row per side exists

#### Scenario: Nuevo slot ocupado aborta todo

- **WHEN** the target slot is taken concurrently
- **THEN** the whole operation rolls back: origin stays `confirmado` and no new turno exists (error de negocio)

### Requirement: Agenda del día staff aislada por profesional

Staff day-agenda reads SHALL return only turnos of the requested day filtered by the caller's `odontologo_id` through `scoped_repository` (odontologo: own only; recepcionista/admin: any), never exposing other professionals' turnos to an odontologo.

#### Scenario: Odontólogo ve solo su agenda

- **WHEN** an odontologo queries the day agenda with two professionals' turnos seeded
- **THEN** only their own turnos are returned (C1, RN-AISLAMIENTO, P8)

#### Scenario: Repository sin scope falla cerrado

- **WHEN** a scoped turno repository is built without `odontologo_id`
- **THEN** construction raises instead of returning unfiltered data

### Requirement: Reserva telefónica por recepcionista

Recepcionista/admin SHALL be able to create a reservation on behalf of a patient (`canal='recepcion'`, minimal data DNI+mail+consentimiento) under `require_role("recepcionista","admin")`; odontologo SHALL be denied on this route.

#### Scenario: Recepcionista reserva por teléfono

- **WHEN** a recepcionista posts a valid phone reservation for a patient
- **THEN** the system responds 201 with `canal='recepcion'`

#### Scenario: Odontólogo no usa la ruta telefónica

- **WHEN** an odontologo token calls the phone-reservation route
- **THEN** the system responds 403 (matriz 03 §2)

### Requirement: GET /mis-turnos exige token, nunca DNI solo

`GET /mis-turnos?dni&token` SHALL return only the turnos of the token's patient (token = C-03 short-lived single-use mail-action JWT); calls with DNI alone or with another patient's token SHALL be rejected.

#### Scenario: Token válido devuelve solo turnos propios

- **WHEN** a valid unused mail-action token for patient P is presented
- **THEN** the system responds 200 with only P's turnos

#### Scenario: DNI solo sin token es rechazado

- **WHEN** the endpoint is called with only a DNI and no token
- **THEN** the system responds 401 and exposes nothing (P12)

### Requirement: Schemas estrictos y migraciones versionadas

Every request/response model in this change SHALL set `extra='forbid'` (422 on undeclared fields, P2); all tables SHALL be created exclusively through Alembic migration `003` with zero `create_all` in runtime (P3); secrets and TTLs SHALL come only from env (`RESERVA_TTL_MIN`, JWT/MP secrets), never hardcoded (P5); v1 SHALL write zero rows to `lista_espera`, create zero sobre-turnos (P13).

#### Scenario: Campo no declarado es rechazado

- **WHEN** any reserva/agenda payload includes an undeclared field
- **THEN** the system responds 422 and persists nothing

#### Scenario: Base fresca se construye solo con migraciones

- **WHEN** migrations are applied to an empty database
- **THEN** `turno` and `turno_historial` exist and `alembic current` reports head `003`
