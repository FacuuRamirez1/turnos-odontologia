# reportes-exportaciones Specification

## Purpose

Permite al consultorio consultar asistencia y caja y exportar turnos, caja y auditoría en CSV/PDF, solo a roles autorizados y con el aislamiento por profesional exigido en backend.

## Requirements

### Requirement: Reporte de asistencia por estado y período

The system SHALL expose a staff-only endpoint returning counts of turnos grouped by the closed state set (`creado`, `confirmado`, `cancelado`, `reprogramado`, `atendido`, `no_show`, `devuelto`) for a period (`desde`, `hasta`), with zero for states without rows. The system SHALL NOT compute any ausentismo rate or proprietary metric (D12).

#### Scenario: Conteos por estado en el período
- **WHEN** a recepcionista requests the report for a period with 3 `atendido` and 1 `no_show` turnos
- **THEN** the response contains `atendido=3`, `no_show=1` and `0` for every other state

#### Scenario: Período inválido
- **WHEN** `desde` is later than `hasta`
- **THEN** the system responds 422 and returns no data (error de negocio)

#### Scenario: Período sin turnos
- **WHEN** the period contains no turnos
- **THEN** all seven states are present with `0` (borde)

### Requirement: Aislamiento por profesional y RBAC

The system SHALL restrict reports and exports to roles `odontologo`, `recepcionista` and `admin` via `require_role`. An `odontologo` SHALL only obtain data of their own `odontologo_id`, forced in the repository regardless of query parameters; `recepcionista`/`admin` MAY filter by any `odontologo_id` or see all.

#### Scenario: Odontólogo solo ve lo propio
- **WHEN** an odontólogo requests a report passing another professional's `odontologo_id`
- **THEN** the response contains only data of their own `odontologo_id` (aislamiento)

#### Scenario: Sin sesión o sin rol
- **WHEN** a request has no valid JWT
- **THEN** the system responds 401; a role outside the three allowed gets 403 (error de negocio)

#### Scenario: Odontólogo sin vínculo
- **WHEN** an `odontologo` identity has no `odontologo_id`
- **THEN** the system responds 403 and returns no data (borde, falla cerrado)

### Requirement: Reporte de caja conciliado con eventos de pago

The system SHALL expose a staff-only caja report for a period with total of pagos `aprobado`, total of devoluciones `ejecutada`, neto (aprobado − devuelto) and per-row detail with trazabilidad (`turno_id`, `pago_id`, `devolucion_id`). Totals SHALL equal the sum of the underlying `pago`/`devolucion` rows and be consistent with `evento_pago`. When `PAGO_MODO=simulado` the response SHALL carry `marca = "(simulado)"`.

#### Scenario: Neto de caja
- **WHEN** the period has one pago aprobado of 10000 and one devolución ejecutada of 6000
- **THEN** the report shows aprobado=10000, devuelto=6000, neto=4000

#### Scenario: Pagos no aprobados no suman
- **WHEN** the period has pagos `pendiente` or `rechazado`
- **THEN** they are excluded from totals (error de negocio)

#### Scenario: Marca simulada
- **WHEN** `PAGO_MODO=simulado`
- **THEN** the response includes `marca = "(simulado)"` and caja exports show it too (borde, P15)

### Requirement: Exportación CSV y PDF de turnos y caja

The system SHALL export turnos and caja as CSV (UTF-8, quoted fields, formula-injection safe: cells starting with `=`, `+`, `-`, `@` are prefixed with `'`) and PDF, filtered by `odontologo_id` and period. Exports SHALL contain no clinical data and no more than the fields of the on-screen report.

#### Scenario: CSV de turnos filtrado
- **WHEN** staff requests CSV of turnos for a period and professional
- **THEN** the response is `text/csv` with a header row and only matching turnos

#### Scenario: PDF de caja con marca
- **WHEN** staff requests PDF of caja with `PAGO_MODO=simulado`
- **THEN** the response is `application/pdf` and the document shows "(simulado)" visibly

#### Scenario: Celda con fórmula
- **WHEN** a field value (e.g. motivo) starts with `=`
- **THEN** the CSV cell is neutralized with a leading `'` (borde)

### Requirement: Exportación de auditoría append-only

The system SHALL export the audit trail (`turno_historial` and `evento_pago`) as CSV with actor, fecha, estado anterior/nuevo or `tipo_evento`, for a period, scoped by professional. Export SHALL be read-only and never modify those tables.

#### Scenario: Auditoría de un período
- **WHEN** staff exports audit for a period
- **THEN** each transition and payment event in the period appears once with actor and fecha

#### Scenario: Aislamiento en auditoría
- **WHEN** an odontólogo exports audit
- **THEN** only rows of their turnos/pagos appear (aislamiento)

### Requirement: Métricas de entrega de mail en reportes

The system SHALL include the six delivery-state counts of C-09 (`contar_por_estado`) in the reports payload, for the same period, without introducing new notification data.

#### Scenario: Conteos de mail con ceros
- **WHEN** no recordatorios exist in the period
- **THEN** the six keys are present with `0`

### Requirement: UI mínima de reportes

The frontend SHALL provide a reportes page with period and professional filters, a counts view and download buttons for CSV/PDF, authenticated with the in-memory access token. The UI SHALL NOT be the only access control (P8) and SHALL show the "(simulado)" banner when the API returns it.

#### Scenario: Descarga autenticada
- **WHEN** staff clicks download
- **THEN** the file is fetched with the bearer token and saved by the browser

#### Scenario: Error de API
- **WHEN** the API returns an error envelope
- **THEN** the page shows a retryable error state without losing filters
