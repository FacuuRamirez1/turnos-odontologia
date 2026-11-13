# Tasks — c-07-pagos-mp-checkout-webhook

> TDD (U2) en cada grupo: RED → GREEN → TRIANGULATE con 3 escenarios (feliz / error de negocio / borde). Tests conviven con su grupo, no al final. Assumptions abiertas (TTL de checkout_token, store del token, intervalo de conciliación) son solo-tuning: se implementan como env-tuneables sin cambiar specs ni tareas.

## 1. Migración 005 + modelos Pago/EventoPago

- [x] 1.1 Crear migración Alembic `005` (down_revision `004_recordatorio_mail`, tablas `pago` + `evento_pago`, `UNIQUE mp_payment_id`, `UNIQUE idempotency_key`, CHECK estados/proveedor, índices, grants least-privilege, `REVOKE UPDATE,DELETE` sobre `evento_pago`, `pago.turno_id` FK RESTRICT → `turno.id`) y verificar `alembic current` = `005` en DB fresca, cero `create_all` en runtime (P3)
- [x] 1.2 Implementar modelos SQLAlchemy `Pago`/`EventoPago` + repositorios y verificar con tests adversos directos a DB: `mp_payment_id` duplicado rechazado, `idempotency_key` duplicada rechazada, estado fuera de CHECK rechazado, `evento_pago` sin UPDATE/DELETE denegado al rol app (P9)
- [x] 1.3 Resolver `turno.pago_id` sin FK + referencia circular: añadir `pago.turno_id` FK, mantener `turno.pago_id` como espejo documentado, validar existencia del pago al reprogramar (el nuevo turno hereda el `pago`) (P9)

## 2. Puerto ProveedorPago + adaptador simulado + selección por PAGO_MODO

- [x] 2.1 Implementar puerto `ProveedorPago` + adaptador `simulado` (`infra/pago_simulado`) seleccionado por `PAGO_MODO=simulado|mercadopago` (default `simulado`); `MP_ACCESS_TOKEN`/`MP_PUBLIC_KEY` opcionales (solo con `mercadopago`); `MP_WEBHOOK_SECRET` en ambos modos (P5)
- [x] 2.2 Adaptador simulado genera `checkout_url` (pantalla "Checkout simulado") + `checkout_token` de 1 uso/vida corta (store con expiración) y firma eventos con HMAC sobre `MP_WEBHOOK_SECRET` entregándolos al handler del webhook (P10)
- [x] 2.3 Verificar arranque: default simulado sin credenciales MP arranca; modo `mercadopago` sin `MP_ACCESS_TOKEN`/`MP_PUBLIC_KEY` falla en validación de configuración (P5)

## 3. settings.py + contrato de entorno

- [x] 3.1 Añadir `PAGO_MODO` (validado `simulado|mercadopago`, default `simulado`) y volver `MP_ACCESS_TOKEN`/`MP_Public_KEY` opcionales con validación condicional en `settings.py`; `MP_WEBHOOK_SECRET` requerida en ambos modos (P5)
- [x] 3.2 Actualizar `backend/app/tests/test_env_contract.py` al nuevo contrato (`PAGO_MODO` default `simulado`, MP_* opcionales, `MP_WEBHOOK_SECRET` requerida en ambos modos, falla si `PAGO_MODO=mercadopago` sin credenciales)
- [x] 3.3 Documentar `PAGO_MODO=simulado` en `.env.example`/`.env` (ya presente) y secretos solo por env (P5)

## 4. POST /reservas integra pago atómico + checkout_url + checkout_token

- [x] 4.1 `POST /reservas` crea atómicamente (una transacción/UnitOfWork) `turno(creado)` + `pago(pendiente, proveedor='simulado')` + `evento_pago(creado)` antes de invocar al adaptador, y devuelve `checkout_url` + `checkout_token`; respeta TTL `RESERVA_TTL_MIN` (15 min) (P10)
- [x] 4.2 Schemas Pydantic v2 `extra='forbid'` en request/response de reserva (P2); tests: feliz (201 con checkout_url+checkout_token), error (consentimiento → 422 sin persistir), borde (replay Idempotency-Key no duplica; carrera misma slot → exactamente 1 turno + 409)

## 5. Endpoint sandbox POST /pagos/{pago_id}/simular

- [x] 5.1 Implementar `POST /pagos/{pago_id}/simular` (Aprobar/Rechazar/Expirar): solo si `PAGO_MODO=simulado`, exige `checkout_token` de 1 uso, rate-limit, token invalida tras consumo; el adaptador emite evento firmado al webhook (P12)
- [x] 5.2 Verificar: sandbox inexistente (404) con `PAGO_MODO=mercadopago`; `checkout_token` reusado → 403/422; flujo Aprobar/Rechazar/Expirar transita pago `pendiente→aprobado/rechazado` y dispara webhook con actor `sistema`

## 6. POST /webhooks/mercadopago (mismo handler, ambos modos)

- [x] 6.1 Implementar `POST /webhooks/mercadopago`: valida firma `MP_WEBHOOK_SECRET` → persiste `evento_pago(webhook_recibido)` con payload crudo → idempotencia por `mp_payment_id`/`mp_refund_id` → `creado→confirmado` (aprobado, actor `sistema`) o `creado→cancelado` (rechazado/expirado, actor `sistema`) (P10)
- [x] 6.2 Tests: webhook válido confirma + historial `sistema`; webhook rechazado cancela + libera slot; replay mismo `mp_payment_id` no duplica transición (idempotencia, P4); firma inválida → 401 sin persistir

## 7. Job diario de conciliación interna

- [x] 7.1 Implementar job diario que compara `pago`/`evento_pago` internos contra el estado del proveedor simulado (consistencia interna, no API MP); discrepancias → `evento_pago(conciliado)` + alerta en bandeja (D14 §6)
- [x] 7.2 Test: conciliación detecta discrepancia y genera `evento_pago(conciliado)` + alerta

## 8. Guard de arranque/CI P15

- [x] 8.1 Implementar guard de arranque: si `ENVIRONMENT=production` y `PAGO_MODO=simulado` (o endpoint sandbox expuesto), falla el arranque con `ValueError` (P15)
- [x] 8.2 Añadir job de CI que falle si `PAGO_MODO=simulado` con `ENVIRONMENT=production`; test que verifique el guard

## 9. Marca "(simulado)" en pago

- [x] 9.1 Agregar marca "(simulado)" a toda respuesta/UI/mail de pago/devolución cuando `PAGO_MODO=simulado`; comprobantes PDF con leyenda "SIMULADO — sin valor fiscal ni movimiento de dinero" (D14)

## 10. Integración y cierre del change

- [x] 10.1 Pasar suite completa (backend pytest + mypy + ruff, `alembic current`=005 en DB fresca, inserciones adversas rechazadas) y verificar `openspec validate --change c-07-pagos-mp-checkout-webhook` en verde
- [x] 10.2 Verificar que ningún spec archivado contradice el nuevo head y que C-08 dependencias quedan listas

## Workflow follow-up

- Archiviar el cambio tras revisión (`/opsx:archive c-07-pagos-mp-checkout-webhook`) y marcar `[x]` C-07 en CHANGES.md.
- Open questions deferrables (Q1 monto default de seña, TTL/store de checkout_token, intervalo de conciliación): solo tuning, no bloquean archive.
