# ficha-paciente-consentimiento

## Purpose

Da al staff una ficha mínima de paciente con consentimiento bloqueante, reconocimiento por DNI para precarga en reserva e historial de turnos acotado sin datos clínicos, con visibilidad estricta por rol.

## Requirements

### Requirement: CRUD ficha mínima con gate de consentimiento

The system SHALL expose staff-only CRUD for the minimal patient record (`dni`, `nombre`, `apellido`, `email`, `telefono`, `consentimiento_datos` + `consentimiento_fecha`) and SHALL persist nothing unless consent is true with a timestamp.

#### Scenario: Alta manual con consentimiento persiste

- **WHEN** staff posts a new patient with valid fields and `consentimiento_datos = true` plus timestamp to `POST /pacientes`
- **THEN** the system responds 201 with the created record including its id

#### Scenario: Alta manual sin consentimiento es rechazada sin persistir

- **WHEN** staff posts a new patient with `consentimiento_datos = false` or missing timestamp to `POST /pacientes`
- **THEN** the system responds 422 with code `CONSENTIMIENTO_REQUERIDO` and no row is created

#### Scenario: Schemas rechazan campos no declarados

- **WHEN** any paciente request includes an undeclared field
- **THEN** the system responds 422 and persists nothing (P2 `extra='forbid'`)

### Requirement: Formato y unicidad de DNI

The system SHALL accept DNI as 7–8 digits (normalized: strip spaces/dots) and SHALL reject duplicates with a uniqueness violation.

#### Scenario: DNI duplicado es rechazado

- **WHEN** a second patient is created with an already-registered DNI (after normalization)
- **THEN** the system responds 409 with a uniqueness error and no second row is created

#### Scenario: DNI con formato inválido es rechazado

- **WHEN** a patient is created with a DNI containing letters or wrong length
- **THEN** the system responds 422 with a validation error

#### Scenario: DNI con puntos o espacios se normaliza

- **WHEN** a patient is created with DNI `30.123.456` or ` 30123456 `
- **THEN** the system stores `30123456` and later lookups match it

### Requirement: Reconocimiento por DNI con precarga (A2)

The system SHALL expose `GET /pacientes?dni=` (staff JWT only) returning the minimal record for an exact normalized-DNI match, or a uniform empty 200 when there is no match.

#### Scenario: DNI existente precarga la ficha

- **WHEN** staff calls `GET /pacientes?dni=30123456` for a registered active patient
- **THEN** the system responds 200 with that patient's minimal record for reservation preload

#### Scenario: DNI inexistente devuelve vacío uniforme

- **WHEN** staff calls `GET /pacientes?dni=` with a well-formed but unregistered DNI
- **THEN** the system responds 200 with an empty result (no 404 distinction)

#### Scenario: Búsqueda exige JWT staff

- **WHEN** `GET /pacientes?dni=` is called without a valid staff token
- **THEN** the system responds 401

### Requirement: Creación implícita desde reserva exige consentimiento

The system SHALL require recorded consent for any patient row created implicitly by `POST /reservas`, failing the whole reservation with 422 `CONSENTIMIENTO_REQUERIDO` when consent is absent.

#### Scenario: Reserva sin consentimiento falla sin persistir nada

- **WHEN** `POST /reservas` carries patient data without consent
- **THEN** the system responds 422 `CONSENTIMIENTO_REQUERIDO` and creates neither patient nor turno (contract for C-05)

#### Scenario: Reserva con consentimiento crea paciente y continúa

- **WHEN** `POST /reservas` carries patient data with consent true plus timestamp
- **THEN** the patient row is created (or reused by DNI) and the reservation flow continues

### Requirement: Historial de turnos acotado sin nada clínico

The system SHALL expose `GET /pacientes/{id}/turnos` returning past and future turnos limited to `{turno_id, odontologo_id, inicio, fin, estado}` with zero clinical fields.

#### Scenario: Historial devuelve ventana acotada sin campos clínicos

- **WHEN** staff calls `GET /pacientes/{id}/turnos` for a patient with past and future turnos
- **THEN** the system responds 200 with both windows and the response schema contains no clinical field

#### Scenario: Paciente sin turnos devuelve lista vacía

- **WHEN** staff calls the historial endpoint for a patient with no turnos
- **THEN** the system responds 200 with an empty list

### Requirement: Visibilidad acotada por rol (matriz 03 §2)

The system SHALL authorize paciente endpoints so odontologo and recepcionista|admin see fichas (contacto + historial), while unauthenticated callers see nothing except their own record via mail-action token.

#### Scenario: Odontólogo y recepcionista ven fichas

- **WHEN** an odontologo or recepcionista token calls paciente read endpoints
- **THEN** the system authorizes contact plus bounded history

#### Scenario: Llamada anónima sin token es rechazada

- **WHEN** any `/pacientes` endpoint is called with no token and no mail-action token
- **THEN** the system responds 401 and exposes no patient data

#### Scenario: Prohibiciones de recepcionista siguen negadas

- **WHEN** a recepcionista token attempts user/role admin, MP config, audit deletion or ARCA vouchers through paciente endpoints
- **THEN** the system responds 403 (P8, matriz 03 §2 intacta)

### Requirement: Paciente solo ve la propia vía token mail

The system SHALL let a patient see only their own minimal record and bounded history through the C-03 mail-action token seam, never via DNI-only lookup or patient listing.

#### Scenario: Token mail válido ve solo ficha propia

- **WHEN** a valid unused mail-action token for patient P is presented to the self-service read
- **THEN** the system returns only P's record and history

#### Scenario: DNI solo sin token no autoriza

- **WHEN** the self-service read is called with only a DNI and no token
- **THEN** the system responds 401 (P12: nunca DNI solo)

#### Scenario: Token mail de otro paciente no cruza datos

- **WHEN** a mail-action token for patient P is used to request patient Q's record
- **THEN** the system responds 403 and exposes nothing of Q

### Requirement: Datos ficticios y sin rutas públicas nuevas

The system SHALL add no new public (JWT-less) route in this change and SHALL use only fictitious DNIs in seeds and tests.

#### Scenario: Ráfaga staff es limitada

- **WHEN** paciente endpoints receive a burst above their rate-limit threshold
- **THEN** the system responds 429

#### Scenario: Seed y tests usan DNI ficticios

- **WHEN** seeds or tests create patients
- **THEN** every DNI matches the fictitious-dev pattern and no real patient data exists (P11)
