# Spec Delta — mails-recordatorios

## Purpose

Entrega mails transaccionales del consultorio (confirmación, recordatorio y aviso de devolución) de forma confiable y observable, permite confirmar o cancelar un turno desde el propio mail con tokens de un solo uso, y expone el estado de entrega al staff. Sobrevive a caídas del worker, a SMTP intermitente y a replays sin duplicar envíos ni acciones.

## ADDED Requirements

### Requirement: Registro de entrega persistente e idempotente por turno y tipo

The system SHALL persist one delivery record per `(turno_id, tipo)` where `tipo` is one of `confirmacion | recordatorio | aviso_devolucion`, with a closed delivery state, `intentos`, `ultimo_error`, `proximo_intento_at`, template version and action-token metadata. A second enqueue for the same pair SHALL return the existing record instead of creating a duplicate.

#### Scenario: Primer encolado crea el registro

- **WHEN** a confirmation is enqueued for a confirmed turno without a delivery record
- **THEN** one record is persisted in state `encolado` with `intentos = 0` and a template version

#### Scenario: Reintento del mismo tipo no duplica

- **WHEN** the same turno is enqueued twice for `confirmacion`
- **THEN** only one record exists for `(turno_id, 'confirmacion')` and the second call returns it unchanged

#### Scenario: Tipos distintos sobre el mismo turno conviven

- **WHEN** a `confirmacion` and a `recordatorio` are enqueued for the same turno
- **THEN** two independent records exist (borde: la unicidad es por par turno+tipo)

### Requirement: Outbox transaccional en la transición de confirmación

When a turno transitions `creado → confirmado` with actor type `sistema`, the system SHALL insert the confirmation delivery record in the SAME database transaction as the state change and its history row. If the transaction rolls back, no delivery record SHALL remain.

#### Scenario: Confirmación aprobada deja outbox en el mismo commit

- **WHEN** the turno becomes `confirmado` by actor `sistema`
- **THEN** the turno, its `turno_historial` row and the `confirmacion` outbox record are committed together

#### Scenario: Rollback no deja outbox huérfano

- **WHEN** the confirmation transition fails or the transaction rolls back
- **THEN** neither the state change nor the delivery record persist (error de negocio)

#### Scenario: Otras transiciones no generan confirmación

- **WHEN** a turno moves `confirmado → atendido` or `confirmado → cancelado`
- **THEN** no automatic `confirmacion` record is created (borde)

### Requirement: Servicios de encolado por tipo de mail

The system SHALL provide enqueue operations for confirmation, reminder and refund notice. The refund-notice operation SHALL be usable and testable at domain level even when no production flow invokes it yet.

#### Scenario: Recordatorio encolado con plantilla versionada

- **WHEN** a reminder is enqueued for a confirmed turno
- **THEN** the record stores `tipo = recordatorio` and the template version used

#### Scenario: Aviso de devolución encolado a nivel dominio

- **WHEN** the refund-notice operation is invoked for a turno with a refund quote
- **THEN** a record `tipo = aviso_devolucion` is created and its payload reflects the quoted percentage (sin ejecutar devolución real)

#### Scenario: Encolar sobre un turno inexistente falla explícitamente

- **WHEN** an enqueue operation references a non-existent turno
- **THEN** the operation fails with a domain error and persists nothing

### Requirement: Paciente sin email queda fallido sin reintentos

If the patient has no usable email address, the system SHALL persist the delivery record in terminal state `fallido` with `destinatario = ''` and `ultimo_error = 'paciente sin email'`, and SHALL NOT retry it.

#### Scenario: Turno sin email no entra a la cola

- **WHEN** a confirmation is enqueued for a patient whose email is null or blank
- **THEN** the record is `fallido`, `intentos = 0`, and no job is pushed to the queue

#### Scenario: Registro fallido por falta de email es visible

- **WHEN** staff reads delivery metrics after a patient without email was enqueued
- **THEN** the failed count includes that record (error de negocio visible, E3)

#### Scenario: Email presente sí encola

- **WHEN** the patient has a non-blank email
- **THEN** the record starts `encolado` and a job is published to `mail:pendientes` (borde)

### Requirement: Token de acción de un solo uso persistido por hash

Each action mail SHALL carry a signed action token with `proposito = 'mail_accion'`; the system SHALL persist only its SHA-256 hash, an expiry from `MAIL_ACTION_TTL_MIN` (default 2880 minutes) and a single-use marker in the database. The single-use rule SHALL be enforced by the database record, not only by in-memory state.

#### Scenario: Primer uso válido del token

