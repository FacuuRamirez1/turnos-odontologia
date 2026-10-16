# disponibilidad-slots

## Purpose

Lets each odontólogo publish their bookable availability and lets the public flow query only the free slots for a professional on a given day, with business rules enforced in the database as well as the API.

## Requirements

### Requirement: Disponibilidad CRUD staff con RBAC por scope

The system SHALL let staff create, list, update and delete `Disponibilidad` rows (`odontologo_id, dia_semana 0=lunes..6=domingo, hora_inicio, hora_fin, duracion_min, tope_dia, vigente_desde/hasta`); an odontologo SHALL operate only rows with their own `odontologo_id`, while recepcionista/admin SHALL operate rows for any professional.

#### Scenario: Odontólogo crea su disponibilidad

- **WHEN** an authenticated odontologo posts a valid row with their own `odontologo_id`
- **THEN** the system responds 201 and the row is persisted

#### Scenario: Odontólogo no toca disponibilidad ajena

- **WHEN** an odontologo attempts to create, update or delete a row with another professional's `odontologo_id`
- **THEN** the system responds 403 and nothing is persisted or changed

#### Scenario: Recepcionista gestiona cualquier profesional

- **WHEN** a recepcionista creates or updates a row for any `odontologo_id`
- **THEN** the system authorizes it

#### Scenario: Rango horario inválido es rechazado

- **WHEN** a row is posted with `hora_fin <= hora_inicio`, `duracion_min <= 0`, `tope_dia <= 0` or `dia_semana` outside 0..6
- **THEN** the system responds 422 and persists nothing

### Requirement: Bloqueos CRUD con motivo cerrado

The system SHALL let staff create, list and delete `Bloqueo` rows (`odontologo_id` NOT NULL, `desde`, `hasta`, `motivo`, `created_by`); `motivo` SHALL be one of `pausa|feriado|bloqueo|vacaciones`, `hasta` SHALL be after `desde`, and the same odontologo-own / recepcionista-any scope rule as disponibilidad SHALL apply.

#### Scenario: Recepcionista carga feriado del profesional

- **WHEN** a recepcionista posts a `Bloqueo` with `motivo='feriado'` covering a full day for an `odontologo_id`
- **THEN** the system responds 201

#### Scenario: Motivo fuera de lista es rechazado

- **WHEN** a bloqueo is posted with a `motivo` outside the 4 allowed values
- **THEN** the system responds 422 and persists nothing

#### Scenario: Bloqueo invertido es rechazado

- **WHEN** a bloqueo is posted with `hasta <= desde`
- **THEN** the system responds 422 and persists nothing

### Requirement: Montos turno y seña configurables por odontólogo

The system SHALL let an authenticated odontologo update only their own `monto_turno` and `monto_senia` (non-negative, at most 2 decimals); recepcionista/admin SHALL be denied (matriz 03 §2).

#### Scenario: Odontólogo actualiza sus montos

- **WHEN** an odontologo patches their own montos with non-negative values
- **THEN** the system responds 200 with the updated amounts

#### Scenario: Recepcionista no configura montos

- **WHEN** a recepcionista attempts to update any montos
- **THEN** the system responds 403 and amounts are unchanged

#### Scenario: Monto negativo es rechazado

- **WHEN** an odontologo patches a negative `monto_turno` or `monto_senia`
- **THEN** the system responds 422 and amounts are unchanged

### Requirement: Motor de slots en múltiplos exactos con tope diario

The slot engine SHALL generate candidate slots as exact multiples of `duracion_min` measured from `hora_inicio` (a trailing partial interval is dropped, never offered), and SHALL offer at most `tope_dia` slots per professional per day (RN-DURACION, RN-TOPE).

#### Scenario: Grilla exacta de 30 minutos

- **WHEN** disponibilidad is 09:00–10:00 with `duracion_min=30`
- **THEN** the engine yields exactly 09:00–09:30 and 09:30–10:00

#### Scenario: Resto parcial no se ofrece

- **WHEN** disponibilidad is 09:00–09:50 with `duracion_min=30`
- **THEN** the engine yields only 09:00–09:30 (09:30–10:00 would exceed `hora_fin`)

#### Scenario: Tope diario corta la oferta

- **WHEN** `tope_dia=2` with 4 candidate slots and no blocks or bookings
- **THEN** only the first 2 slots of the day are offered

### Requirement: Bloqueos y ocupados restan slots ofrecibles

The engine SHALL remove any candidate slot overlapping a `Bloqueo` interval for that professional and day, and SHALL subtract already-booked slots passed in as input; booked input is empty in C-04 (no `turno` table yet) and is the seam C-05 will wire (RN-PAUSAS).

#### Scenario: Pausa del mediodía quita slots

- **WHEN** a `pausa` block covers 12:00–13:00 and candidates exist on both sides
- **THEN** slots inside 12:00–13:00 are absent while morning and afternoon slots remain

#### Scenario: Feriado de día completo vacía el día

- **WHEN** a `feriado` block covers the whole working range of a date
- **THEN** zero slots are offered for that professional and date

#### Scenario: Slot límite que toca el bloqueo no se ofrece

- **WHEN** a candidate slot overlaps a block even partially (e.g. 11:30–12:00 vs block from 11:45)
- **THEN** that slot is absent (any overlap removes it)

