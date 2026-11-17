# frontend-reserva-publica Specification

## Purpose

Provee la interfaz pública en React + TypeScript estricto para que un paciente (con datos ficticios en pruebas) reserve turnos en 3–4 pasos con reconocimiento por DNI y consentimiento bloqueante, pague la seña mediante el checkout simulado (`PAGO_MODO=simulado`, D14), consulte precios/trial (`D11`) y ejecute confirmaciones, cancelaciones, reprogramaciones o consultas acotadas de sus turnos sin exponer datos de terceros.

## Requirements

### Requirement: Flujo público de reserva en 3–4 pasos con DNI y consentimiento bloqueante

La SPA SHALL exponer en `/reservar` (alias `/reserva`) un flujo secuencial de 4 pasos: datos del paciente (normalizando DNI, reconociendo datos existentes si aplica según A2 y exigiendo `consentimiento_datos = true`), selección de profesional con monto de turno y seña visibles, selección de fecha/slot desde `GET /api/disponibilidad`, y confirmación enviando `POST /api/reservas` con header `Idempotency-Key` único.

#### Scenario: Funcionamiento esperado — reserva feliz completa con checkout simulado aprobado
- **WHEN** un paciente con DNI ficticio válido y `consentimiento_datos = true` selecciona profesional, elige un slot libre futuro, visualiza monto del turno y seña con marca `"(simulado)"`, confirma creando turno en `creado` + pago `pendiente` y aprueba en `/checkout-simulado` con `checkout_token` válido
- **THEN** el adaptador emite el evento firmado a `POST /api/webhooks/mercadopago` (`actor = sistema`), el turno queda `confirmado` y la SPA muestra la confirmación inmediata sin haber confirmado el pago desde código cliente (P10)

#### Scenario: Error de negocio — consentimiento faltante o slot ocupado en concurrencia
- **WHEN** el paciente intenta avanzar sin otorgar consentimiento (`consentimiento_datos = false`) o intenta confirmar un slot tomado concurrentemente (`409 SLOT_OCUPADO` o `422 CONSENTIMIENTO_REQUERIDO`)
- **THEN** la SPA impide persistir o informa el error de dominio claramente sin bloquear al usuario, y le permite aceptar el consentimiento o elegir otro slot disponible en el mismo flujo (RN-CONSENTIMIENTO / RN-DOBLE / RN-SOLAPE)

### Requirement: Pantalla de Checkout simulado con marca visible y token de un solo uso

Cuando `PAGO_MODO=simulado` (D14), la SPA SHALL exponer `/checkout-simulado` leyendo `pago_id` y `token` (`checkout_token`) desde query params, mostrando un banner destacado con la marca `"(simulado)"` y la leyenda `"SIMULADO — sin valor fiscal ni movimiento de dinero"`, ejecutando únicamente `POST /api/pagos/{pago_id}/simular` para Aprobar, Rechazar o Expirar sin mutar estados localmente (P10/P15).

#### Scenario: Error de negocio — rechazo o expiración en checkout simulado libera el slot
- **WHEN** el usuario selecciona Rechazar o Expirar en `/checkout-simulado` o expira la pre-reserva TTL (`RESERVA_TTL_MIN`, 15 min) sin pago aprobado
- **THEN** el webhook del backend pasa el turno a `cancelado` (actor `sistema`), el slot vuelve a aparecer disponible en `GET /api/disponibilidad` y la SPA ofrece iniciar una nueva selección sin bloquear al usuario (RN-LIBERACION / A5)

#### Scenario: Caso borde — checkout_token reutilizado o expirado es rechazado
- **WHEN** el usuario recarga o intenta reenviar un `checkout_token` ya consumido o vencido en `/checkout-simulado`
- **THEN** el backend rechaza con `403`/`422` y la SPA muestra un aviso amigable indicando que el enlace de pago simulado ya fue utilizado o expiró, sin duplicar eventos (P12)

### Requirement: Páginas públicas de acción por mail y consulta acotada /mis-turnos

La SPA SHALL exponer `/mail/confirmar`, `/mail/cancelar` y `/mis-turnos` consumiendo `token` (y `dni` en `/mis-turnos`) mediante `useSearchParams`; `/mis-turnos` SHALL exigir ambos parámetros `dni` y `token` y NEVER permitir consultar solo por DNI (P12).

#### Scenario: Caso borde — acceso a /mis-turnos con DNI solo o token inválido
- **WHEN** un visitante intenta consultar `/mis-turnos` enviando únicamente `dni` sin `token`, o con un `token` expirado/de otro paciente
- **THEN** la SPA no realiza ni muestra turnos de terceros, refleja el rechazo (`401`/`403`) y solicita un enlace válido enviado por correo (P12)

#### Scenario: Cancelación o reprogramación desde /mis-turnos o mail muestra seña antes de confirmar
- **WHEN** el paciente inicia cancelación desde `/mail/cancelar` o `/mis-turnos` o reprograma un turno `confirmado`
- **THEN** la SPA consulta y muestra la cotización aplicable (`100 %` en término, `60 %` fuera de término, `0 %` no-show) antes de confirmar la cancelación (RN-SENIA-PAGO / B2) y, al reprogramar a un slot válido, advierte que en MVP se conserva la seña original (Q3)

### Requirement: Vista y endpoint público de precios y trial sin datos de pacientes

La SPA SHALL exponer la vista `/precios` (D11) consumiendo el endpoint público `GET /api/precios` (incluido en `PUBLIC_ROUTES`, con rate-limit y schema `extra='forbid'` P2) mostrando aranceles por profesional, seña orientativa `"(simulado)"` y condiciones de trial sin exponer datos clínicos ni agendas de pacientes.

#### Scenario: Consulta pública de precios muestra aranceles y trial sin requerir login
- **WHEN** un visitante anónimo navega a `/precios`
- **THEN** la SPA obtiene de `GET /api/precios` los montos configurados por profesional activo y la información de trial sin exigir JWT y sin incluir ningún dato de pacientes (D11 / P12)

### Requirement: Tipado TypeScript estricto y manejo recuperable de errores y rate-limit

Todo nuevo componente, página y cliente HTTP de `C-10` SHALL cumplir TypeScript estricto sin `any` (`P1`), nombres de componentes en `PascalCase`, y manejo recuperable de respuestas `429 Too Many Requests`, `404` y errores de red.

#### Scenario: Ráfaga 429 en endpoints públicos no rompe el estado de la SPA
- **WHEN** `GET /api/disponibilidad`, `POST /api/reservas` o `/api/mail/*` responde HTTP `429`
- **THEN** la SPA conserva los datos ingresados por el usuario, muestra un aviso claro de espera y habilita reintentar sin errores de runtime ni uso de `any` (P1)
