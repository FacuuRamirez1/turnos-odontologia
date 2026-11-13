# Proposal — c-07-pagos-mp-checkout-webhook

## Why

La reserva de C-05 deja al turno en `creado` sin confirmar: nada cobra la seña ni conecta con un proveedor de pagos. C-07 cierra esa brecha del camino crítico (C-05 → C-07) con un proveedor de pagos simulado (`PAGO_MODO=simulado`, D14) detrás del mismo puerto/adaptador que usará MercadoPago en v2. Así el sistema valida el flujo E2E reserva→seña simulada→confirmación sin depender de credenciales reales de MP, manteniendo idempotencia y audit trail append-only (D2, P4/P9 intactos).

## What Changes

- Puerto `ProveedorPago` + adaptador `simulado` (`infra/pago_simulado`) seleccionado por `PAGO_MODO=simulado|mercadopago` (default `simulado`); `MP_ACCESS_TOKEN`/`MP_PUBLIC_KEY` opcionales (solo con `mercadopago`); `MP_WEBHOOK_SECRET` se usa también en simulado (el adaptador firma con HMAC y entrega al mismo handler del webhook) (P5).
- Modelos `Pago` (separado del turno, D13: `proveedor`, `mp_payment_id` único sintético `sim_pay_<uuid>`, `mp_preference_id` nullable, estados `pendiente|aprobado|rechazado`, `idempotency_key` única) y `EventoPago` append-only (sin UPDATE/DELETE) + migración Alembic `005` (cero `create_all`, P3). Resuelve `pago_id` sin FK + referencia circular turno↔pago con FK diferible o columna solo de un lado; valida existencia del pago al reprogramar (P9).
- `POST /reservas` crea `turno(creado)` + `pago(pendiente, proveedor='simulado')` + `evento_pago(creado)` de forma atómica y devuelve `checkout_url` + `checkout_token` de 1 uso/vida corta; respeta TTL `RESERVA_TTL_MIN` (15 min) (P10).
- Endpoint sandbox `POST /pagos/{pago_id}/simular` (Aprobar/Rechazar/Expirar): existe solo con `PAGO_MODO=simulado`, exige `checkout_token` de 1 uso, rate-limit; apagado en producción/modo `mercadopago` (P12/P15 excepción documentada). El frontend nunca confirma; el adaptador emite el evento firmado.
- `POST /webhooks/mercadopago` (mismo handler en ambos modos): valida firma `MP_WEBHOOK_SECRET` → persiste `evento_pago(webhook_recibido)` con payload crudo → idempotencia por `mp_payment_id`/`mp_refund_id` → `creado→confirmado` (aprobado, actor `sistema`) o `creado→cancelado` (rechazado/expirado, actor `sistema`) (P10).
- Escritura atómica turno+pago+evento antes de invocar al adaptador (nunca cobrar sin rastro local).
- Job diario de conciliación contra el estado del proveedor simulado (verificación de consistencia interna; discrepancias → `evento_pago(conciliado)` + alerta).
- Marca "(simulado)" en toda respuesta/UI/mail de pago cuando `PAGO_MODO=simulado`; guard de arranque/CI que impida `PAGO_MODO=simulado` o el endpoint sandbox en producción (P15).
- `settings.py` suma `PAGO_MODO` (validado `simulado|mercadopago`, default `simulado`); `MP_ACCESS_TOKEN`/`MP_PUBLIC_KEY` opcionales con validación condicional; `test_env_contract.py` se actualiza al nuevo contrato.

## Capabilities

### New Capabilities

- `pagos`: proveedor de pagos con adaptador simulado y puerto `ProveedorPago`; modelos `Pago`/`EventoPago`; `POST /reservas` crea turno+pago+evento atómicamente y devuelve `checkout_url`+`checkout_token`; endpoint sandbox `POST /pagos/{pago_id}/simular` (solo modo simulado); `POST /webhooks/mercadopago` idempotente y firmado que confirma/cancela el turno con actor `sistema`; job diario de conciliación interna; marca "(simulado)" y guard de arranque P15.

### Modified Capabilities

- `reserva-turnos-estados`: `POST /reservas` ahora crea también `pago(pendiente)` + `evento_pago(creado)` y devuelve `checkout_url`+`checkout_token`; la transición `creado→confirmado`/`creado→cancelado` es disparada por el webhook de pagos (actor `sistema`) en lugar de solo por expiración TTL. El seam `turno.pago_id` (sin FK en 003) se constriñe en la migración 005 de este change.

## Impact

- Añade: `backend/app/domain/pagos/` (modelos, servicio, puerto proveedor, adaptador simulado), `backend/app/infra/pago_simulado/`, `backend/app/api/pagos.py` (sandbox + webhook), `backend/app/api/reservas.py` (integra pago en la reserva), migración `005` (`pago` + `evento_pago`), job de conciliación en `backend/app/workers/`, guard de arranque/CI, tests webhook/sandbox/conciliación/guard.
- Modifica: `backend/app/core/settings.py` (`PAGO_MODO`, MP_* condicionales), `backend/app/infra/db/models/turno.py` (FK `pago_id` en 005), `.env.example`/`.env` (documenta `PAGO_MODO=simulado`), `backend/app/tests/test_env_contract.py` (nuevo contrato).
- No toca: auth/JWT (reutiliza `require_role()`), ficha/paciente (C-06), mails (C-09 consume el outbox `creado→confirmado` ya listo), frontend (C-10 consume `checkout_url`+`checkout_token`), tablas v2 apagadas (P13: cero escrituras en `lista_espera`, sin sobre-turnos).
