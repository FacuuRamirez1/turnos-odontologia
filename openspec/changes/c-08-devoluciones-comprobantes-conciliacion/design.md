# Design — c-08-devoluciones-comprobantes-conciliacion

## Context

Motivación en `proposal.md` (Why). Estado observado en el código (head de migraciones `005_pago_evento_pago`):

- `domain/turnos/estados.py::transition()` es el único camino de transición; ya admite `cancelado→devuelto` solo para `sistema` y ya engancha el outbox de C-09 en `creado→confirmado` (patrón "efecto en el mismo flush").
- `domain/turnos/cancelacion.py::cotizar_devolucion()` es pura (100 si `inicio - ahora >= ANTICIPACION_MIN_HS`, 60 si futuro, 0 si ya empezó). La usan `POST /reservas/{id}/cancelar` y `GET /mail/cancelar`; ninguno persiste la devolución (la respuesta de reservas arma un dict `{"estado":"pendiente"}` a mano).
- `api/pagos.py::_procesar_webhook_pago()` hace idempotencia buscando **cualquier** `evento_pago(webhook_recibido)` del pago. Un webhook de devolución sobre un pago ya aprobado sería descartado como replay → hay que separar la idempotencia de pago y de devolución.
- `ProveedorPago` solo tiene `generar_checkout` / `ejecutar_accion`; `PagoSimuladoAdapter` guarda `checkout_token` en memoria (singleton por proceso).
- `evento_pago.tipo_evento` tiene CHECK cerrado sin `devolucion_rechazada`; `actor` es CHECK de tipos de rol (`paciente|odontologo|recepcionista|admin|sistema`), el id del actor no tiene columna.
- `workers/conciliacion.py` infiere el estado esperado solo desde eventos de pago: un pago `reembolsado_*` hoy sería falsa discrepancia.
- Reprogramación (`api/reservas.py`): el turno nuevo hereda `turno.pago_id`; `pago.turno_id` sigue apuntando al turno original. Resolver "pago del turno" exige `turno.pago_id` o, si es null, `Pago.turno_id == turno.id`.
- `SmtpMailer.enviar()` no soporta adjuntos; outbox `_encolar` es idempotente por `(turno_id, tipo)`; el worker renderiza `aviso_devolucion` con `contexto_json`.
- No hay librería de PDF en `requirements.txt`; C-09 fijó el criterio "sin dependencias nuevas".

## Goals / Non-Goals

**Goals:**
- Un solo punto de alta de devolución (hook en `transition`) que cubra los tres orígenes de cancelación sin duplicar lógica.
- Doble barrera (app + DB) para el ciclo de la devolución y para "una devolución por pago" (P6).
- Ejecución que pase por el mismo pipeline firmado del webhook (P10) y sea segura ante reintentos, caídas y concurrencia (P4).
- Comprobantes inmutables reproducibles en PDF sin dependencias ni blobs.

**Non-Goals:**
- Adaptador MercadoPago real de devoluciones (queda la firma del puerto; `mercadopago` sigue `NotImplementedError`).
- Auto-aprobación por umbral (Q4): no se agrega env var ni código condicional.
- Vista de estado de devolución para el paciente, UI de bandeja (C-11), exportaciones de caja (C-12).

## Decisions

### D1. Alta de la devolución como efecto de `transition(confirmado→cancelado)`

En `transition()`, tras escribir el historial y antes del `flush`, si `(origen, destino) == ("confirmado","cancelado")` se invoca (import diferido, igual que el outbox) `domain.devoluciones.service.registrar_por_cancelacion(session, turno, ahora=referencia, actor_tipo, actor_id)`: resuelve el pago del turno (helper `resolver_pago_de_turno`, extraído de la lógica de reprogramar), y si está `aprobado` **y el porcentaje es > 0** crea `devolucion(pendiente)` + `evento_pago(devolucion_solicitada, actor=actor_tipo, payload={actor_id, porcentaje, monto})`. Mismo flush ⇒ si falla, rollback de la cancelación (spec "Falla al crear la devolución revierte la cancelación").
El porcentaje se calcula con `cotizar_devolucion(turno.inicio, ANTICIPACION_MIN_HS, ahora=referencia)`: **la misma función y el mismo instante** que la transición, así el borde exacto (`==` → 100) coincide con la cotización previa.
**Cotización 0 % (decisión del usuario en revisión humana, sustituye la versión anterior que persistía una fila de monto 0 solo rechazable)**: el servicio retorna `None` sin escribir nada — sin `devolucion`, sin `devolucion_solicitada`, sin recibo de devolución, sin `aviso_devolucion`; el pago sigue `aprobado` y el turno queda `cancelado` como estado final (la máquina sigue permitiendo `cancelado→devuelto` solo para `sistema` tras una devolución ejecutada, que en este caso nunca existe). `cotizar_devolucion` no cambia: sigue devolviendo 0 para que la UI/mail muestren la regla antes de confirmar.
`POST /reservas/{id}/cancelar` deja de calcular el dict a mano y devuelve la devolución creada, o `null` si no hubo pago aprobado o la cotización fue 0 %.
**Decisión aprobada por el equipo (revisión humana del propose)**: el cambio de forma de la respuesta de `POST /reservas/{id}/cancelar` (objeto real o `null`, marcado BREAKING en el proposal) fue aprobado por el usuario sin cambios de fondo.
*Alternativa descartada*: llamar al servicio desde cada endpoint (reservas, mail, staff) → tres puntos de falla y riesgo de olvidar uno.

