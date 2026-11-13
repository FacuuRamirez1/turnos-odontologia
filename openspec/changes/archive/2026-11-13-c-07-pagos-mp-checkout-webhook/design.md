# Design — c-07-pagos-mp-checkout-webhook

## Context

C-05 ya creó `turno` con `pago_id` UUID nullable **sin FK** (seam documentado, design D6 de C-05) y `reprogramado_de_id` para trazabilidad F3; la migración `003` dejó esa columna sin constreñir a la espera de C-07 (CHANGES.md renumeración: C-07 → `005`, head actual `004_recordatorio_mail`). `backend/app/domain/pagos/` es un paquete esqueleto sin lógica; `backend/app/infra/mp/` también es esqueleto. `settings.py` no tiene `PAGO_MODO` (debe añadirse en C-07, D14). `POST /reservas` hoy crea solo `turno(creado)` y devuelve `ReservaOut` sin `checkout_url` ni `checkout_token`. La máquina de estados `transition()` ya admite `creado→confirmado` y `creado→cancelado` con actor `sistema`, y el outbox de C-09 encola el mail de confirmación en `creado→confirmado` dentro de la misma transacción. No hay `create_all` en runtime; todo va por Alembic (P3).

## Goals / Non-Goals

**Goals:**
- Puerto `ProveedorPago` + adaptador `simulado` seleccionable por `PAGO_MODO`, listo para cambiar a `mercadopago` en v2 solo cambiando el adaptador.
- `Pago` y `EventoPago` append-only con idempotencia (`UNIQUE`) en DB, no solo en app (P4/P6/P9).
- `POST /reservas` escribe atómicamente turno+pago+evento antes de invocar al adaptador (nunca cobrar sin rastro local, P10).
- Confirmación/cancelación del turno solo server-to-server vía `POST /webhooks/mercadopago` (mismo handler en ambos modos); el frontend nunca confirma (P10).
- Sandbox `POST /pagos/{pago_id}/simular` solo en modo simulado, con `checkout_token` de 1 uso y rate-limit; apagado en producción/mercadopago (P12/P15).
- Guard de arranque/CI que impida `PAGO_MODO=simulado` o sandbox en producción (P15).
- Migración `005` versionada (P3) que resuelve `pago_id` sin FK + referencia circular turno↔pago.

**Non-Goals:**
- MercadoPago real (checkout, preferencias, credenciales de producción) — queda diseñado, no construido en v1 (D14/P13).
- Devoluciones, comprobantes, bandeja, conciliación contra API MP real — son C-08; aquí solo el job de conciliación interna contra el proveedor simulado.
- Frontend (pantalla Checkout simulado) — es C-10; aquí solo se proveen `checkout_url`+`checkout_token`.
- Mails de confirmación/cancelación — C-09 ya preparó el outbox; C-07 solo dispara `creado→confirmado` (actor sistema) que lo consume.

## Decisions

### 1. Modelo `Pago` separado del turno + `EventoPago` append-only (D13, P9)

`pago`: `id, turno_id, odontologo_id, monto, moneda='ARS', proveedor (simulado|mercadopago default simulado), mp_payment_id UNIQUE (sim_pay_<uuid> si simulado), mp_preference_id nullable, estado (pendiente|aprobado|rechazado|...), idempotency_key UNIQUE, created_at`. `evento_pago`: `id, pago_id, tipo_evento, payload_json, actor, created_at`, sin UPDATE/DELETE (revoke al rol app, P9). Alternativa descartada: embebe pago en turno → imposibilitaría conciliación con proveedor y comprobante separado (D13).

### 2. Referencia circular turno↔pago: columna solo del lado de pago + FK `pago.turno_id`

En `003`, `turno.pago_id` existe sin FK (seam). En `005` se añade `pago.turno_id` con FK RESTRICT → `turno.id` (columna solo de un lado, rompe el círculo) y se mantiene `turno.pago_id` como columna espejo para trazabilidad agenda (se constriñe o se documenta como sin FK para evitar el círculo; se valida existencia del pago al reprogramar en la app). Alternativa descartada: FK diferible bidireccional → complejidad en migraciones y pruebas; una sola dirección basta para las reglas v1.

### 3. Adaptador simulado firma con HMAC (`MP_WEBHOOK_SECRET`) y entrega al mismo handler del webhook

El adaptador `simulado` no expone checkout externo: genera `checkout_url` apuntando a la pantalla "Checkout simulado" y `checkout_token` (1 uso, vida corta, almacenado con expiración en Redis/DB). Al llamar al sandbox, el adaptador emite un evento firmado con HMAC-SHA256 sobre `MP_WEBHOOK_SECRET` y lo entrega a `POST /webhooks/mercadopago`, que valida la firma, persiste `evento_pago(webhook_recibido)` con payload crudo, aplica idempotencia por `mp_payment_id`/`mp_refund_id` y dispara `creado→confirmado` o `creado→cancelado` con actor `sistema`. Alternativa descartada: endpoint webhook distinto por modo → rompe P10 (mismo handler) y duplica lógica de firma.