- **WHEN** an unexpired, unused action token is presented
- **THEN** the action executes and the record is marked used with a timestamp

#### Scenario: Reutilización del mismo token es rechazada

- **WHEN** the same action token is presented a second time
- **THEN** the system rejects the action and performs no state change (error de negocio)

#### Scenario: Token expirado es rechazado

- **WHEN** a token is presented after `MAIL_ACTION_TTL_MIN` has elapsed
- **THEN** the system rejects it with an expiration message and no state change (borde)

#### Scenario: No se persiste el token crudo

- **WHEN** a delivery record is persisted
- **THEN** only the SHA-256 hash of the token is stored, never the raw token (P12)

### Requirement: Envío SMTP configurable sin nuevas dependencias

The system SHALL send mail through the standard-library SMTP adapter configured only by `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS` and `MAIL_FROM`, using no additional dependency. Local development SHALL work against MailHog at `mailhog:1025` without authentication.

#### Scenario: Envío local contra MailHog

- **WHEN** the worker delivers a mail with MailHog settings and empty credentials
- **THEN** the message is accepted without authentication and the record becomes `enviado`

#### Scenario: SMTP caído deja el envío reintentable

- **WHEN** the SMTP server is unreachable during a delivery attempt
- **THEN** the record keeps its attempt count, records `ultimo_error` and schedules a retry (error de negocio)

#### Scenario: Remitente siempre alineado a MAIL_FROM

- **WHEN** any template is rendered and sent
- **THEN** the `From` header equals the configured `MAIL_FROM` (borde, P14)

### Requirement: Plantillas versionadas con texto, HTML y links de acción

The system SHALL render three versioned templates in v1 (`confirmacion`, `recordatorio`, `aviso_devolucion`) with a plain-text part and an HTML part. All interpolated values SHALL be HTML-escaped, and confirmation/reminder templates SHALL include confirm and cancel links built from `API_PUBLIC_URL`.

#### Scenario: Render feliz incluye ambos formatos y links

- **WHEN** a reminder template is rendered for a confirmed turno
- **THEN** the message has text and HTML parts and both action links

#### Scenario: Dato del paciente con HTML es escapado

- **WHEN** a patient name contains `<script>` or `&`
- **THEN** the rendered HTML escapes it and does not emit executable markup (error de negocio / seguridad)

#### Scenario: Devolución usa la plantilla de aviso

- **WHEN** an `aviso_devolucion` is rendered
- **THEN** the message states the refund percentage and does not offer confirm/cancel actions (borde)

### Requirement: Worker con reintentos acotados y backoff

The worker SHALL consume `mail:pendientes` with payload `{"recordatorio_id": "<uuid>"}`, re-read the record from the database, verify it is still sendable, send it, and mark terminal states. It SHALL allow at most 3 attempts with backoff delays of 1 and 5 minutes via `proximo_intento_at`, and the third failure SHALL end in `fallido`.

#### Scenario: Primer intento exitoso

- **WHEN** a queued record is processed and SMTP accepts it
- **THEN** the record becomes `enviado` and no retry is scheduled

#### Scenario: Fallo transitorio reintenta

- **WHEN** the first attempt fails
- **THEN** the record becomes `reintentando`, `intentos = 1` and `proximo_intento_at` is about 1 minute later (error de negocio)

#### Scenario: Tercer fallo termina en fallido

- **WHEN** the third attempt fails
- **THEN** the record becomes `fallido` with `intentos = 3` and no further retry (borde, E3)

#### Scenario: Replay del mismo job no reenvía

- **WHEN** the same `recordatorio_id` is consumed twice
- **THEN** the second processing sends nothing because the record is no longer sendable (idempotencia)

### Requirement: Scheduler de ventana de recordatorio

The worker SHALL run a periodic scheduler that finds `confirmado` turnos starting within `RECORDATORIO_VENTANA_HS` that have no reminder yet, and SHALL enqueue one reminder per turno. It SHALL also re-enqueue overdue `reintentando` records whose `proximo_intento_at` has passed.

#### Scenario: Turno dentro de la ventana recibe recordatorio

- **WHEN** a confirmed turno starts within the configured window and has no reminder
- **THEN** exactly one `recordatorio` record is enqueued

#### Scenario: Turno fuera de la ventana no recibe recordatorio

- **WHEN** a confirmed turno starts after the window
- **THEN** no reminder is created (error de negocio)

#### Scenario: Reintento vencido se vuelve a encolar

- **WHEN** a record is `reintentando` with `proximo_intento_at` in the past
- **THEN** the scheduler republishes its job once (borde)

### Requirement: Confirmar desde el mail es idempotente

