# Tasks — c-08-devoluciones-comprobantes-conciliacion

> **Governance CRÍTICO**: cada grupo cierra con checkpoint de revisión humana antes de seguir. TDD (U2) en cada tarea: SAFETY NET (tests existentes del archivo a tocar) → RED → GREEN → TRIANGULATE con 3 escenarios (feliz / error de negocio / borde) → REFACTOR. Los tests viven en su grupo, no al final. Q4 queda abierta: **no** se implementa auto-aprobación ni umbral.

## 1. Migración 006 + modelos Devolucion/Comprobante

- [x] 1.1 Safety net: correr `test_pagos_migration_005.py`, `test_pagos_modelos.py`, `test_pagos_webhook.py`, `test_pagos_conciliacion.py`, `test_reservas_cancelacion.py`, `test_turno_transiciones.py`, `test_api_mail.py`, `test_plantillas.py`, `test_smtp.py`, `test_worker.py` y registrar el baseline (N passing); si algo falla, frenar y reportar como pre-existente
- [x] 1.2 RED: `test_migration_006.py` — upgrade sobre head `005` deja `alembic current` = `006_devolucion_comprobante`; downgrade restaura el CHECK original de `evento_pago`; downgrade aborta si existen eventos `devolucion_rechazada`
- [x] 1.3 GREEN: crear `backend/alembic/versions/006_devolucion_comprobante.py` (design D3/D6/D10: tablas, UNIQUE totales y parciales, CHECKs —`porcentaje IN (100,60)` y `monto > 0`—, triggers de transición y de `monto <= pago.monto`, secuencia de número, CHECK de `evento_pago` con `devolucion_rechazada`, índices, grants y `REVOKE UPDATE, DELETE` sobre `comprobante`); cero `create_all` (P3); verificar 1.2 en verde
- [x] 1.4 Modelos `infra/db/models/devolucion.py` y `comprobante.py` (+ export en `models/__init__.py`, `TIPOS_EVENTO_PAGO` con `devolucion_rechazada`) y `test_devolucion_modelos.py` con inserciones adversas directas a DB: segunda devolución por pago rechazada, `porcentaje = 0` y `porcentaje = 50` rechazados, `monto` > pago, `monto = 0` o negativo rechazado, retroceso `ejecutada→pendiente` rechazado por trigger, `ejecutada` sin `mp_refund_id` rechazado, UPDATE/DELETE de `comprobante` denegado al rol app, `evento_pago(devolucion_rechazada)` aceptado
- [x] 1.5 Checkpoint de revisión humana (CRÍTICO): presentar migración + resultado de tests adversos — **APROBADO por el usuario el 2026-11-16** (migración `006_devolucion_comprobante` aplicada; `test_devolucion_modelos.py` 17 casos + `test_migration_006.py` 7 casos, 30 passed)

## 2. Cálculo y alta de la devolución al cancelar

- [x] 2.1 RED→GREEN→TRIANGULATE `domain/devoluciones/calculo.py::calcular_monto_devolucion` en `test_devolucion_calculo.py`: 100 % de 10000.00 = 10000.00 (feliz), 60 % de 3333.33 = 2000.00 half-up (borde), porcentaje 0 o 50 → error de dominio (error; el 0 % nunca llega al cálculo)
- [x] 2.2 Extraer `resolver_pago_de_turno` (lógica hoy inline en `reprogramar`) y cubrirlo: turno con `pago_id`, turno sin `pago_id` resuelto por `pago.turno_id`, turno sin pago → `None`; verificar `test_reservas_reprogramacion.py` sigue en verde
- [x] 2.3 Servicio `domain/devoluciones/service.py::registrar_por_cancelacion` + hook en `transition()` para `confirmado→cancelado` (design D1) con `test_devolucion_alta.py`: en término → 100 % + `devolucion_solicitada` con actor (feliz); fuera de término → 60 %; límite exacto de anticipación → 100 %; **cancelación post-`inicio` con cotización 0 % → turno `cancelado` con historial y slot liberado, sin `devolucion`, sin `devolucion_solicitada`, sin recibo de devolución, sin `aviso_devolucion`, pago sigue `aprobado` y turno nunca pasa a `devuelto` (borde, `test_cancelacion_cero_sin_devolucion`)**; turno sin pago aprobado / `creado→cancelado` por sistema → sin devolución (error); fallo forzado al insertar → rollback y turno sigue `confirmado` (borde); `no_show` no crea devolución y `no_show→cancelado` → 422
- [x] 2.4 `POST /reservas/{id}/cancelar` devuelve la devolución persistida (`id`, `porcentaje`, `monto`, `estado`) o `null`; actualizar `test_reservas_cancelacion.py` (staff con pago aprobado, paciente con token, sin pago → `null`, cotización 0 % → `null`)
- [x] 2.5 `GET /mail/cancelar` deja `devolucion(pendiente)` y la página indica revisión con "(simulado)"; actualizar `test_api_mail.py` (válido con pago aprobado, turno no confirmado → sin transición, sin ejecución ni aprobación, cotización 0 % → sin `devolucion` ni `aviso_devolucion`)
- [x] 2.6 Checkpoint de revisión humana: alta de devolución en los tres orígenes de cancelación — **APROBADO por el usuario el 2026-11-16** (3 orígenes cubiertos: staff, paciente con token y mail; 0 % sin devolución; rollback probado)

