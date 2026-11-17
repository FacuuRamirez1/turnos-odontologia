# devoluciones Specification

## Purpose
Gestiona la devolución de la seña de un turno cancelado: la registra con el porcentaje que fija la política 100/60 (con 0 % no hay devolución), la hace pasar por una bandeja con aprobación manual trazable (actor + fecha + monto), la ejecuta de forma idempotente a través del proveedor de pagos (simulado en el MVP, sin mover dinero) y cierra el turno en `devuelto`.

## Requirements

### Requirement: Devolución persistida con constraints de dominio en DB

The system SHALL persist each refund as a `devolucion` record linked to its `pago` and `turno`, with `monto`, `porcentaje` (100 or 60), `motivo`, `estado` (`pendiente|aprobada|rechazada|ejecutada`), an `idempotency_key` and a `mp_refund_id`. The database SHALL enforce one refund per payment, unique `idempotency_key`, unique `mp_refund_id`, the closed set of states and percentages, and `monto` greater than 0 and not above the payment amount (P4, P6).

#### Scenario: Devolución válida se persiste
- **WHEN** a refund of 60 % is recorded for an approved payment of 10000.00 ARS
- **THEN** a `devolucion` exists with `porcentaje = 60`, `monto = 6000.00`, `estado = pendiente` and a non-null `idempotency_key`

#### Scenario: Segunda devolución para el mismo pago es rechazada por la DB
- **WHEN** a second `devolucion` for the same `pago_id` is inserted bypassing the API
- **THEN** the database rejects it with a uniqueness violation (error de negocio, P4/P6)

#### Scenario: Porcentaje o monto fuera de dominio rechazado por la DB
- **WHEN** a row with `porcentaje = 0` or `porcentaje = 50`, or with `monto` greater than the payment amount, or with `monto` equal to 0 or negative is inserted bypassing the API
- **THEN** the database rejects the insertion (borde, P6)

### Requirement: Alta automática de la devolución al cancelar un turno pagado

Every `confirmado→cancelado` transition, whatever its origin (staff, patient with action token, cancel-from-mail), SHALL create in the same commit a `devolucion(pendiente)` with the percentage given by RN-SENIA-100/60 at cancellation time and an `evento_pago(devolucion_solicitada)` carrying the cancelling actor, but only when the turno has an approved payment and the quoted percentage is greater than 0.

#### Scenario: Cancelación en término crea devolución del 100 %
- **WHEN** staff cancels a `confirmado` turno with an approved payment while still inside the anticipation window (RN-ANTICIPACION)
- **THEN** in the same commit the turno is `cancelado`, a `devolucion(pendiente, porcentaje = 100, monto = monto del pago)` exists and an `evento_pago(devolucion_solicitada)` records the staff actor and timestamp (RN-SENIA-100)

#### Scenario: Cancelación fuera de término crea devolución del 60 %
- **WHEN** the patient cancels a `confirmado` turno with an approved payment outside the anticipation window but before its start
- **THEN** a `devolucion(pendiente, porcentaje = 60)` is created with `monto` equal to 60 % of the payment, rounded to cents (RN-SENIA-60)

#### Scenario: Redondeo del 60 % a centavos half-up
- **WHEN** a 60 % refund is created for an approved payment of 3333.33 ARS
- **THEN** `monto = 2000.00` (1999.998 rounded half-up to cents) and never exceeds the payment amount (borde, RN-SENIA-60)

#### Scenario: Cancelación exactamente en el límite de anticipación
- **WHEN** a turno with an approved payment is cancelled when `inicio - ahora` equals exactly `ANTICIPACION_MIN_HS`
- **THEN** the refund is created with `porcentaje = 100`, the same rule the prior quote showed (borde, RN-ANTICIPACION)

#### Scenario: Turno sin pago aprobado no genera devolución
- **WHEN** a turno is cancelled from `creado` by the system (payment rejected or TTL expired) or is cancelled with no approved payment
- **THEN** no `devolucion` and no `devolucion_solicitada` event are created (error de negocio: no se devuelve lo que no se cobró)

#### Scenario: Falla al crear la devolución revierte la cancelación
- **WHEN** persisting the `devolucion` fails during a cancellation
- **THEN** the whole transaction is rolled back and the turno remains `confirmado` holding its slot (borde, atomicidad)

### Requirement: Cotización de 0 % no genera devolución

