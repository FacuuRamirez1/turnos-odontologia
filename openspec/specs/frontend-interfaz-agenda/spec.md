# frontend-interfaz-agenda Specification

## Purpose
Define the verifiable behavior of the operator-facing React SPA slice that connects the existing JWT, agenda and patient-record endpoints to a usable interface, without changing backend contracts.

## Requirements

### Requirement: Login de operador con access token en memoria

The system SHALL authenticate staff against `POST /api/auth/login` and SHALL keep the returned access token only in memory, never in `localStorage`, `sessionStorage` or a non-HttpOnly cookie.

#### Scenario: Login válido inicia sesión y carga identidad

- **WHEN** an operator submits a valid email and password
- **THEN** the system stores the access token in memory, calls `GET /api/auth/me`, and shows the agenda for that operator
- **AND** no token value is written to browser storage

#### Scenario: Credenciales inválidas no crean sesión

- **WHEN** the login endpoint responds 401 or 429
- **THEN** the system shows the backend `detail` message, keeps no access token and remains on the login screen

#### Scenario: Campos inválidos se validan antes de enviar

- **WHEN** the operator submits an empty email or password
- **THEN** the system shows an inline validation message and sends no request

### Requirement: Bootstrap de sesión con refresh HttpOnly

The system SHALL restore an expired in-memory session by calling `POST /api/auth/refresh` with credentials, and SHALL fall back to the anonymous state when refresh fails.

#### Scenario: Recarga con refresh válido restaura la sesión

- **WHEN** the application mounts without an in-memory access token and the refresh cookie is valid
- **THEN** the system obtains a new access token, loads `GET /api/auth/me` and renders the agenda

#### Scenario: Refresh inválido o ausente muestra login

- **WHEN** refresh responds 401 because the cookie is absent, expired or reused
- **THEN** the system clears session state and renders the login screen without exposing protected data

#### Scenario: Un 401 posterior expira la sesión de forma centralizada

- **WHEN** any authenticated request responds 401
- **THEN** the system clears the in-memory token and returns to the login screen with a session-expired message

### Requirement: Logout invalida la sesión local y remota

The system SHALL call `POST /api/auth/logout` and SHALL clear all local session state even if the remote call fails.

#### Scenario: Logout exitoso vuelve al login

- **WHEN** the operator confirms logout
- **THEN** the system sends the Bearer token to the logout endpoint, clears memory state and shows the login screen

#### Scenario: Fallo de red durante logout no deja sesión local

- **WHEN** the logout request fails because the server is unreachable
- **THEN** the system still clears the in-memory token and returns to login

### Requirement: Consulta de agenda aislada por profesional

The system SHALL query `GET /api/agenda` with a `fecha` (YYYY-MM-DD) and an `odontologo_id`, and SHALL NOT add a backend endpoint to discover professionals.

#### Scenario: Odontólogo consulta únicamente su agenda

- **WHEN** the authenticated role is `odontologo`
- **THEN** the system uses the `odontologo_id` returned by `/api/auth/me`, renders it as read-only and sends it in the agenda query

#### Scenario: Recepción o admin indican el UUID del profesional

- **WHEN** the authenticated role is `recepcionista` or `admin`
- **THEN** the system requires a valid UUID in the professional field, reflects it in the URL query string and sends it to the agenda endpoint

#### Scenario: UUID inválido no dispara la consulta

- **WHEN** the professional field does not contain a valid UUID
- **THEN** the system shows a validation message and sends no agenda request

#### Scenario: Agenda vacía se comunica sin error

- **WHEN** the agenda endpoint responds 200 with an empty list
- **THEN** the system shows an explicit empty state for the selected date and professional

#### Scenario: Error de agenda es visible y recuperable

- **WHEN** the agenda endpoint responds 403, 404 or 5xx
- **THEN** the system shows the backend `detail`, keeps the filters usable and offers a retry action

### Requirement: Render fiel del contrato `TurnoAgendaOut`