## 3. Bandeja: lectura, aprobación y rechazo con RBAC

- [x] 3.1 `DevolucionRepository.scoped(ident)` (scope forzado en repositorio, P8) + `domain/devoluciones/estados.py` (tabla de transiciones app → 409) con tests unitarios de scope y de transiciones
- [x] 3.2 `api/devoluciones.py` `GET /api/devoluciones?estado=` y `GET /api/devoluciones/{id}` (schemas `extra='forbid'`, campo `marca`) + router en `main.py`; `test_devoluciones_bandeja.py`: recepcionista ve todas con "(simulado)" (feliz), odontólogo A → 403 en devolución de B (error), sin JWT → 401 / token de paciente → 403 / odontólogo sin `odontologo_id` → 403 (borde)
- [x] 3.3 `POST /api/devoluciones/{id}/aprobar` con `monto_confirmado`: aprobación registra `aprobada_por/at` + `evento_pago(devolucion_aprobada)` con actor y monto (feliz); monto distinto → 422 `MONTO_NO_COINCIDE` sin evento (error); aprobar `aprobada|rechazada|ejecutada` → 409 `TRANSICION_DEVOLUCION_INVALIDA`; 60 % sin acción queda `pendiente` (borde Q4); recepcionista aprueba devolución de otro profesional; odontólogo ajeno → 403 sin evento
- [x] 3.4 `POST /api/devoluciones/{id}/rechazar` con motivo obligatorio: rechazo registra `rechazada_por/at/motivo` + `evento_pago(devolucion_rechazada)`, turno `cancelado` y pago `aprobado` sin cambios (feliz); motivo vacío → 422 (error); rechazar `aprobada|ejecutada|rechazada` → 409 (borde); odontólogo ajeno → 403
- [x] 3.5 Verificar `test_rbac_matrix.py` / `test_public_routes.py`: las rutas nuevas exigen JWT staff y la lista de 6 rutas públicas no cambia (P12)
- [x] 3.6 Checkpoint de revisión humana: matriz RBAC de la bandeja — **APROBADO por el usuario el 2026-11-16** (scope P8 por JOIN turno, 403 vs 404 sin fuga de datos, 409/422 con evento solo tras validación)

## 4. Ejecución idempotente vía puerto + webhook

- [x] 4.1 Ampliar `ProveedorPago` con `ejecutar_devolucion` / `consultar_devolucion` y el adaptador simulado (`sim_refund_` + uuid5 de la `idempotency_key`, evento firmado HMAC con `kind=devolucion`); `test_pagos_proveedor.py`: misma key → mismo id sin mover dinero (feliz), consulta de key inexistente → no existe sin crearla (borde), firma inválida detectada (error)
- [x] 4.2 Separar idempotencia del webhook por `kind` (design D5) y agregar la rama devolución en el procesamiento compartido; `test_pagos_webhook.py`: webhook de devolución sobre pago ya aprobado se procesa (feliz), replay por `mp_refund_id` no duplica (P4), `mp_refund_id` de devolución no `aprobada` → error explícito con payload crudo persistido y sin efectos (borde); eventos C-07 sin `kind` siguen tratándose como pago
- [x] 4.3 Rama devolución: devolución `ejecutada` + `mp_refund_id`, pago `reembolsado_total|parcial`, `evento_pago(devolucion_ejecutada)` actor `sistema` con `solicitado_por`, `transition(cancelado→devuelto, sistema)` con historial; tests: 100 % → `reembolsado_total`, 60 % → `reembolsado_parcial` con monto original intacto, turno reprogramado → solo el turno cancelado pasa a `devuelto`, staff no puede pedir `cancelado→devuelto` (403)
- [x] 4.4 `POST /api/devoluciones/{id}/ejecutar` (design D4: `FOR UPDATE`, `ejecutada_por/at`, consultar antes de ejecutar); `test_devoluciones_ejecucion.py`: ejecución feliz con "(simulado)" (feliz), `pendiente` → 409 sin invocar proveedor (error), reintento devuelve mismo `mp_refund_id` sin segundo evento, dos ejecuciones concurrentes → una sola ejecución, `PAGO_MODO=mercadopago` → 503 `PROVEEDOR_NO_DISPONIBLE` y sigue `aprobada` sin fallback (borde), odontólogo ajeno → 403 sin invocar proveedor
- [x] 4.5 Checkpoint de revisión humana (CRÍTICO): flujo completo de ejecución e idempotencia — **APROBADO por el usuario el 2026-11-16** (flujo (a)–(e) auditado en código y tests; 503 sin fallback con rollback a `aprobada`; replay por `mp_refund_id` sin duplicar; P12 cubierto también para `/ejecutar`)

