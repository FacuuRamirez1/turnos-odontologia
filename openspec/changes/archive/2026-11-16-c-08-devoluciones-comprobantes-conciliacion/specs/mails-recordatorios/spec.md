# Spec Delta — mails-recordatorios

## MODIFIED Requirements

### Requirement: Servicios de encolado por tipo de mail

The system SHALL provide enqueue operations for confirmation, reminder and refund notice. The refund-notice operation SHALL be invoked by the refund flow when a refund is executed or rejected, carrying percentage, amount, outcome and, when executed, the receipt to attach; it SHALL remain usable and testable at domain level.

#### Scenario: Recordatorio encolado con plantilla versionada

- **WHEN** a reminder is enqueued for a confirmed turno
- **THEN** the record stores `tipo = recordatorio` and the template version used

#### Scenario: Aviso de devolución encolado a nivel dominio

- **WHEN** the refund-notice operation is invoked for a turno with a refund quote
- **THEN** a record `tipo = aviso_devolucion` is created and its payload reflects the quoted percentage (sin ejecutar devolución real)

#### Scenario: Encolar sobre un turno inexistente falla explícitamente

- **WHEN** an enqueue operation references a non-existent turno
- **THEN** the operation fails with a domain error and persists nothing

#### Scenario: Devolución ejecutada encola el aviso con su resultado

- **WHEN** a refund is executed
- **THEN** a single `aviso_devolucion` record is created in the same transaction whose payload holds percentage, amount, outcome `ejecutada` and the receipt reference

### Requirement: Plantillas versionadas con texto, HTML y links de acción

The system SHALL render versioned templates (`confirmacion`, `recordatorio`, `aviso_devolucion`) with a plain-text part and an HTML part. All interpolated values SHALL be HTML-escaped, and confirmation/reminder templates SHALL include confirm and cancel links built from `API_PUBLIC_URL`. The refund notice SHALL state percentage, amount and outcome, and carry "(simulado)" when `PAGO_MODO=simulado`.

#### Scenario: Render feliz incluye ambos formatos y links

- **WHEN** a reminder template is rendered for a confirmed turno
- **THEN** the message has text and HTML parts and both action links

#### Scenario: Dato del paciente con HTML es escapado

- **WHEN** a patient name contains `<script>` or `&`
- **THEN** the rendered HTML escapes it and does not emit executable markup (error de negocio / seguridad)

#### Scenario: Devolución usa la plantilla de aviso

- **WHEN** an `aviso_devolucion` is rendered
- **THEN** the message states the refund percentage and does not offer confirm/cancel actions (borde)

#### Scenario: Aviso de devolución ejecutada en modo simulado

- **WHEN** an `aviso_devolucion` for an executed refund is rendered with `PAGO_MODO=simulado`
- **THEN** both parts state the amount and contain "(simulado)", and the text says that no real money was moved (P15)

#### Scenario: Aviso de devolución rechazada

- **WHEN** an `aviso_devolucion` for a rejected refund is rendered
- **THEN** the message states that the refund was not granted and mentions no amount returned (error de negocio)

### Requirement: Envío SMTP configurable sin nuevas dependencias

The system SHALL send mail through the standard-library SMTP adapter configured only by `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS` and `MAIL_FROM`, using no additional dependency. Local development SHALL work against MailHog at `mailhog:1025` without authentication. The adapter SHALL support optional PDF attachments.

#### Scenario: Envío local contra MailHog

- **WHEN** the worker delivers a mail with MailHog settings and empty credentials
- **THEN** the message is accepted without authentication and the record becomes `enviado`

#### Scenario: SMTP caído deja el envío reintentable

- **WHEN** the SMTP server is unreachable during a delivery attempt
- **THEN** the record keeps its attempt count, records `ultimo_error` and schedules a retry (error de negocio)

#### Scenario: Remitente siempre alineado a MAIL_FROM

- **WHEN** any template is rendered and sent
- **THEN** the `From` header equals the configured `MAIL_FROM` (borde, P14)

#### Scenario: Aviso de devolución ejecutada viaja con el recibo adjunto

- **WHEN** the worker delivers an `aviso_devolucion` for an executed refund
- **THEN** the message carries one `application/pdf` attachment with the refund receipt and no public link to it (P12)

### Requirement: Cancelar desde el mail deriva a la regla de seña sin ejecutar devolución

`GET /api/mail/cancelar?token=` SHALL validate the action token, cancel a `confirmado` turno through the C-05 state machine, show the applicable 100/60/0 quote, and mark the delivery record `cancelado_desde_mail`. It SHALL leave the refund `pendiente` in the bandeja when the turno had an approved payment and the quote is above 0 %, and SHALL NOT approve or execute any refund.

#### Scenario: Cancelación válida mueve el turno y muestra la cotización

- **WHEN** a valid unused cancel token for a `confirmado` turno is opened
- **THEN** the turno becomes `cancelado` with actor `paciente` and the page shows the applicable percentage

#### Scenario: Turno ya cancelado no se recancela

- **WHEN** a cancel token is used for a turno that is not `confirmado`
- **THEN** the system reports the invalid state and writes no transition (error de negocio)

#### Scenario: Cancelación no invoca ninguna devolución real

- **WHEN** a cancellation from mail completes
- **THEN** no refund is executed or recorded as executed; at most a `devolucion(pendiente)` is created for staff review (borde)

#### Scenario: Cancelación desde mail deja la devolución en bandeja

- **WHEN** a patient cancels from mail a turno with an approved payment
- **THEN** a `devolucion(pendiente)` with the quoted percentage appears in the bandeja and the page says the refund will be reviewed, marked "(simulado)" in simulated mode

#### Scenario: Cancelación desde mail con cotización 0 % no genera devolución ni aviso

- **WHEN** a patient cancels from mail, after the turno's `inicio`, a turno with an approved payment (quote 0 %)
- **THEN** the turno becomes `cancelado`, the page shows 0 %, and no `devolucion` nor `aviso_devolucion` record is created (borde, RN-SENIA-0)