### D2. Cálculo de monto con `Decimal` y `ROUND_HALF_UP`

`monto = (pago.monto * porcentaje / 100).quantize(Decimal("0.01"), ROUND_HALF_UP)`, función pura `calcular_monto_devolucion(monto_pago, porcentaje)` en `domain/devoluciones/calculo.py`, que solo acepta 100 o 60 (cualquier otro valor, incluido 0, es error de dominio: el 0 % se filtra antes en D1). Nunca `float`. El trigger de DB verifica `monto <= pago.monto`.

### D3. Modelo `devolucion` y doble barrera de transiciones

Columnas: `id, pago_id FK RESTRICT, turno_id FK RESTRICT, monto NUMERIC(10,2), porcentaje SMALLINT, motivo, estado, idempotency_key, mp_refund_id NULL, aprobada_por, aprobada_at, rechazada_por, rechazada_at, motivo_rechazo, ejecutada_por, ejecutada_at` + `AuditMixin` (la fila cambia de estado; el rastro inmutable vive en `evento_pago`).
Constraints: `UNIQUE(pago_id)`, `UNIQUE(idempotency_key)`, `UNIQUE(mp_refund_id)`, `CHECK porcentaje IN (100,60)`, `CHECK monto > 0`, `CHECK estado IN (...)`, `CHECK (estado <> 'ejecutada' OR mp_refund_id IS NOT NULL)`, `CHECK` de coherencia actor/fecha por estado (aprobada/ejecutada ⇒ `aprobada_por/at`; rechazada ⇒ `rechazada_por/at/motivo_rechazo`; ejecutada ⇒ `ejecutada_por/at`).
Trigger `BEFORE UPDATE` `devolucion_guard_transicion`: solo permite `pendiente→aprobada|rechazada`, `aprobada→ejecutada` o sin cambio de estado; trigger `BEFORE INSERT` valida `monto <= pago.monto`. En app, `domain/devoluciones/estados.py` replica la tabla de transiciones → 409 `TRANSICION_DEVOLUCION_INVALIDA` antes de tocar la DB.
`idempotency_key = "dev_" + pago_id` (determinística: un pago, una devolución). Los ids de actor (`sub` del JWT) se guardan en columnas `*_por` y en `payload_json` del evento; el `actor` del evento sigue siendo el tipo de rol (CHECK existente).
*Alternativa descartada*: `turno_historial`-style tabla de historial de devolución → duplica `evento_pago`, que ya es el audit trail append-only de pagos.

### D4. Ejecución: endpoint → puerto → evento firmado → mismo handler del webhook

`POST /api/devoluciones/{id}/ejecutar`:
1. `SELECT … FOR UPDATE` de la devolución (serializa ejecuciones concurrentes) + chequeo de scope P8.
2. Si `estado == ejecutada` → responde el resultado existente (idempotente). Si no es `aprobada` → 409.
3. Registra `ejecutada_por/at` (quién pidió la ejecución y cuándo) en la fila todavía `aprobada` —así sirve igual cuando el webhook real de MP llegue asíncrono—, consulta `proveedor.consultar_devolucion(idempotency_key)`; si no existe, `proveedor.ejecutar_devolucion(idempotency_key, mp_payment_id, monto)`.
4. El adaptador simulado devuelve `{payload, firma}` con `mp_refund_id = "sim_refund_" + uuid5(NAMESPACE, idempotency_key)` (estable sin store persistente: sobrevive reinicios del proceso), `mp_payment_id`, `monto`, `status=refunded`.
5. El endpoint entrega el evento a `procesar_webhook(...)` —la misma función que usa `POST /webhooks/mercadopago`— que valida firma, persiste `webhook_recibido` con payload crudo y despacha por tipo: si el payload trae `mp_refund_id` → rama devolución.
6. Rama devolución (idempotente por `mp_refund_id`: si ya hay devolución con ese id en `ejecutada`, no hace nada): devolución `ejecutada` + `mp_refund_id`, pago `reembolsado_total|parcial`, `evento_pago(devolucion_ejecutada, actor=sistema, payload={solicitado_por, monto, mp_refund_id})`, `transition(turno, "devuelto", actor_tipo="sistema")`, recibo de devolución, `encolar_aviso_devolucion(...)`. Todo en una transacción; commit al final.
En `PAGO_MODO=mercadopago`, `get_proveedor_pago()` lanza `NotImplementedError` → 503 `PROVEEDOR_NO_DISPONIBLE`, sin fallback.
*Alternativa descartada*: que el endpoint marque `ejecutada` directamente → rompe P10 (solo el handler del webhook confirma) y no ejercita la firma/idempotencia que usará MP real.

