# pagos

## Purpose

Provee un puerto de pagos con adaptador simulado (MVP, `PAGO_MODO=simulado`) que convierte una reserva en `creado` en un pago con checkout, confirma o cancela el turno únicamente vía webhook server-to-server, y deja listo el mismo handler para MercadoPago real en v2 sin refactorizar (D14).

## Requirements

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

### Requirement: Modelo Pago separado del turno con idempotencia

El sistema SHALL persistir `Pago` como entidad separada del `Turno` (D13) con: `turno_id`, `odontologo_id`, `monto`, `moneda='ARS'`, `proveedor` (`simulado|mercadopago`, default `simulado`), `mp_payment_id` único (sintético `sim_pay_<uuid>` si simulado), `mp_preference_id` nullable (solo mercadopago), `estado` (`pendiente|aprobado|rechazado|reembolsado_parcial|reembolsado_total`), `idempotency_key` única, `created_at`. `UNIQUE(mp_payment_id)` y `UNIQUE(idempotency_key)` enforced en DB (P4/P6).

#### Scenario: Pago pendiente con mp_payment_id sintético al reservar
- **WHEN** `PAGO_MODO=simulado` y se crea una reserva
- **THEN** se persiste un `Pago` con `estado='pendiente'`, `proveedor='simulado'` y `mp_payment_id='sim_pay_<uuid>'`

#### Scenario: Dos pagos con mismo idempotency_key son rechazados por DB
- **WHEN** se intenta insertar un segundo `Pago` con `idempotency_key` duplicada saltando la API
- **THEN** la base de datos rechaza la inserción por violación de unicidad (P4)

### Requirement: Modelo EventoPago append-only sin UPDATE/DELETE

El sistema SHALL persistir `EventoPago` append-only con: `pago_id`, `tipo_evento` (`creado|webhook_recibido|aprobado|rechazado|devolucion_solicitada|devolucion_aprobada|devolucion_rechazada|devolucion_ejecutada|conciliado`), `payload_json`, `actor`, `created_at`. El rol de app SHALL tener revocado `UPDATE`/`DELETE` sobre `evento_pago` (P9).

#### Scenario: Evento de pago se inserta y no se puede modificar ni borrar
- **WHEN** se inserta un `EventoPago` y el rol de app intenta `UPDATE` o `DELETE`
- **THEN** la base de datos deniega la sentencia (P9)

#### Scenario: Evento de rechazo de devolución es un tipo válido
- **WHEN** se inserta un `EventoPago` con `tipo_evento = devolucion_rechazada`
- **THEN** la base de datos lo acepta, y rechaza cualquier `tipo_evento` fuera de la lista cerrada (borde)

### Requirement: Migración 005 tablas pago + evento_pago; resolver referencia circular turno↔pago

El sistema SHALL crear mediante migración Alembic `005` (down_revision `004_recordatorio_mail`, cero `create_all`, P3) las tablas `pago` y `evento_pago`. Se resuelve `turno.pago_id` sin FK + referencia circular con FK diferible o columna solo de un lado, y se valida la existencia del pago al reprogramar (el nuevo turno hereda el `pago`) (P3/P9).

#### Scenario: Migración 005 aplica sobre head 004 y crea pago + evento_pago
- **WHEN** se ejecutan las migraciones hasta `005` sobre una base con head `004`
- **THEN** existen las tablas `pago` y `evento_pago` con sus constraints y `alembic current` reporta `005`

#### Scenario: Nuevo turno al reprogramar hereda el pago del origen
- **WHEN** se reprograma un `confirmado` con `pago_id` asignado
- **THEN** el nuevo turno `confirmado` hereda el mismo `pago_id` y no hay nuevo cobro (Q3 default: seña original)

### Requirement: POST /reservas crea turno+pago+evento atómicamente y devuelve checkout_url + checkout_token

El sistema SHALL, en `POST /reservas`, crear de forma atómica (una transacción) `turno(creado)` + `pago(pendiente, proveedor='simulado')` + `evento_pago(creado)` antes de invocar al adaptador, y devolver `checkout_url` (pantalla "Checkout simulado") + `checkout_token` de 1 uso y vida corta. Respeta TTL de pre-reserva `RESERVA_TTL_MIN` (15 min). Escribir turno+pago+evento antes de invocar al adaptador: nunca cobrar sin rastro local (P10).