### 4. Escritura atómica turno+pago+evento antes del adaptador (UnitOfWork C-02)

`POST /reservas` abre una `UnitOfWork`, inserta `turno(creado)`, `pago(pendiente)`, `evento_pago(creado)` y commit; solo entonces invoca al adaptador para generar `checkout_url`/`checkout_token`. Si la transacción falla, no se toca el adaptador (P10). El `checkout_token` se valida en el sandbox como 1 uso y se invalida tras consumo (P12).

### 5. `POST /reservas` devuelve `checkout_url` + `checkout_token` y respeta TTL

El response de reserva se extiende con `checkout_url` y `checkout_token`. El TTL `RESERVA_TTL_MIN` (15 min) ya existe (C-01/C-05); el job de expiración de C-05 sigue formalizando `creado` vencido → `cancelado` (actor sistema), y el webhook puede confirmar antes del TTL (`creado→confirmado` gana sobre expiración por guarda de estado, idempotente).

### 6. Guard de arranque/CI (P15)

Al iniciar la aplicación, si `ENVIRONMENT=production` y `PAGO_MODO=simulado` (o se detecta el endpoint sandbox expuesto), se lanza `ValueError` y se impide el arranque. CI incluye un job que falla si `PAGO_MODO=simulado` con `ENVIRONMENT=production`. `MP_ACCESS_TOKEN`/`MP_PUBLIC_KEY` opcionales con validación condicional: requeridas solo si `PAGO_MODO=mercadopago` (P5).

### 7. Migración `005` (down_revision `004_recordatorio_mail`)

Crea tablas `pago` y `evento_pago` con constraints (`UNIQUE mp_payment_id`, `UNIQUE idempotency_key`, CHECK estados, CHECK proveedor), índices (`pago.id`, `pago.turno_id`, `evento_pago.pago_id`), grants least-privilege (`SELECT, INSERT` a `app_turnos`, `REVOKE UPDATE, DELETE` sobre `evento_pago`), y añade `pago.turno_id` FK RESTRICT. Downgrade completo. No hay `create_all` en runtime (P3). `alembic current` debe reportar `005` tras aplicar.

## Risks / Trade-offs

- [Risk] `turno.pago_id` sin FK temporalmente huérfano si C-07 falla antes de constreñirlo → Mitigación: columna documentada como seam, tipos UUID estrictos, ningún flujo v1 la escribe salvo reprogramación (copia del valor puesto por C-07); `005` añade la constricción del lado de pago.
- [Risk] Reloj DB vs app en expiración TTL y checkout_token → Mitigación: `now()` transaccional de Postgres como referencia; tests congelan tiempo (freezegun) en el borde TTL (patrón C-05).
- [Risk] El adaptador simulado no valida dinero real → Mitigación: marca "(simulado)" en UI/mail/comprobantes y guard P15 impide modo simulado en producción.
- [Risk] Numeración de migraciones: `005` después de `004_recordatorio_mail` (head actual) → Mitigación: `down_revision = "004_recordatorio_mail"`, verificar `alembic current` en DB fresca.
- Trade-off: expiración computada (C-05) + job → lecturas con una condición más, a cambio de robustez ante caída del worker.
- Trade-off: `checkout_token` en Redis/DB con expiración → complejidad de store, a cambio de token de 1 uso exigido por P12.

## Migration Plan

1. Migración `005`: tablas `pago` + `evento_pago` (constraints, índices, grants, `REVOKE UPDATE,DELETE` sobre `evento_pago`), `pago.turno_id` FK RESTRICT → `turno.id`; sin datos iniciales.
2. Deploy: `alembic upgrade head` → luego API+worker; rollback = `downgrade -1` (tablas nuevas, sin pérdida si C-08 aún no corrió).
3. Verificación: `alembic current` = `005`; inserciones adversas (pago duplicado, idempotency_key duplicada, estado inválido) rechazadas en DB fresca; suite TDD en verde (webhook válido/inválido, replay idempotente, sandbox Aprobar/Rechazar/Expirar, token 1 uso, sandbox inexistente en mercadopago, guard P15, conciliación con discrepancia).

## Open Questions

- Q1 (monto default de seña): defaults configurables por env/DB, documentados (ya abierto en `10 §1.1`); no bloquea C-07.
- TTL exacta de `checkout_token` (vida corta) y su store (Redis vs DB): tuning, no cambia specs ni tareas.
- Intervalo del job de conciliación (diario): tuning por env.