### D5. Idempotencia del webhook separada para pago y devolución

`_procesar_webhook_pago` pasa a buscar un `webhook_recibido` previo cuyo payload tenga el **mismo `mp_payment_id` y sea de tipo pago** (`payload_json.kind = "pago"`); la rama devolución usa `mp_refund_id`. Se agrega `kind` (`pago|devolucion`) al payload persistido. Los `webhook_recibido` existentes de C-07 sin `kind` se interpretan como `pago` (compatibilidad, sin migrar datos).

### D6. Comprobantes: fila inmutable + PDF generado on-demand

Tabla `comprobante`: `id, pago_id FK, devolucion_id FK NULL, turno_id FK, tipo ('recibo_interno'|'factura_arca'), concepto ('pago'|'devolucion'), numero (desde secuencia `comprobante_numero_seq`, formateado `RI-000001`), monto, moneda, cae NULL, emitida_at, simulado BOOL, payload_json` (snapshot: paciente nombre/apellido, odontólogo, fecha del turno, porcentaje). Sin `AuditMixin`; `GRANT SELECT, INSERT` + `REVOKE UPDATE, DELETE`. Unicidad parcial: `UNIQUE(pago_id) WHERE concepto='pago'`, `UNIQUE(devolucion_id) WHERE devolucion_id IS NOT NULL`; `CHECK (concepto='devolucion') = (devolucion_id IS NOT NULL)`. `simulado = (pago.proveedor == 'simulado')` al emitir; nunca se recalcula.
Emisión: `emitir_recibo_pago` en la rama `aprobado` del webhook y `emitir_recibo_devolucion` en la rama devolución, ambas idempotentes (si ya existe, devuelven la existente; la DB arbitra con los UNIQUE parciales).
PDF: `domain/comprobantes/pdf.py`, generador PDF 1.4 mínimo en stdlib (una página, Helvetica, `WinAnsiEncoding` que incluye "—" y acentos), renderizado desde el snapshot → determinístico, sin blobs en DB. La leyenda "SIMULADO — sin valor fiscal ni movimiento de dinero" se dibuja si `comprobante.simulado`.
*Alternativas descartadas*: `reportlab`/`fpdf2` → dependencia nueva contra el criterio de C-09; guardar el PDF como `bytea` → duplica datos y complica la inmutabilidad.

### D7. Aviso de devolución con adjunto, sin link público

`encolar_aviso_devolucion(session, turno, porcentaje, *, monto, resultado, comprobante_id=None)` amplía `contexto_json`. El worker, si `contexto_json.comprobante_id`, regenera el PDF y lo pasa a `SmtpMailer.enviar(..., adjuntos=[(nombre, bytes, "application/pdf")])` (stdlib `EmailMessage.add_attachment`). Plantilla `aviso_devolucion` versión `v2` (monto, resultado, "(simulado)" y "no se movió dinero real"); `v1` queda registrada para filas viejas. Se encola en ejecución o rechazo; la idempotencia `(turno_id, tipo)` del outbox garantiza un único aviso. No hay endpoint público de comprobantes (P12).

### D8. API staff y scope P8

Router `api/devoluciones.py` con `require_role("odontologo","recepcionista","admin")`; repositorio `DevolucionRepository.scoped(ident)` que agrega `JOIN turno … WHERE turno.odontologo_id = :propio` cuando el rol es odontólogo (forzado en repositorio, nunca en el endpoint). Lecturas/acciones fuera de scope → 403 (consistente con `GET /pagos/{id}` de C-07). Endpoints: `GET /api/devoluciones?estado=`, `GET /api/devoluciones/alertas`, `GET /api/devoluciones/{id}`, `POST …/{id}/aprobar` (`{monto_confirmado: Decimal, motivo?}`), `POST …/{id}/rechazar` (`{motivo: str min_length=1}`), `POST …/{id}/ejecutar`; `api/comprobantes.py` (`GET /api/comprobantes/{id}`, `GET /api/comprobantes/{id}/pdf`); `GET /api/turnos/{turno_id}/trazabilidad`. Todos los schemas Pydantic v2 con `extra='forbid'` (P2) y campo `marca` = `marca_pago_actual()`.

