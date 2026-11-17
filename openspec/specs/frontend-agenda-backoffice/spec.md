# frontend-agenda-backoffice Specification

## Purpose

Provee la interfaz operativa de backoffice en React + TypeScript estricto para que el personal autenticado (`odontologo`, `recepcionista`, `admin`) gestione disponibilidad/bloqueos, reservas telefónicas según su rol (`Q10`), cancelaciones y reprogramaciones con trazabilidad (`B3`), y la bandeja de devoluciones y comprobantes simulados (`C-08`, `P15`) respetando el aislamiento RBAC (`P8`).

## Requirements

### Requirement: Navegación staff protegida y cumplimiento de alcance por rol

El shell autenticado SHALL exponer navegación entre `/agenda` y `/bandeja` bajo `<ProtectedRoute />`, mantener visibilidad explícita de prohibiciones de v1/recepcionista (sin usuarios/roles, sin config de pagos/`PAGO_MODO`, sin ARCA), y ocultar/inhabilitar reserva telefónica para `odontologo` (`03 §2`, `P8`).

#### Scenario: Funcionamiento esperado — navegación entre Agenda y Bandeja para staff autenticado
- **WHEN** un usuario autenticado con rol `recepcionista`, `admin` u `odontologo` navega por `AppShell` entre `/agenda` y `/bandeja`
- **THEN** accede a ambas vistas protegidas manteniendo su token en memoria, visualiza su rol activo y nunca ve controles de usuarios, config de pagos/`PAGO_MODO` ni ARCA

#### Scenario: Error de negocio — odontólogo no puede operar reserva telefónica
- **WHEN** el rol autenticado es `odontologo`
- **THEN** la UI no habilita el formulario de reserva telefónica (`POST /api/reservas/telefonica`) e informa que corresponde únicamente a recepción/administración (P8)

### Requirement: Bandeja de devoluciones simuladas y alertas de conciliación

La ruta protegida `/bandeja` SHALL mostrar el banner `"(simulado)"`, filtrar devoluciones vía `GET /api/devoluciones?estado=`, listar alertas de `GET /api/devoluciones/alertas`, y permitir aprobar (exigiendo `monto_confirmado` manual, `Q4`), rechazar (exigiendo motivo) o ejecutar devoluciones vía servidor (`P10`/`P15`).

#### Scenario: Funcionamiento esperado — aprobar y ejecutar devolución en modo simulado
- **WHEN** un operador revisa una devolución `pendiente`, ingresa `monto_confirmado` coincidente para aprobarla y luego ejecuta `POST /api/devoluciones/{id}/ejecutar`
- **THEN** la UI refleja la devolución `ejecutada`, el `mp_refund_id` simulado, el nuevo estado de pago devuelto por backend y el banner `"(simulado)"` sin transicionar estados localmente (P10/P15)

#### Scenario: Error de negocio — monto incorrecto o rechazo sin motivo es bloqueado sin mutar estado
- **WHEN** el operador intenta aprobar con `monto_confirmado` distinto (`422 MONTO_NO_COINCIDE`) o rechazar con motivo vacío (`422`) o la API responde `403`/`409`
- **THEN** la UI conserva la devolución en su estado previo, muestra el mensaje de error claro y no inventa comprobantes ni reembolsos

#### Scenario: Caso borde — modo mercadopago no disponible en v1 retorna 503 recuperable
- **WHEN** `POST /api/devoluciones/{id}/ejecutar` responde `503 PROVEEDOR_NO_DISPONIBLE` (`P13`/`P15`)
- **THEN** la bandeja informa que el proveedor real no está habilitado en v1 sin aplicar fallback en cliente

### Requirement: Trazabilidad auditable e historial con actor y fecha

Tanto `/bandeja` como `/agenda` SHALL permitir abrir la trazabilidad completa de un turno (`GET /api/turnos/{id}/trazabilidad`) mostrando turno, pago, devolución, `comprobantes` (con descarga PDF autenticada vía `/api/comprobantes/{id}/pdf`), `eventos_pago` y `historial` cronológico con actor, fecha y motivo (`B3`, `P9`).

#### Scenario: Consulta de trazabilidad y descarga de recibo PDF simulado
- **WHEN** el operador abre la trazabilidad de un turno con pago/devolución y solicita descargar un recibo PDF
- **THEN** visualiza la cadena completa con actores y fechas (`P9`), la marca `"(simulado)"` y dispara la descarga autenticada de `application/pdf`

#### Scenario: Caso borde — acceso ajeno de odontólogo recibe 403 sin filtrar datos
- **WHEN** `GET /api/turnos/{id}/trazabilidad` o `/api/devoluciones` responde `403`
- **THEN** el panel muestra un aviso de permiso insuficiente sin renderizar datos clínicos ni montos ajenos (`P8`)

### Requirement: ABM de disponibilidad y bloqueos scopeado al profesional

Desde `/agenda`, el personal autenticado SHALL gestionar franjas semanales (`/api/staff/disponibilidad`) y bloqueos (`/api/staff/bloqueos`) sobre el `effectiveOdontologoId` activo, validando orden temporal antes de enviar y reflejando rechazos `422` por solapamiento.

#### Scenario: Alta y baja lógica de disponibilidad y bloqueos en agenda
- **WHEN** un odontólogo (su propio ID) o recepcionista (con UUID válido) crea una franja semanal o un bloqueo futuro y luego lo elimina
- **THEN** la UI actualiza las listas del profesional activo y ante `hora_fin <= hora_inicio` o `hasta <= desde` bloquea el envío sin perder los campos (`RN-SOLAPE`)

### Requirement: Reserva telefónica Q10 y cancelación o reprogramación staff en agenda

En `/agenda`, `recepcionista`/`admin` SHALL poder crear reservas telefónicas (`Q10`: `odontologo_id`, fecha/hora futura, DNI, nombre, apellido, email y `consentimiento_datos = true`, `P11`), y todo rol autorizado SHALL poder cancelar (previa cotización y motivo) o reprogramar turnos `confirmado` (aviso `Q3`, `RN-PASADO`, `RN-DOBLE`).

#### Scenario: Funcionamiento esperado — reserva telefónica con consentimiento y reprogramación Q3
- **WHEN** una recepcionista crea una reserva telefónica con DNI ficticio válido, email, fecha/hora futura y `consentimiento_datos = true`
- **THEN** envía `POST /api/reservas/telefonica` con `Idempotency-Key` y recarga la agenda; al reprogramar un turno `confirmado` advierte conservación de seña (`Q3`) y maneja `409 SLOT_OCUPADO` sin perder el motivo/datos

#### Scenario: Error de negocio — consentimiento falso o turno pasado bloquea reserva telefónica
- **WHEN** la recepcionista intenta confirmar reserva telefónica sin aceptar `consentimiento_datos` o backend responde `422 CONSENTIMIENTO_REQUERIDO` / `422 SLOT_NO_DISPONIBLE`
- **THEN** la UI bloquea o informa el error de dominio sin crear paciente ni turno (`RN-CONSENTIMIENTO` / `RN-PASADO` / `P11`)