`GET /api/mail/confirmar?token=` SHALL validate the action token, confirm only a `confirmado` turno belonging to the token, and mark the delivery record `confirmado_desde_mail`. Replaying the action SHALL return a safe, non-destructive result without duplicating history or changing other turnos.

#### Scenario: Confirmación válida deja rastro en el mail y no toca el turno

- **WHEN** a valid unused confirm token for a `confirmado` turno is opened
- **THEN** the response is successful HTML and the delivery record becomes `confirmado_desde_mail`

#### Scenario: Token ajeno no autoriza el turno

- **WHEN** the token belongs to a different turno or patient
- **THEN** the system responds with a non-success HTML page and changes nothing (error de negocio, P12)

#### Scenario: Replay de confirmación no duplica

- **WHEN** the same confirm token or an already-confirmed turno is processed again
- **THEN** the page reports the turno is already confirmed and no new history row is written (borde)

### Requirement: Cancelar desde el mail deriva a la regla de seña sin ejecutar devolución

`GET /api/mail/cancelar?token=` SHALL validate the action token, cancel a `confirmado` turno through the C-05 state machine, show the applicable 100/60/0 quote, and mark the delivery record `cancelado_desde_mail`. It SHALL NOT execute a real refund because C-08 is not implemented.

#### Scenario: Cancelación válida mueve el turno y muestra la cotización

- **WHEN** a valid unused cancel token for a `confirmado` turno is opened
- **THEN** the turno becomes `cancelado` with actor `paciente` and the page shows the applicable percentage

#### Scenario: Turno ya cancelado no se recancela

- **WHEN** a cancel token is used for a turno that is not `confirmado`
- **THEN** the system reports the invalid state and writes no transition (error de negocio)

#### Scenario: Cancelación no invoca ninguna devolución real

- **WHEN** a cancellation from mail completes
- **THEN** no refund is executed or recorded as executed; only the quote is shown (borde, C-08 pendiente)

### Requirement: Endpoints públicos de mail con rate-limit

Both `/api/mail/confirmar` and `/api/mail/cancelar` SHALL be public (no JWT) and rate-limited by client IP using `MAIL_RATE_LIMIT`. Exceeding the threshold SHALL return HTTP 429 without consuming the token.

#### Scenario: Uso normal queda bajo el límite

- **WHEN** a client below the threshold opens a valid action link
- **THEN** the request is processed and the token is consumed only on success

#### Scenario: Ráfaga excede el límite

- **WHEN** one IP exceeds `MAIL_RATE_LIMIT` within the window
- **THEN** further requests return 429 and the token remains unused (error de negocio)

#### Scenario: Token inválido no consume el cupo de acciones válidas

- **WHEN** a malformed token is presented
- **THEN** the system responds with a non-success page without altering any record (borde)

### Requirement: Métricas de entrega visibles para staff

The system SHALL expose delivery counts grouped by state (`encolado`, `enviado`, `reintentando`, `fallido`, `confirmado_desde_mail`, `cancelado_desde_mail`) through `GET /api/mail/metricas`, restricted to authenticated staff roles.

#### Scenario: Staff consulta métricas

- **WHEN** an authenticated odontologo, recepcionista or admin requests the metrics endpoint
- **THEN** the response contains counts per state for the current period

#### Scenario: Paciente no accede a métricas

- **WHEN** the metrics endpoint is called without a valid staff token
- **THEN** the system responds 401/403 and exposes no counts (error de negocio, P8)

#### Scenario: Sin registros responde ceros

- **WHEN** no delivery records exist
- **THEN** every state appears with count 0 (borde)

### Requirement: Migración versionada y configuración solo por entorno

The delivery table SHALL be created exclusively by Alembic migration `004_recordatorio_mail`, chained to the real head `003_turno_historial`, with zero `create_all` at runtime (P3). New settings SHALL come only from environment variables and SHALL NOT alter the 15 pinned variables of the C-01 contract (P5/P14).

#### Scenario: Base fresca reporta head 004

- **WHEN** migrations run on an empty database
- **THEN** the delivery table exists and `alembic current` reports `004_recordatorio_mail`

#### Scenario: Down migration revierte solo lo nuevo

- **WHEN** `downgrade` runs from `004`
- **THEN** the delivery table and its indexes are removed and the previous head remains `003_turno_historial`

#### Scenario: Variables pineadas intactas

- **WHEN** the environment contract is read after this change
- **THEN** `RECORDATORIO_VENTANA_HS=24`, `RESERVA_TTL_MIN=15`, `WHATSAPP_ENABLED=false` and `ARCA_ENABLED=false` remain unchanged (borde)
