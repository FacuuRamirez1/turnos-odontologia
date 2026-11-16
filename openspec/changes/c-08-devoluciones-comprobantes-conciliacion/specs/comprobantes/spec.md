# Spec Delta — comprobantes

## Purpose

Emite y entrega recibos internos inmutables por cada pago aprobado y cada devolución ejecutada, separados del turno y del pago para que la facturación ARCA de v2 no exija refactorizar, y deja inequívoco en el PDF cuando el comprobante es simulado y no tiene valor fiscal.

## ADDED Requirements

### Requirement: Comprobante separado e inmutable

The system SHALL persist receipts as `comprobante` records separate from `turno` and `pago` (D13), with `tipo` (`recibo_interno` in v1; `factura_arca` reserved for v2), concepto (`pago` or `devolucion`), a unique sequential `numero`, `monto`, `emitida_at`, `simulado`, a data snapshot and ARCA columns such as `cae` that stay null in v1. The application role SHALL NOT be able to update or delete receipts.

#### Scenario: Recibo emitido con número correlativo
- **WHEN** two receipts are emitted one after the other
- **THEN** each has a distinct `numero` from the same correlative series and `tipo = recibo_interno`

#### Scenario: Comprobante no se modifica ni se borra
- **WHEN** the application role attempts `UPDATE` or `DELETE` on `comprobante`
- **THEN** the database denies the statement (error de negocio, auditoría)

#### Scenario: Campos ARCA quedan apagados en v1
- **WHEN** any receipt is emitted with `ARCA_ENABLED=false`
- **THEN** `tipo = recibo_interno` and `cae` is null; no `factura_arca` is ever emitted (borde, P13)

### Requirement: Recibo interno por pago aprobado

When a payment becomes `aprobado` through the webhook handler, the system SHALL emit exactly one receipt with concepto `pago` for it, in the same transaction.

#### Scenario: Aprobación del pago emite su recibo
- **WHEN** the webhook approves a `pendiente` payment
- **THEN** one receipt with concepto `pago`, the payment amount and `simulado = true` (in simulated mode) exists for that payment

#### Scenario: Pago rechazado no emite recibo
- **WHEN** the webhook rejects or expires a payment
- **THEN** no receipt exists for that payment (error de negocio)

#### Scenario: Replay del webhook no duplica el recibo
- **WHEN** the same approval webhook is delivered twice
- **THEN** there is still exactly one receipt with concepto `pago` for that payment (borde, idempotencia)

### Requirement: Recibo interno por devolución ejecutada

When a refund becomes `ejecutada`, the system SHALL emit exactly one receipt with concepto `devolucion` for the refunded amount, linked to the refund, payment and turno, in the same transaction.

#### Scenario: Ejecución emite recibo de devolución
- **WHEN** a 60 % refund of 6000.00 is executed
- **THEN** one receipt with concepto `devolucion`, `monto = 6000.00` and a link to the refund exists

#### Scenario: Devolución rechazada no emite recibo
- **WHEN** a refund is rejected
- **THEN** no receipt with concepto `devolucion` is emitted (error de negocio)

#### Scenario: Cancelación con 0 % no emite recibo de devolución
- **WHEN** a turno with an approved payment is cancelled with a 0 % quote
- **THEN** no receipt with concepto `devolucion` exists and the payment keeps only its `pago` receipt (borde, RN-SENIA-0)

#### Scenario: Reintento de ejecución no duplica el recibo
- **WHEN** the execution of the same refund is retried
- **THEN** there is still exactly one receipt for that refund (borde)

### Requirement: PDF del recibo con leyenda de simulado

Staff SHALL download each receipt as a PDF showing number, date, patient, dentist, concept and amount. A receipt with `simulado = true` SHALL show the visible legend "SIMULADO — sin valor fiscal ni movimiento de dinero"; the legend depends on the receipt's own flag, not on the current `PAGO_MODO`.

#### Scenario: PDF simulado lleva la leyenda
- **WHEN** staff downloads the PDF of a receipt emitted with `PAGO_MODO=simulado`
- **THEN** the response is `application/pdf` and its text contains "SIMULADO — sin valor fiscal ni movimiento de dinero" (P15)

#### Scenario: Leyenda persiste aunque cambie el modo
- **WHEN** a receipt emitted as `simulado = true` is downloaded after the deployment changed `PAGO_MODO`
- **THEN** the PDF still contains the legend (borde)

#### Scenario: Recibo inexistente
- **WHEN** staff requests the PDF of a receipt id that does not exist
- **THEN** the system responds 404 (error de negocio)

### Requirement: Acceso a comprobantes solo para staff con alcance por rol

Receipt detail and PDF SHALL only be served to authenticated staff: dentists only for receipts of their own turnos, recepcionista and admin for all (P8). There SHALL be no public URL for receipts; patients receive the refund receipt only as a mail attachment (P12).

#### Scenario: Recepcionista descarga cualquier recibo
- **WHEN** a recepcionista downloads a receipt of any dentist
- **THEN** the system responds 200 with the PDF

#### Scenario: Odontólogo no descarga recibos ajenos
- **WHEN** dentist A downloads a receipt of a turno of dentist B
- **THEN** the system responds 403 (error de negocio, P8)

#### Scenario: Sin autenticación no hay acceso
- **WHEN** the receipt endpoints are called without a staff bearer token
- **THEN** the system responds 401 and no PDF is produced (borde, P12)