### Requirement: Anticipación mínima configurable

Slots SHALL be offered only when `slot.inicio - now >= ANTICIPACION_MIN_HS` (default 24, env-overridable); slots inside the anticipation window SHALL be absent (RN-ANTICIPACION).

#### Scenario: Slots de mañana no se ofrecen hoy

- **WHEN** now is 10:00 and a slot starts tomorrow at 09:00 (23 h ahead, anticipacion 24 h)
- **THEN** that slot is absent

#### Scenario: Slot justo en el límite sí se ofrece

- **WHEN** a slot starts exactly `ANTICIPACION_MIN_HS` after now
- **THEN** that slot is offered (boundary is inclusive)

#### Scenario: Fecha pasada es rechazada

- **WHEN** the public endpoint is queried with a `fecha` before today
- **THEN** the system responds 422

### Requirement: Endpoint público de huecos libres con rate-limit

`GET /disponibilidad?odontologo_id&fecha=` (both required, `fecha` YYYY-MM-DD) SHALL return only free slots (`inicio`, `fin` ISO) for that professional and date, SHALL contain zero data about other patients, and SHALL be rate-limited to 30 requests/minute per IP (429 beyond; P12, ruta 03 §3.1).

#### Scenario: Día con huecos devuelve solo inicios y fines

- **WHEN** an anonymous client queries a date with 3 free slots
- **THEN** the system responds 200 with exactly those 3 `inicio/fin` pairs and no patient fields

#### Scenario: Día vacío devuelve lista vacía

- **WHEN** an anonymous client queries a date fully blocked or past the daily cap
- **THEN** the system responds 200 with an empty slot list (not an error)

#### Scenario: Parámetros faltantes o malformados son rechazados

- **WHEN** the query omits `odontologo_id`, omits `fecha`, or passes a non-date `fecha`
- **THEN** the system responds 422

#### Scenario: Ráfaga pública es limitada

- **WHEN** one IP exceeds 30 requests within 60 seconds on this route
- **THEN** further requests respond 429

### Requirement: Aislamiento por profesional en cada lectura staff

Every staff read of disponibilidad, bloqueos and generated slots SHALL be filtered by `odontologo_id` through `scoped_repository`, so an odontologo SHALL never receive rows or slots of another professional (RN-AISLAMIENTO, P8).

#### Scenario: Odontólogo lista solo lo propio

- **WHEN** an odontologo lists disponibilidad with rows of two professionals seeded
- **THEN** only their own rows are returned

#### Scenario: Repository sin scope falla cerrado

- **WHEN** a scoped repository for `Disponibilidad` or `Bloqueo` is built without `odontologo_id`
- **THEN** construction raises instead of returning unfiltered data

### Requirement: Schemas Pydantic estrictos en todo endpoint

Every request/response model in this change SHALL set `extra='forbid'`; any payload with an undeclared field SHALL be rejected with 422 and cause no state change (P2).

#### Scenario: Campo no declarado es rechazado

- **WHEN** a disponibilidad create payload includes an undeclared field
- **THEN** the system responds 422 and persists nothing

### Requirement: Migración versionada con constraints de dominio en DB

All tables SHALL be created exclusively through Alembic migration `002` (zero `create_all` in runtime, P3); Postgres SHALL enforce no-overlap of disponibilidad rows per (`odontologo_id`, `dia_semana`) via `EXCLUDE USING gist`, plus `CHECK`s on time range, positive duration/cap and closed motivo list (P6).

#### Scenario: Base fresca se construye solo con migraciones

- **WHEN** migrations are applied to an empty database
- **THEN** `disponibilidad` and `bloqueo` exist and `alembic current` reports head `002`

#### Scenario: Disponibilidades solapadas del mismo profesional son rechazadas por DB

- **WHEN** two overlapping time ranges for the same (`odontologo_id`, `dia_semana`) are inserted bypassing the API
- **THEN** the database rejects the second insert

#### Scenario: Sin create_all en runtime

- **WHEN** the backend codebase is searched for `create_all`
- **THEN** zero matches exist outside tests asserting its absence

### Requirement: Motor y endpoint restan turnos activos ocupados

The slot engine and `GET /disponibilidad?odontologo_id&fecha` SHALL additionally subtract slots occupied by active turnos of that professional and day (`creado` not yet expired plus `confirmado`); `cancelado`, `reprogramado` (origin), `atendido`, `no_show` and `devuelto` SHALL free the slot. Expired `creado` SHALL count as free even before the job runs (expiry is computed, not only job-driven).

#### Scenario: Slot con turno confirmado no se ofrece

- **WHEN** an anonymous client queries a date where 09:00–09:30 holds a `confirmado` turno
- **THEN** the system responds 200 without that slot while other free slots remain

#### Scenario: Slot con turno cancelado vuelve a ofrecerse

- **WHEN** the occupying turno is `cancelado` (or origin `reprogramado`)
- **THEN** the slot reappears in the response (RN-LIBERACION)

#### Scenario: Pre-reserva expirada cuenta como libre

- **WHEN** a `creado` turno is past `created_at + RESERVA_TTL_MIN` with no approved payment
- **THEN** its slot is offered as free (borde: expiración computada, el job solo formaliza el estado)
