# Spec Delta — pagos

## MODIFIED Requirements

### Requirement: Puerto ProveedorPago con adaptador simulado y selección por PAGO_MODO

El sistema SHALL exponer un puerto `ProveedorPago` con adaptador `simulado` (infra/pago_simulado) y seleccionar la implementación por `PAGO_MODO=simulado|mercadopago` (default `simulado`). El puerto SHALL ofrecer además ejecutar y consultar una devolución por `idempotency_key`. `MP_ACCESS_TOKEN` y `MP_PUBLIC_KEY` SHALL ser opcionales y requeridas solo cuando `PAGO_MODO=mercadopago`; `MP_WEBHOOK_SECRET` SHALL usarse en ambos modos (P5).

#### Scenario: Default simulado sin credenciales MP arranca
- **WHEN** `PAGO_MODO=simulado` y `MP_ACCESS_TOKEN`/`MP_PUBLIC_KEY` están vacíos
- **THEN** el adaptador activo es `simulado` y la aplicación arranca sin exigir credenciales de MP

#### Scenario: Modo mercadopago sin credenciales falla en validación
- **WHEN** `PAGO_MODO=mercadopago` y falta `MP_ACCESS_TOKEN` o `MP_PUBLIC_KEY`
- **THEN** el sistema rechaza el arranque con error de configuración (P5)

#### Scenario: Devolución simulada devuelve id sintético estable por idempotency_key
- **WHEN** el adaptador simulado ejecuta dos veces una devolución con la misma `idempotency_key`
- **THEN** ambas llamadas devuelven el mismo `mp_refund_id` con prefijo `sim_refund_`, ninguna mueve dinero y la consulta por esa key informa la devolución como realizada (P4)

#### Scenario: Consulta de devolución nunca ejecutada
- **WHEN** se consulta al adaptador simulado una `idempotency_key` que nunca se ejecutó
- **THEN** informa que no existe devolución para esa key, sin crearla (borde)

### Requirement: Modelo EventoPago append-only sin UPDATE/DELETE

El sistema SHALL persistir `EventoPago` append-only con: `pago_id`, `tipo_evento` (`creado|webhook_recibido|aprobado|rechazado|devolucion_solicitada|devolucion_aprobada|devolucion_rechazada|devolucion_ejecutada|conciliado`), `payload_json`, `actor`, `created_at`. El rol de app SHALL tener revocado `UPDATE`/`DELETE` sobre `evento_pago` (P9).

#### Scenario: Evento de pago se inserta y no se puede modificar ni borrar
- **WHEN** se inserta un `EventoPago` y el rol de app intenta `UPDATE` o `DELETE`
- **THEN** la base de datos deniega la sentencia (P9)

#### Scenario: Evento de rechazo de devolución es un tipo válido
- **WHEN** se inserta un `EventoPago` con `tipo_evento = devolucion_rechazada`
- **THEN** la base de datos lo acepta, y rechaza cualquier `tipo_evento` fuera de la lista cerrada (borde)

### Requirement: POST /webhooks/mercadopago mismo handler en ambos modos

El sistema SHALL exponer `POST /webhooks/mercadopago` (mismo handler en ambos modos): valida firma con `MP_WEBHOOK_SECRET` → persiste `evento_pago(webhook_recibido)` con payload crudo → idempotencia por `mp_payment_id` para eventos de pago y por `mp_refund_id` para eventos de devolución, independientes entre sí → recién ahí `creado→confirmado` (`aprobado`, emitiendo su recibo) o `creado→cancelado` (`rechazado`/expirado), o la ejecución de la devolución, con actor `sistema` (P10).

#### Scenario: Webhook válido aprueba y confirma el turno con actor sistema
- **WHEN** llega un webhook firmado con `MP_WEBHOOK_SECRET` y `mp_payment_id` de un pago `pendiente` con estado `aprobado`
- **THEN** se persiste `evento_pago(webhook_recibido)` con payload crudo y el turno pasa a `confirmado` con historial (`sistema`)

#### Scenario: Webhook rechazado cancela el turno con actor sistema
- **WHEN** el webhook indica `rechazado` para un pago `pendiente`
- **THEN** el turno pasa a `cancelado` con historial (`sistema`) y se libera el slot

#### Scenario: Replay del mismo webhook no duplica transición (idempotencia)
- **WHEN** se envía dos veces el mismo webhook con idéntico `mp_payment_id`
- **THEN** la segunda vez no crea segunda transición ni segundo `evento_pago(webhook_recibido)` procesado (P4)

#### Scenario: Firma inválida es rechazada
- **WHEN** el webhook llega con firma que no valida contra `MP_WEBHOOK_SECRET`
- **THEN** el sistema responde 401 y no persiste evento ni muta el pago

#### Scenario: Webhook de devolución sobre un pago ya aprobado se procesa
- **WHEN** llega un webhook firmado con `mp_refund_id` de una devolución `aprobada` cuyo pago ya tuvo su webhook de aprobación
- **THEN** el evento no se descarta como replay del pago: se persiste `webhook_recibido`, la devolución pasa a `ejecutada` y el turno a `devuelto` (actor `sistema`)

#### Scenario: Replay del webhook de devolución no duplica
- **WHEN** se entrega dos veces el mismo webhook con idéntico `mp_refund_id`
- **THEN** la segunda entrega no crea un segundo `devolucion_ejecutada`, ni recibo, ni transición (P4)

#### Scenario: Webhook de devolución no aprobada es ignorado sin efectos
- **WHEN** llega un webhook firmado con un `mp_refund_id` que no corresponde a una devolución `aprobada`
- **THEN** el sistema responde con error explícito, persiste el payload crudo para auditoría y no ejecuta ni transiciona nada (borde)

### Requirement: Job diario de conciliación interna contra proveedor simulado

El sistema SHALL ejecutar un job diario que compare `pago`/`evento_pago` internos contra el estado del proveedor simulado (verificación de consistencia interna, no contra API de MP), teniendo en cuenta las devoluciones ejecutadas. Discrepancias → `evento_pago(conciliado)` + alerta en bandeja (D14 §6).

#### Scenario: Conciliación detecta discrepancia y genera evento conciliado
- **WHEN** el estado interno de un pago difiere del estado reportado por el proveedor simulado
- **THEN** se persiste `evento_pago(conciliado)` con payload y se genera una alerta en bandeja

#### Scenario: Pago reembolsado no se reporta como discrepancia
- **WHEN** un pago está `reembolsado_parcial` o `reembolsado_total` y tiene su `devolucion_ejecutada` consistente
- **THEN** el job no genera alerta para ese pago

#### Scenario: Pago aprobado de turno cancelado con 0 % no es discrepancia
- **WHEN** un pago sigue `aprobado` y su turno quedó `cancelado` o `no_show` con cotización 0 % y sin devolución
- **THEN** el job no genera alerta: la seña retenida es el estado esperado (RN-SENIA-0)

#### Scenario: Devolución ejecutada sin reflejo en pago o turno genera alerta
- **WHEN** una devolución figura `ejecutada` pero su pago sigue `aprobado` o su turno no está `devuelto`
- **THEN** el job persiste `evento_pago(conciliado)` con el detalle de la inconsistencia y la alerta aparece en la bandeja (borde)