#### Scenario: Reserva feliz crea turno creado + pago pendiente + evento creado + checkout
- **WHEN** un cliente público reserva un slot válido con `PAGO_MODO=simulado`
- **THEN** responde 201 con `checkout_url`, `checkout_token` de 1 uso y vida corta, y existen `turno(creado)`, `pago(pendiente)`, `evento_pago(creado)` ligados al turno

#### Scenario: Escritura atómica antes de invocar el adaptador
- **WHEN** la reserva se confirma en la transacción local antes de llamar al adaptador simulado
- **THEN** si la transacción falla no se invoca al adaptador ni se persiste pago (no cobro sin rastro)

#### Scenario: Checkout_token de 1 uso no se reutiliza
- **WHEN** se consume un `checkout_token` en el sandbox
- **THEN** el token queda inutilizado para un segundo `POST /pagos/{pago_id}/simular`

### Requirement: Endpoint sandbox POST /pagos/{pago_id}/simular solo en modo simulado

El sistema SHALL exponer `POST /pagos/{pago_id}/simular` (Aprobar / Rechazar / opcional Expirar) solo si `PAGO_MODO=simulado`. Exige `checkout_token` de 1 uso, con rate-limit. Apagado en producción / modo `mercadopago`. No integra las 6 rutas públicas de producción (P12: excepción documentada condicionada por flag). El frontend nunca confirma: el endpoint le pide al adaptador simulado emitir el evento firmado (P10).

#### Scenario: Sandbox aprueba con checkout_token válido en modo simulado
- **WHEN** `PAGO_MODO=simulado` y se llama al sandbox con `checkout_token` válido y acción Aprobar
- **THEN** el adaptador emite un evento firmado (`MP_WEBHOOK_SECRET`) entregado al handler del webhook y el pago pasa a `aprobado`

#### Scenario: Sandbox inexistente con PAGO_MODO=mercadopago o en producción
- **WHEN** `PAGO_MODO=mercadopago` o el entorno es producción
- **THEN** `POST /pagos/{pago_id}/simular` no existe (404) o el guard de arranque impide el modo simulado (P15)

#### Scenario: Checkout_token de 1 uso rechazado tras consumo
- **WHEN** se reusa un `checkout_token` ya consumido
- **THEN** el sistema responde 403/422 y no emite evento (P12)

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

### Requirement: Escritura atómica turno+pago+evento antes de invocar el adaptador

El sistema SHALL persistir `turno` + `pago` + `evento_pago` en la misma transacción antes de invocar al adaptador de pagos; el adaptador solo emite eventos, nunca confirma directamente el turno (P10).

#### Scenario: No se invoca al adaptador si la transacción local falla
- **WHEN** la escritura local de turno+pago+evento falla
- **THEN** no se invoca al adaptador simulado y no hay cobro ni evento externo

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

### Requirement: Marca "(simulado)" en respuesta/UI/mail de pago cuando PAGO_MODO=simulado

El sistema SHALL agregar la marca "(simulado)" a toda respuesta, UI y mail de pago/devolución cuando `PAGO_MODO=simulado`, para no prometer dinero real ni valor fiscal (D14 §0, §5). Los comprobantes PDF llevan leyenda "SIMULADO — sin valor fiscal ni movimiento de dinero".

#### Scenario: Respuesta de pago incluye marca simulado en modo simulado
- **WHEN** `PAGO_MODO=simulado` y se consulta un pago aprobado
- **THEN** la respuesta incluye la marca "(simulado)"

### Requirement: Guard de arranque/CI contra modo simulado y sandbox en producción (P15)

El sistema SHALL incluir un guard de arranque y de CI que impida que `PAGO_MODO=simulado` o el endpoint sandbox `POST /pagos/{pago_id}/simular` estén activos en producción (P15).

#### Scenario: Arranque en producción con PAGO_MODO=simulado falla
- **WHEN** `ENVIRONMENT=production` y `PAGO_MODO=simulado`
- **THEN** la aplicación falla al arrancar (P15)
