# Spec Delta — reserva-turnos-estados

## MODIFIED Requirements

### Requirement: Cotización previa muestra regla de seña antes de confirmar

Before confirming a cancellation, the system SHALL show the applicable rule computed from anticipation: in-term → 100 % (RN-SENIA-100), out-of-term → 60 % (RN-SENIA-60); confirming then moves the turno to `cancelado`, frees the slot and, when the turno has an approved payment and the quote is above 0 %, persists the `devolucion(pendiente)` with that percentage, all in the same commit. The response SHALL return the persisted refund (`id`, `porcentaje`, `monto`, `estado`) or `null` when there is no approved payment or the quote is 0 %.

#### Scenario: Cancelación en término cotiza 100 %
- **WHEN** a cancellation is quoted inside the anticipation window
- **THEN** the quote shows 100 % refund before anything is persisted (B2)

#### Scenario: Cancelación fuera de término cotiza 60 %
- **WHEN** a cancellation is quoted outside the anticipation window
- **THEN** the quote shows 60 % and confirming creates the `devolucion` in `pendiente` with that percentage

#### Scenario: Confirmar libera el hueco en el mismo commit
- **WHEN** a cancellation is confirmed
- **THEN** the turno is `cancelado` and the slot is offerable again atomically — never a cancelled turno holding a slot (RN-LIBERACION)

#### Scenario: Respuesta de cancelación refleja la devolución persistida
- **WHEN** staff confirms the cancellation of a `confirmado` turno with an approved payment
- **THEN** the response includes `devolucion` with the persisted `id`, `porcentaje`, `monto` and `estado = pendiente`, and that refund is visible in the bandeja

#### Scenario: Cancelación sin pago aprobado responde devolución nula
- **WHEN** a cancellation is confirmed for a turno with no approved payment
- **THEN** the response has `devolucion = null` and no refund is created (borde)

#### Scenario: Cancelación con cotización 0 % responde devolución nula
- **WHEN** a cancellation is confirmed for a turno with an approved payment after its `inicio` (quote 0 %, RN-SENIA-0)
- **THEN** the turno is `cancelado` and stays so (never `devuelto`), the response has `devolucion = null` and no refund is created (borde)