When the refund quote is 0 % (RN-SENIA-0: a `no_show`, or a cancellation after the turno's `inicio`), the system SHALL NOT create a `devolucion`, a `devolucion_solicitada` event, a refund receipt or an `aviso_devolucion`; the payment SHALL stay `aprobado` and the turno SHALL stay `no_show` or `cancelado`, never reaching `devuelto`.

#### Scenario: No-show retiene la seña
- **WHEN** staff marks a `confirmado` turno with an approved payment as `no_show` after its `fin`
- **THEN** no `devolucion` exists for that payment and the payment stays `aprobado` (RN-SENIA-0)

#### Scenario: Un no-show no se puede cancelar para forzar devolución
- **WHEN** staff or the patient tries to cancel a turno already marked `no_show`
- **THEN** the system responds 422 (transition not allowed) and no `devolucion` is created (error de negocio, RN-ESTADOS)

#### Scenario: Cancelación con cotización 0 % no genera devolución
- **WHEN** a `confirmado` turno with an approved payment is cancelled after its `inicio` (quote 0 %)
- **THEN** the turno becomes `cancelado` with its history row and frees its slot, but no `devolucion`, no `devolucion_solicitada` event, no refund receipt and no `aviso_devolucion` exist; the payment stays `aprobado`, the turno stays `cancelado` (never `devuelto`) and the cancel response has `devolucion = null` (borde, RN-SENIA-0)

### Requirement: Bandeja lista y detalla devoluciones con alcance por rol

Staff SHALL list refunds (filterable by `estado`) and read a refund's detail through authenticated endpoints. A dentist SHALL only see refunds of their own turnos, scope enforced in the backend query (P8); recepcionista and admin SHALL see all. Patients and anonymous callers SHALL be denied. Every response SHALL include the mark "(simulado)" when `PAGO_MODO=simulado`.

#### Scenario: Recepcionista ve todas las devoluciones
- **WHEN** a recepcionista lists refunds with `estado=pendiente`
- **THEN** the response contains the pending refunds of every dentist and each item carries `marca = "(simulado)"`

#### Scenario: Odontólogo no accede a devoluciones ajenas
- **WHEN** dentist A requests the detail of a refund that belongs to a turno of dentist B
- **THEN** the system responds 403 and returns no data of that refund (error de negocio, P8)

#### Scenario: Sin JWT o con token de paciente se deniega
- **WHEN** the bandeja is called without a bearer token or with a patient mail-action token
- **THEN** the system responds 401 (no JWT) or 403 (patient) and lists nothing (borde, P12)

### Requirement: Acciones de bandeja restringidas al alcance del rol

Approve, reject and execute SHALL apply the same backend scope as reading: a dentist SHALL only act on refunds of their own turnos, recepcionista and admin on all; any out-of-scope attempt SHALL be denied before any state change, event or provider call (P8).

#### Scenario: Recepcionista aprueba la devolución de cualquier profesional
- **WHEN** a recepcionista approves a `pendiente` refund of a turno of dentist B restating its `monto`
- **THEN** the refund becomes `aprobada` with the recepcionista as approver

#### Scenario: Odontólogo no aprueba, rechaza ni ejecuta devoluciones ajenas
- **WHEN** dentist A sends approve, reject or execute for a refund of a turno of dentist B
- **THEN** the system responds 403, the refund is unchanged, no `evento_pago` is written and the payment provider is not invoked (error de negocio, P8)

#### Scenario: Odontólogo sin odontologo_id en el token es denegado
- **WHEN** a token with rol `odontologo` but without `odontologo_id` calls any bandeja action
- **THEN** the system responds 403 and changes nothing (borde, P8)

### Requirement: Aprobación manual con confirmación del monto

Every refund, including the 60 % ones, SHALL require manual approval in the bandeja; the system SHALL NOT auto-approve (Q4 default). Approving SHALL require the caller to restate the amount, which MUST equal the computed `monto`; it SHALL record approver, timestamp and amount and append `evento_pago(devolucion_aprobada)`. Only `pendiente` refunds SHALL be approvable.

#### Scenario: Aprobación feliz registra actor, fecha y monto
- **WHEN** an authorised staff member approves a `pendiente` refund restating its exact `monto`
- **THEN** the refund becomes `aprobada` with `aprobada_por` and `aprobada_at` set, and an `evento_pago(devolucion_aprobada)` stores actor, timestamp and amount (RN-BANDEJA)

#### Scenario: Monto distinto al calculado es rechazado
- **WHEN** the approval restates an amount different from the computed `monto`
- **THEN** the system responds 422 `MONTO_NO_COINCIDE` and the refund stays `pendiente` with no event written (error de negocio)

#### Scenario: Aprobar una devolución ya resuelta es inválido
- **WHEN** staff tries to approve an `aprobada`, `rechazada` or `ejecutada` refund
- **THEN** the system responds 409 `TRANSICION_DEVOLUCION_INVALIDA` and writes no event (borde)

#### Scenario: Una devolución del 60 % nunca se aprueba sola
- **WHEN** a 60 % refund is created and no staff action happens
- **THEN** it remains `pendiente` indefinitely; no automatic approval or execution occurs (borde, Q4)

### Requirement: Rechazo con motivo obligatorio

Staff SHALL be able to reject a `pendiente` refund giving a non-empty reason; the system SHALL record who rejected and when, append `evento_pago(devolucion_rechazada)`, and leave the turno `cancelado` and the payment `aprobado`. A rejected refund is terminal.

#### Scenario: Rechazo feliz
- **WHEN** an authorised staff member rejects a `pendiente` refund with motivo "pago duplicado verificado"
- **THEN** the refund becomes `rechazada` with actor and timestamp, an `evento_pago(devolucion_rechazada)` is appended and the turno stays `cancelado`

#### Scenario: Rechazo sin motivo es inválido
- **WHEN** a rejection is sent with an empty or missing motivo
- **THEN** the system responds 422 and the refund stays `pendiente` (error de negocio)

#### Scenario: No se rechaza una devolución ya resuelta
- **WHEN** staff tries to reject an `aprobada`, `ejecutada` or `rechazada` refund
- **THEN** the system responds 409 `TRANSICION_DEVOLUCION_INVALIDA` and nothing changes (borde)

### Requirement: Ciclo de estados de la devolución cerrado en app y DB

Refund states SHALL only move `pendiente→aprobada`, `pendiente→rechazada` and `aprobada→ejecutada`. Any other move SHALL be rejected by the application (409) and by the database itself when attempted directly (P6, P9). `ejecutada` SHALL require a non-null `mp_refund_id`.

#### Scenario: Recorrido válido completo
- **WHEN** a refund goes `pendiente→aprobada→ejecutada` through the bandeja
- **THEN** each move is accepted and the refund keeps approver, executor and their timestamps

#### Scenario: Ejecutar sin aprobar es rechazado
- **WHEN** staff tries to execute a `pendiente` refund
- **THEN** the system responds 409 `TRANSICION_DEVOLUCION_INVALIDA` and the payment provider is not invoked (error de negocio)

#### Scenario: La DB impide retroceder una devolución ejecutada
- **WHEN** a direct SQL update tries to move an `ejecutada` refund back to `pendiente` or to set `estado = ejecutada` with null `mp_refund_id`
- **THEN** the database rejects the statement (borde, P6)

### Requirement: Ejecución idempotente sin movimiento de dinero en modo simulado

Executing an `aprobada` refund SHALL record the requesting staff member and time, then go through the payment provider port with the refund's `idempotency_key`. In `PAGO_MODO=simulado` the provider SHALL move no money, return a synthetic `mp_refund_id` `sim_refund_<uuid>` stable for that key, and deliver a signed refund event to the payments webhook handler, the only path that marks the refund `ejecutada` (P4, P10).

#### Scenario: Ejecución feliz en modo simulado
- **WHEN** staff executes an `aprobada` refund of 6000.00 with `PAGO_MODO=simulado`
- **THEN** the refund becomes `ejecutada` with `mp_refund_id` starting with `sim_refund_`, `ejecutada_por` and `ejecutada_at` identify the staff member and time, an `evento_pago(devolucion_ejecutada)` is appended with actor `sistema` and the requesting staff and amount in its payload, the payment becomes `reembolsado_parcial` and the response carries `marca = "(simulado)"` (RN-BANDEJA)

#### Scenario: Reintento de ejecución no duplica la devolución
- **WHEN** the execute call is repeated for the same refund, or retried after a failure that happened after the provider answered
- **THEN** the system first checks the stored `mp_refund_id` and the provider status for the same `idempotency_key`, returns the same `mp_refund_id`, and writes no second `devolucion_ejecutada` event nor a second transition (P4)

#### Scenario: Ejecuciones concurrentes producen una sola ejecución
- **WHEN** two staff members execute the same `aprobada` refund at the same time
- **THEN** exactly one execution is recorded; the other request receives the same result or 409, never a second refund (borde)

#### Scenario: Proveedor no disponible deja la devolución aprobada
- **WHEN** `PAGO_MODO=mercadopago` (not built in v1) or the provider fails before answering
- **THEN** the system responds 503 `PROVEEDOR_NO_DISPONIBLE`, the refund stays `aprobada` and it never falls back to the simulated provider (borde, P13/P15)

### Requirement: Devolución total o parcial ajusta el estado del pago

When a refund is executed, the payment SHALL become `reembolsado_total` if the refunded amount equals the payment amount and `reembolsado_parcial` otherwise, in the same transaction that marks the refund `ejecutada`.

#### Scenario: Devolución del 100 % marca reembolso total
- **WHEN** a 100 % refund is executed
- **THEN** the payment becomes `reembolsado_total`

#### Scenario: Devolución del 60 % marca reembolso parcial
- **WHEN** a 60 % refund is executed
- **THEN** the payment becomes `reembolsado_parcial` and its original `monto` is unchanged (borde)

#### Scenario: Devolución rechazada no altera el pago
- **WHEN** a refund is rejected
- **THEN** the payment stays `aprobado` and no reimbursement state is set (error de negocio)

### Requirement: Turno cancelado pasa a devuelto tras la ejecución

After a refund is executed, its turno SHALL transition `cancelado→devuelto` with actor `sistema` and a history row with date, in the same transaction (RN-ESTADOS, P9). No other path SHALL move a turno to `devuelto`.

#### Scenario: Ejecución cierra el turno en devuelto
- **WHEN** a refund is executed for a `cancelado` turno
- **THEN** the turno becomes `devuelto` and `turno_historial` has a row `cancelado→devuelto` with actor `sistema` and timestamp

#### Scenario: Staff no puede marcar devuelto a mano
- **WHEN** a staff member requests the transition `cancelado→devuelto` directly
- **THEN** the system responds 403 and the turno stays `cancelado` (error de negocio)

#### Scenario: Turno reprogramado se devuelve sobre el turno cancelado
- **WHEN** a turno that inherited its payment through rescheduling is cancelled and its refund executed
- **THEN** the `devolucion` points to the cancelled (new) turno and the shared payment, and only that turno becomes `devuelto`; the original `reprogramado` turno is untouched (borde, F3)

### Requirement: Aviso de devolución al paciente marcado como simulado

When a refund reaches `ejecutada` or `rechazada`, the system SHALL enqueue exactly one `aviso_devolucion` mail for the patient in the same transaction, stating percentage, amount and outcome. With `PAGO_MODO=simulado` the mail SHALL carry the mark "(simulado)" and SHALL NOT promise a real refund.

#### Scenario: Ejecución encola el aviso con el recibo
- **WHEN** a refund is executed with `PAGO_MODO=simulado`
- **THEN** one `aviso_devolucion` is enqueued whose rendered text contains the amount, "(simulado)" and the receipt attached as PDF

#### Scenario: Rechazo encola el aviso sin recibo
- **WHEN** a refund is rejected
- **THEN** one `aviso_devolucion` is enqueued stating that the refund was not granted, without attachment (error de negocio)

#### Scenario: Reintentos de ejecución no duplican el aviso
- **WHEN** the execution of the same refund is retried
- **THEN** there is still a single `aviso_devolucion` record for that turno (borde, idempotencia)

### Requirement: Trazabilidad navegable turno, pago, devolución y comprobante

Staff SHALL get, for a turno, the linked payment, refund and receipts, plus the ordered `evento_pago` and `turno_historial` entries with actor and date, under the same role scope as the bandeja (P8). History and payment events SHALL remain append-only (P9).

#### Scenario: Trazabilidad completa de un turno devuelto
- **WHEN** a recepcionista requests the traceability of a `devuelto` turno
- **THEN** the response links turno, payment, refund and both receipts, and lists events `creado`, `webhook_recibido`, `devolucion_solicitada`, `devolucion_aprobada`, `devolucion_ejecutada` in order with actor and date

#### Scenario: Odontólogo no navega la trazabilidad de turnos ajenos
- **WHEN** dentist A requests the traceability of a turno of dentist B
- **THEN** the system responds 403 (error de negocio, P8)

#### Scenario: Turno sin pago muestra la cadena vacía
- **WHEN** traceability is requested for a turno that never had a payment
- **THEN** the response contains the turno history and explicit empty payment, refund and receipt sections (borde)

### Requirement: Alertas de conciliación visibles en la bandeja

The bandeja SHALL expose the reconciliation alerts produced by the reconciliation job, under the same role scope, with the mark "(simulado)" in simulated mode.

#### Scenario: Alerta de discrepancia aparece en la bandeja
- **WHEN** the reconciliation job records a discrepancy for a payment of dentist A
- **THEN** a recepcionista and dentist A see that alert in the bandeja, and dentist B does not (P8)

#### Scenario: Paciente o anónimo no ve alertas
- **WHEN** the alert list is requested without a staff bearer token
- **THEN** the system responds 401/403 and returns no alert (error de negocio, P8/P12)

#### Scenario: Sin discrepancias no hay alertas
- **WHEN** the reconciliation job finds every payment consistent
- **THEN** the bandeja alert list is empty (borde)