### D9. Conciliación con reembolsos

`_estado_esperado_desde_eventos` incorpora `devolucion_ejecutada` (→ `reembolsado_total|parcial` según payload). Se agrega `conciliar_devoluciones(session)`: para cada devolución `ejecutada`, verifica pago `reembolsado_*` y turno `devuelto`; si no, `evento_pago(conciliado, payload={tipo:"devolucion", detalle})`. Un pago `aprobado` cuyo turno está `cancelado`/`no_show` sin devolución (cotización 0 %) es estado esperado, no discrepancia. Las alertas de bandeja se leen de `evento_pago(conciliado)` con `discrepancia=true`, scope P8 vía `pago.odontologo_id`.

### D10. Migración `006_devolucion_comprobante`

`down_revision = "005_pago_evento_pago"`. Crea `devolucion` (+ triggers), secuencia y `comprobante`, reemplaza `ck_evento_pago_tipo_cerrado` agregando `devolucion_rechazada`, índices (`devolucion.estado`, `devolucion.turno_id`, `comprobante.pago_id`, `comprobante.turno_id`), grants (`devolucion`: SELECT/INSERT/UPDATE; `comprobante`: SELECT/INSERT + REVOKE UPDATE/DELETE). Downgrade completo (restaura el CHECK original; falla explícitamente si existen eventos `devolucion_rechazada`, para no perder audit trail).

## Risks / Trade-offs

- [Risk] Hook en `transition()` acopla turnos→devoluciones → Mitigación: import diferido + servicio con interfaz mínima; tests del hook aislados y tests de C-05 en verde como safety net.
- [Risk] Generador PDF artesanal produce archivos inválidos en algún visor → Mitigación: test que valida estructura (`%PDF-1.4`, xref, `%%EOF`) y extracción del texto de la leyenda; contenido solo ASCII/WinAnsi.
- [Risk] Carrera entre dos ejecuciones → Mitigación: `FOR UPDATE` + `UNIQUE(mp_refund_id)` + id determinístico; la segunda ve `ejecutada` y responde idempotente.
- [Risk] Caída entre respuesta del proveedor y commit local → Mitigación: el reintento consulta `consultar_devolucion(idempotency_key)` (simulado: id determinístico) antes de re-ejecutar; nunca segunda devolución.
- [Risk] Cambio de semántica de idempotencia del webhook rompe tests de C-07 → Mitigación: eventos sin `kind` = `pago`; correr `test_pagos_webhook.py` como safety net antes de tocar.
- [Risk] Respuesta de `cancelar` cambia (`devolucion` puede ser `null`) → Mitigación: marcado BREAKING en proposal; C-10/C-11 aún no consumen el campo (C-10 sin implementar).
- Trade-off: aprobación manual de todo (Q4) agrega carga operativa a cambio de no inventar una política no aprobada.
- Trade-off: con cotización 0 % no hay fila de devolución (decisión del usuario); la trazabilidad de esa cancelación queda en `turno_historial` (actor + fecha) y el pago `aprobado` sin devolución, a cambio de no cargar la bandeja con filas que solo se podían rechazar.

## Migration Plan

1. `alembic upgrade head` → `006_devolucion_comprobante` (sin datos iniciales; tablas vacías).
2. Deploy API + worker (el worker necesita la plantilla `v2` y el soporte de adjuntos).
3. `seed_dev.py` agrega 1 pago aprobado con su recibo + 1 devolución 60 % ejecutada con su recibo (proveedor `simulado`, KB 04 §5), idempotente.
4. Verificación: `alembic current` = `006`; inserciones adversas rechazadas (segunda devolución por pago, porcentaje 0 o 50, monto 0, retroceso de estado, UPDATE de comprobante); suite TDD completa en verde.
5. Rollback: `alembic downgrade -1` (solo si no hay eventos `devolucion_rechazada`; si los hay, el downgrade aborta a propósito).

## Open Questions

- Q4 (umbral de auto-aprobación del 60 %): sigue abierta; el diseño no la resuelve y no deja código condicional. Agregarla después es un requirement nuevo, no un cambio de éste.
- Formato exacto del número de recibo (`RI-000001` vs. con año): cosmético, no cambia specs.
- Nombre de archivo del adjunto PDF (`recibo-RI-000001.pdf`): cosmético.