## 5. Comprobantes y PDF

- [x] 5.1 `domain/comprobantes/service.py` (`emitir_recibo_pago`, `emitir_recibo_devolucion`, idempotentes, `simulado` fijado al emitir, `tipo=recibo_interno`, `cae` null) enganchados en la rama `aprobado` del webhook y en la rama devolución; `test_comprobantes_emision.py`: aprobación emite un recibo (feliz), rechazo/expiración, devolución rechazada y cancelación con 0 % no emiten recibo de devolución (error), replay de webhook y reintento de ejecución no duplican; número correlativo distinto entre dos emisiones (borde)
- [x] 5.2 `domain/comprobantes/pdf.py` (PDF 1.4 stdlib, WinAnsi) con `test_comprobantes_pdf.py`: estructura válida (`%PDF-1.4`, xref, `%%EOF`) y datos del recibo (feliz), leyenda "SIMULADO — sin valor fiscal ni movimiento de dinero" presente si `simulado = true` aunque cambie `PAGO_MODO` (borde), ausente si `simulado = false` (error)
- [x] 5.3 `api/comprobantes.py` `GET /api/comprobantes/{id}` y `/pdf`: recepcionista descarga cualquiera (`application/pdf`), odontólogo ajeno → 403, sin JWT → 401, id inexistente → 404
- [ ] 5.4 Checkpoint de revisión humana: PDF de muestra simulado revisado a ojo

## 6. Aviso de devolución por mail con adjunto

- [x] 6.1 `SmtpMailer.enviar(..., adjuntos=None)` con stdlib; `test_smtp.py`: adjunto PDF viaja como `application/pdf` (feliz), sin adjuntos el mensaje no cambia (borde), `From` sigue alineado a `MAIL_FROM` (P14)
- [x] 6.2 Plantilla `aviso_devolucion` `v2` (monto, resultado, "(simulado)", "no se movió dinero real"; `v1` registrada para filas viejas) en `test_plantillas.py`: ejecutada en simulado (feliz), rechazada sin monto devuelto (error), HTML escapado (borde)
- [x] 6.3 `encolar_aviso_devolucion` con `monto/resultado/comprobante_id` invocado al ejecutar y al rechazar; worker adjunta el PDF regenerado; `test_outbox.py`/`test_worker.py`: ejecución encola un aviso con adjunto, rechazo sin adjunto, reintento de ejecución no duplica el aviso

## 7. Trazabilidad, conciliación y alertas

- [x] 7.1 `GET /api/turnos/{turno_id}/trazabilidad` (scope P8): turno devuelto con pago, devolución, ambos recibos y eventos ordenados con actor y fecha (feliz), odontólogo ajeno → 403 (error), turno sin pago → secciones vacías explícitas (borde)
- [x] 7.2 Conciliación con reembolsos (design D9) en `test_pagos_conciliacion.py`: pago `reembolsado_*` consistente sin alerta (feliz), pago `aprobado` de turno `cancelado`/`no_show` con 0 % sin devolución → sin alerta, discrepancia de pago sigue generando `conciliado` (error), devolución `ejecutada` con pago `aprobado` o turno no `devuelto` → alerta (borde)
- [x] 7.3 `GET /api/devoluciones/alertas` con scope P8 y "(simulado)": recepcionista y odontólogo dueño ven la alerta, odontólogo ajeno no; sin JWT → 401; sin discrepancias → lista vacía

## 8. Seed y verificación integral

- [x] 8.1 `seed_dev.py`: 1 pago aprobado con recibo + 1 devolución 60 % ejecutada con recibo (proveedor `simulado`, ids sintéticos, DNI ficticios P11), idempotente; actualizar `test_seed_dev.py`
- [x] 8.2 E2E F2 en `test_f2_devolucion_e2e.py`: reserva → aprobación simulada (recibo de pago) → cancelación fuera de término → bandeja aprueba → ejecuta → turno `devuelto`, pago `reembolsado_parcial`, dos recibos, un `aviso_devolucion`, trazabilidad completa y conciliación sin alertas
- [x] 8.3 Correr suite completa + `ruff` + `mypy` en verde y comparar contra el baseline de 1.1 (sin regresiones)

## Workflow follow-up

- Revisión humana final (governance CRÍTICO) antes de `/opsx:archive`.
- Al archivar: marcar `[x]` C-08 en `CHANGES.md` y actualizar la nota de C-09 (productor de `aviso_devolucion` integrado).
- Commits convencionales `feat(C-08): ...` por integrante, solo con pedido explícito (U1, P7).
