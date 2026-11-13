# Proposal — c-10-frontend-reserva-publica

## Why

El backend ya expone las capacidades públicas de disponibilidad (`C-04`), reserva con pre-reserva TTL, reprogramación/cancelación y `/mis-turnos` (`C-05`), pagos simulados con `checkout_url`/`checkout_token` + webhook (`C-07`) y acciones desde mail (`C-09`), mientras `frontend/src/pages/reserva/ReservaPage.tsx` sigue siendo un placeholder estático y no existen aún rutas públicas para checkout simulado, consulta de turnos propios, acciones por mail ni vista pública de precios/trial (D11). Con `C-05` y `C-07` ya archivados, `C-10` entrega la cara pública de la SPA para que un paciente complete una reserva en 3–4 pasos sin intervención telefónica.

## What Changes

- Flujo público de reserva en 3–4 pasos en `/reservar` (o `/reserva`): datos del paciente (normalización y reconocimiento por DNI existente según A2 + consentimiento explícito bloqueante RN-CONSENTIMIENTO) → selección de profesional y visualización previa de monto del turno y seña → selección de fecha/horario desde `GET /api/disponibilidad` → resumen pre-confirmación y envío a `POST /api/reservas` con `Idempotency-Key`.
- Pantalla pública `/checkout-simulado` (modo MVP `PAGO_MODO=simulado`, D14): lee `checkout_token` de la URL, muestra claramente la marca visible `"(simulado)"` y la leyenda de entorno sin dinero real, y dispara acciones Aprobar / Rechazar / Expirar contra `POST /api/pagos/{pago_id}/simular` (el frontend jamás confirma el turno directamente; espera confirmación/rechazo originado por el webhook server-to-server, P10).
- Vistas públicas de autogestión y acción por mail:
  - `/mail/confirmar` y `/mail/cancelar`: consumen `token` desde query string vía `useSearchParams` (React Router v6), muestran el resultado o la cotización de devolución (100 % / 60 % / 0 %) antes de confirmar cancelación y manejan tokens expirados/consumidos o HTTP 429 sin bloquear al usuario.
  - `/mis-turnos`: exige ambos parámetros `dni` + `token` (nunca consulta por DNI solo, P12), muestra solo turnos propios con botones de cancelar (cotización previa RN-SENIA-*) y reprogramar (advirtiendo que se mantiene la seña original ante diferencia de monto según Q3).
- Vista pública de precios y trial `/precios` (D11, `03 §3.6`), consumiendo `GET /api/precios` (añadido en backend dentro de la lista cerrada `PUBLIC_ROUTES`, sin datos de pacientes) más exposición mínima de `pago_id` en `ReservaOut`/`checkout_url` para enlazar el sandbox sin romper C-07.

## Capabilities

### New Capabilities

- `frontend-reserva-publica`: SPA pública del paciente para reserva en 3–4 pasos con reconocimiento por DNI y consentimiento bloqueante, pantalla de checkout simulado (`PAGO_MODO=simulado`, marca `"(simulado)"`, `checkout_token` de un uso), páginas públicas `/mail/confirmar`, `/mail/cancelar`, `/mis-turnos` (con `dni` + `token`) y `/precios` (D11), cumpliendo React + TypeScript estricto (`P1`), rutas cerradas (`P12`) y sin confirmación de pago desde cliente (`P10`).

### Modified Capabilities

<!-- Ninguna capability existente cambia reglas de dominio: C-10 consume C-04/C-05/C-07/C-09 y materializa el endpoint GET /precios ya reservado en PUBLIC_ROUTES (03 §3.6). -->

## Impact

- **Frontend (`frontend/src/`)**: nuevas páginas y componentes bajo `pages/reserva/`, `pages/checkout/`, `pages/mail/`, `pages/mis-turnos/`, `pages/precios/`, clientes HTTP en `api/` (`disponibilidad.ts`, `reservas.ts`, `pagos.ts`, `precios.ts`), tipos estrictos sin `any` (`P1`) en `api/types.ts`, y rutas públicas en `App.tsx` preservando las rutas protegidas de `C-07F`.
- **Backend (`backend/app/`)**: nuevo router público `GET /api/precios` (D11, rate-limit, `extra='forbid'` P2, listado en `PUBLIC_ROUTES`) y campo opcional `pago_id` en `ReservaOut` / query `?pago_id=&token=` en `PagoSimuladoAdapter.generar_checkout` para que el checkout simulado llame a `POST /api/pagos/{pago_id}/simular`.
- **Dependencias**: requiere `C-05` (`[x]` archivado) y `C-07` (`[x]` archivado). No toca BD/migraciones (`C-08` pendiente, `WHATSAPP_ENABLED=false` y `ARCA_ENABLED=false` siguen en `false`, P13).
