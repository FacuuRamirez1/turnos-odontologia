# Spec Delta — disponibilidad-slots

## ADDED Requirements

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
