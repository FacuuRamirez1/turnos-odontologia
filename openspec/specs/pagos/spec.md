# pagos

## Purpose

Provee un puerto de pagos con adaptador simulado (MVP, `PAGO_MODO=simulado`) que convierte una reserva en `creado` en un pago con checkout, confirma o cancela el turno únicamente vía webhook server-to-server, y deja listo el mismo handler para MercadoPago real en v2 sin refactorizar (D14).

## Requirements

### Requirement: Puerto ProveedorPago con adaptador simulado y selección por PAGO_MODO

El sistema SHALL exponer un puerto `ProveedorPago` con adaptador `simulado` (infra/pago_simulado) y seleccionar la implementación por `PAGO_MODO=simulado|mercadopago` (default `simulado`). `MP_ACCESS_TOKEN` y `MP_PUBLIC_KEY` SHALL ser opcionales y requeridas solo cuando `PAGO_MODO=mercadopago`; `MP_WEBHOOK_SECRET` SHALL usarse en ambos modos (P5).

#### Scenario: Default simulado sin credenciales MP arranca
- **WHEN** `PAGO_MODO=simulado` y `MP_ACCESS_TOKEN`/`MP_PUBLIC_KEY` están vacíos
- **THEN** el adaptador activo es `simulado` y la aplicación arranca sin exigir credenciales de MP

#### Scenario: Modo mercadopago sin credenciales falla en validación
- **WHEN** `PAGO_MODO=mercadopago` y falta `MP_ACCESS_TOKEN` o `MP_PUBLIC_KEY`
- **THEN** el sistema rechaza el arranque con error de configuración (P5)

### Requirement: Modelo Pago separado del turno con idempotencia

El sistema SHALL persistir `Pago` como entidad separada del `Turno` (D13) con: `turno_id`, `odontologo_id`, `monto`, `moneda='ARS'`, `proveedor` (`simulado|mercadopago`, default `simulado`), `mp_payment_id` único (sintético `sim_pay_<uuid>` si simulado), `mp_preference_id` nullable (solo mercadopago), `estado` (`pendiente|aprobado|rechazado|reembolsado_parcial|reembolsado_total`), `idempotency_key` única, `created_at`. `UNIQUE(mp_payment_id)` y `UNIQUE(idempotency_key)` enforced en DB (P4/P6).

#### Scenario: Pago pendiente con mp_payment_id sintético al reservar
- **WHEN** `PAGO_MODO=simulado` y se crea una reserva
- **THEN** se persiste un `Pago` con `estado='pendiente'`, `proveedor='simulado'` y `mp_payment_id='sim_pay_<uuid>'`

#### Scenario: Dos pagos con mismo idempotency_key son rechazados por DB
- **WHEN** se intenta insertar un segundo `Pago` con `idempotency_key` duplicada saltando la API
- **THEN** la base de datos rechaza la inserción por violación de unicidad (P4)

### Requirement: Modelo EventoPago append-only sin UPDATE/DELETE

El sistema SHALL persistir `EventoPago` append-only con: `pago_id`, `tipo_evento` (`creado|webhook_recibido|aprobado|rechazado|devolucion_solicitada|devolucion_aprobada|devolucion_ejecutada|conciliado`), `payload_json`, `actor`, `created_at`. El rol de app SHALL tener revocado `UPDATE`/`DELETE` sobre `evento_pago` (P9).

#### Scenario: Evento de pago se inserta y no se puede modificar ni borrar
- **WHEN** se inserta un `EventoPago` y el rol de app intenta `UPDATE` o `DELETE`
- **THEN** la base de datos deniega la sentencia (P9)

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

El sistema SHALL exponer `POST /webhooks/mercadopago` (mismo handler en modo simulado y mercadopago): valida firma con `MP_WEBHOOK_SECRET` → persiste `evento_pago(webhook_recibido)` con payload crudo → idempotencia por `mp_payment_id`/`mp_refund_id` → recién ahí `creado→confirmado` (`aprobado`) o `creado→cancelado` (`rechazado`/expirado), con actor `sistema` (P10).

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

### Requirement: Escritura atómica turno+pago+evento antes de invocar el adaptador

El sistema SHALL persistir `turno` + `pago` + `evento_pago` en la misma transacción antes de invocar al adaptador de pagos; el adaptador solo emite eventos, nunca confirma directamente el turno (P10).

#### Scenario: No se invoca al adaptador si la transacción local falla
- **WHEN** la escritura local de turno+pago+evento falla
- **THEN** no se invoca al adaptador simulado y no hay cobro ni evento externo

### Requirement: Job diario de conciliación interna contra proveedor simulado

El sistema SHALL ejecutar un job diario que compare `pago`/`evento_pago` internos contra el estado del proveedor simulado (verificación de consistencia interna, no contra API de MP). Discrepancias → `evento_pago(conciliado)` + alerta en bandeja (D14 §6).

#### Scenario: Conciliación detecta discrepancia y genera evento conciliado
- **WHEN** el estado interno de un pago difiere del estado reportado por el proveedor simulado
- **THEN** se persiste `evento_pago(conciliado)` con payload y se genera una alerta en bandeja

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