The system SHALL render only fields present in the agenda contract and SHALL format times in the operator's local timezone.

#### Scenario: Fila de agenda muestra horario, estado y canal

- **WHEN** the agenda response contains turnos
- **THEN** each row shows the local start/end time, the closed-set state (with text, not color alone) and the channel
- **AND** no patient name or clinical data is invented from the response

#### Scenario: Estado desconocido no rompe la vista

- **WHEN** a turno arrives with a state outside the known union
- **THEN** the system renders it as `desconocido` while preserving the row and its actions disabled

### Requirement: Acciones de estado permitidas

The system SHALL expose `Atendido` and `No show` actions only for `confirmado` turnos and SHALL call the existing agenda mutation endpoints.

#### Scenario: Marcar atendido actualiza la agenda

- **WHEN** the operator activates `Atendido` on a `confirmado` turno and the backend responds 200
- **THEN** the system refreshes the agenda and the open patient history and shows the new `atendido` state

#### Scenario: No show antes del fin es rechazado con mensaje

- **WHEN** the operator activates `No show` before the turno end time or the backend responds 422
- **THEN** the system does not mutate local state silently and shows the backend `detail`

#### Scenario: Acciones no disponibles para estados cerrados

- **WHEN** a turno is not `confirmado`
- **THEN** the mutation buttons are disabled or hidden and no request is sent

### Requirement: Ficha mínima e historial acotado en paralelo

The system SHALL open a patient panel by fetching `GET /api/pacientes/{id}` and `GET /api/pacientes/{id}/turnos` in parallel, and SHALL NOT persist that data.

#### Scenario: Seleccionar un turno abre la ficha y el historial

- **WHEN** the operator selects an agenda row
- **THEN** the system requests the patient record and the bounded history concurrently and shows contact, consent status and history states

#### Scenario: Ficha no autorizada no expone datos

- **WHEN** the patient endpoint responds 401, 403 or 404
- **THEN** the system shows a non-sensitive message, closes or empties the panel and renders no patient fields

#### Scenario: Cerrar la ficha descarta los datos

- **WHEN** the operator closes the panel or selects another turno
- **THEN** the previous patient data is removed from component state and is not written to browser storage

### Requirement: Errores del backend con envelope heterogéneo

The system SHALL surface backend errors from `{error, detail, path}`, `{code, detail}` and FastAPI `{detail: [...]}` shapes without crashing or showing raw HTML.

#### Scenario: Error de negocio muestra detail

- **WHEN** the backend responds with `code` and `detail`
- **THEN** the system shows the `detail` text and, when present, the code as supporting context

#### Scenario: Error no JSON usa mensaje seguro

- **WHEN** an error response body is empty or not JSON
- **THEN** the system shows a generic message including the HTTP status and logs no patient data

### Requirement: Accesibilidad y diseño operable

The system SHALL provide a keyboard-operable, AA-contrast interface with labeled controls, visible focus and announced errors.

#### Scenario: Navegación por teclado

- **WHEN** an operator navigates with Tab/Enter/Escape
- **THEN** filters, agenda rows, panel and actions are reachable and the focus indicator is visible
- **AND** Escape closes the patient panel

#### Scenario: Error anunciado a lectores de pantalla

- **WHEN** a request fails
- **THEN** the error container uses `aria-live` and exposes the message as text

#### Scenario: Estado no depende solo del color

- **WHEN** a turno state is displayed
- **THEN** the state includes a text label in addition to any color token

### Requirement: TypeScript estricto y build limpio

The system SHALL compile under the existing strict TypeScript configuration with no `any`, no unused symbols and no ESLint warnings.

#### Scenario: Gate de calidad pasa

- **WHEN** `npm run typecheck`, `npm run lint` and `npm run build` run in `frontend/`
- **THEN** all three complete with exit code 0 and the build reports no warnings or errors

#### Scenario: Sin `any` en el código fuente

- **WHEN** the frontend source is linted
- **THEN** `@typescript-eslint/no-explicit-any` reports zero violations in `frontend/src`
