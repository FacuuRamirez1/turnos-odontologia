# Tasks â€” c-08-devoluciones-comprobantes-conciliacion

> **Governance CRÃTICO**: cada grupo cierra con checkpoint de revisiÃ³n humana antes de seguir. TDD (U2) en cada tarea: SAFETY NET (tests existentes del archivo a tocar) â†’ RED â†’ GREEN â†’ TRIANGULATE con 3 escenarios (feliz / error de negocio / borde) â†’ REFACTOR. Los tests viven en su grupo, no al final. Q4 queda abierta: **no** se implementa auto-aprobaciÃ³n ni umbral.

## 1. MigraciÃ³n 006 + modelos Devolucion/Comprobante

- [x] 1.1 Safety net: correr `test_pagos_migration_005.py`, `test_pagos_modelos.py`, `test_pagos_webhook.py`, `test_pagos_conciliacion.py`, `test_reservas_cancelacion.py`, `test_turno_transiciones.py`, `test_api_mail.py`, `test_plantillas.py`, `test_smtp.py`, `test_worker.py` y registrar el baseline (N passing); si algo falla, frenar y reportar como pre-existente
- [x] 1.2 RED: `test_migration_006.py` â€” upgrade sobre head `005` deja `alembic current` = `006_devolucion_comprobante`; downgrade restaura el CHECK original de `evento_pago`; downgrade aborta si existen eventos `devolucion_rechazada`
- [x] 1.3 GREEN: crear `backend/alembic/versions/006_devolucion_comprobante.py` (design D3/D6/D10: tablas, UNIQUE totales y parciales, CHECKs â€”`porcentaje IN (100,60)` y `monto > 0`â€”, triggers de transiciÃ³n y de `monto <= pago.monto`, secuencia de nÃºmero, CHECK de `evento_pago` con `devolucion_rechazada`, Ã­ndices, grants y `REVOKE UPDATE, DELETE` sobre `comprobante`); cero `create_all` (P3); verificar 1.2 en verde
- [x] 1.4 Modelos `infra/db/models/devolucion.py` y `comprobante.py` (+ export en `models/__init__.py`, `TIPOS_EVENTO_PAGO` con `devolucion_rechazada`) y `test_devolucion_modelos.py` con inserciones adversas directas a DB: segunda devoluciÃ³n por pago rechazada, `porcentaje = 0` y `porcentaje = 50` rechazados, `monto` > pago, `monto = 0` o negativo rechazado, retroceso `ejecutadaâ†’pendiente` rechazado por trigger, `ejecutada` sin `mp_refund_id` rechazado, UPDATE/DELETE de `comprobante` denegado al rol app, `evento_pago(devolucion_rechazada)` aceptado
- [x] 1.5 Checkpoint de revisiÃ³n humana (CRÃTICO): presentar migraciÃ³n + resultado de tests adversos â€” **APROBADO por el usuario el 2026-11-16** (migraciÃ³n `006_devolucion_comprobante` aplicada; `test_devolucion_modelos.py` 17 casos + `test_migration_006.py` 7 casos, 30 passed)

## 2. CÃ¡lculo y alta de la devoluciÃ³n al cancelar

- [x] 2.1 REDâ†’GREENâ†’TRIANGULATE `domain/devoluciones/calculo.py::calcular_monto_devolucion` en `test_devolucion_calculo.py`: 100 % de 10000.00 = 10000.00 (feliz), 60 % de 3333.33 = 2000.00 half-up (borde), porcentaje 0 o 50 â†’ error de dominio (error; el 0 % nunca llega al cÃ¡lculo)
- [x] 2.2 Extraer `resolver_pago_de_turno` (lÃ³gica hoy inline en `reprogramar`) y cubrirlo: turno con `pago_id`, turno sin `pago_id` resuelto por `pago.turno_id`, turno sin pago â†’ `None`; verificar `test_reservas_reprogramacion.py` sigue en verde
- [x] 2.3 Servicio `domain/devoluciones/service.py::registrar_por_cancelacion` + hook en `transition()` para `confirmadoâ†’cancelado` (design D1) con `test_devolucion_alta.py`: en tÃ©rmino â†’ 100 % + `devolucion_solicitada` con actor (feliz); fuera de tÃ©rmino â†’ 60 %; lÃ­mite exacto de anticipaciÃ³n â†’ 100 %; **cancelaciÃ³n post-`inicio` con cotizaciÃ³n 0 % â†’ turno `cancelado` con historial y slot liberado, sin `devolucion`, sin `devolucion_solicitada`, sin recibo de devoluciÃ³n, sin `aviso_devolucion`, pago sigue `aprobado` y turno nunca pasa a `devuelto` (borde, `test_cancelacion_cero_sin_devolucion`)**; turno sin pago aprobado / `creadoâ†’cancelado` por sistema â†’ sin devoluciÃ³n (error); fallo forzado al insertar â†’ rollback y turno sigue `confirmado` (borde); `no_show` no crea devoluciÃ³n y `no_showâ†’cancelado` â†’ 422
- [x] 2.4 `POST /reservas/{id}/cancelar` devuelve la devoluciÃ³n persistida (`id`, `porcentaje`, `monto`, `estado`) o `null`; actualizar `test_reservas_cancelacion.py` (staff con pago aprobado, paciente con token, sin pago â†’ `null`, cotizaciÃ³n 0 % â†’ `null`)
- [x] 2.5 `GET /mail/cancelar` deja `devolucion(pendiente)` y la pÃ¡gina indica revisiÃ³n con "(simulado)"; actualizar `test_api_mail.py` (vÃ¡lido con pago aprobado, turno no confirmado â†’ sin transiciÃ³n, sin ejecuciÃ³n ni aprobaciÃ³n, cotizaciÃ³n 0 % â†’ sin `devolucion` ni `aviso_devolucion`)
- [x] 2.6 Checkpoint de revisiÃ³n humana: alta de devoluciÃ³n en los tres orÃ­genes de cancelaciÃ³n â€” **APROBADO por el usuario el 2026-11-16** (3 orÃ­genes cubiertos: staff, paciente con token y mail; 0 % sin devoluciÃ³n; rollback probado)

## 3. Bandeja: lectura, aprobaciÃ³n y rechazo con RBAC

- [x] 3.1 `DevolucionRepository.scoped(ident)` (scope forzado en repositorio, P8) + `domain/devoluciones/estados.py` (tabla de transiciones app â†’ 409) con tests unitarios de scope y de transiciones
- [x] 3.2 `api/devoluciones.py` `GET /api/devoluciones?estado=` y `GET /api/devoluciones/{id}` (schemas `extra='forbid'`, campo `marca`) + router en `main.py`; `test_devoluciones_bandeja.py`: recepcionista ve todas con "(simulado)" (feliz), odontÃ³logo A â†’ 403 en devoluciÃ³n de B (error), sin JWT â†’ 401 / token de paciente â†’ 403 / odontÃ³logo sin `odontologo_id` â†’ 403 (borde)
- [x] 3.3 `POST /api/devoluciones/{id}/aprobar` con `monto_confirmado`: aprobaciÃ³n registra `aprobada_por/at` + `evento_pago(devolucion_aprobada)` con actor y monto (feliz); monto distinto â†’ 422 `MONTO_NO_COINCIDE` sin evento (error); aprobar `aprobada|rechazada|ejecutada` â†’ 409 `TRANSICION_DEVOLUCION_INVALIDA`; 60 % sin acciÃ³n queda `pendiente` (borde Q4); recepcionista aprueba devoluciÃ³n de otro profesional; odontÃ³logo ajeno â†’ 403 sin evento
- [x] 3.4 `POST /api/devoluciones/{id}/rechazar` con motivo obligatorio: rechazo registra `rechazada_por/at/motivo` + `evento_pago(devolucion_rechazada)`, turno `cancelado` y pago `aprobado` sin cambios (feliz); motivo vacÃ­o â†’ 422 (error); rechazar `aprobada|ejecutada|rechazada` â†’ 409 (borde); odontÃ³logo ajeno â†’ 403
- [x] 3.5 Verificar `test_rbac_matrix.py` / `test_public_routes.py`: las rutas nuevas exigen JWT staff y la lista de 6 rutas pÃºblicas no cambia (P12)
- [x] 3.6 Checkpoint de revisiÃ³n humana: matriz RBAC de la bandeja â€” **APROBADO por el usuario el 2026-11-16** (scope P8 por JOIN turno, 403 vs 404 sin fuga de datos, 409/422 con evento solo tras validaciÃ³n)

## 4. EjecuciÃ³n idempotente vÃ­a puerto + webhook

- [x] 4.1 Ampliar `ProveedorPago` con `ejecutar_devolucion` / `consultar_devolucion` y el adaptador simulado (`sim_refund_` + uuid5 de la `idempotency_key`, evento firmado HMAC con `kind=devolucion`); `test_pagos_proveedor.py`: misma key â†’ mismo id sin mover dinero (feliz), consulta de key inexistente â†’ no existe sin crearla (borde), firma invÃ¡lida detectada (error)
- [x] 4.2 Separar idempotencia del webhook por `kind` (design D5) y agregar la rama devoluciÃ³n en el procesamiento compartido; `test_pagos_webhook.py`: webhook de devoluciÃ³n sobre pago ya aprobado se procesa (feliz), replay por `mp_refund_id` no duplica (P4), `mp_refund_id` de devoluciÃ³n no `aprobada` â†’ error explÃ­cito con payload crudo persistido y sin efectos (borde); eventos C-07 sin `kind` siguen tratÃ¡ndose como pago
- [x] 4.3 Rama devoluciÃ³n: devoluciÃ³n `ejecutada` + `mp_refund_id`, pago `reembolsado_total|parcial`, `evento_pago(devolucion_ejecutada)` actor `sistema` con `solicitado_por`, `transition(canceladoâ†’devuelto, sistema)` con historial; tests: 100 % â†’ `reembolsado_total`, 60 % â†’ `reembolsado_parcial` con monto original intacto, turno reprogramado â†’ solo el turno cancelado pasa a `devuelto`, staff no puede pedir `canceladoâ†’devuelto` (403)
- [x] 4.4 `POST /api/devoluciones/{id}/ejecutar` (design D4: `FOR UPDATE`, `ejecutada_por/at`, consultar antes de ejecutar); `test_devoluciones_ejecucion.py`: ejecuciÃ³n feliz con "(simulado)" (feliz), `pendiente` â†’ 409 sin invocar proveedor (error), reintento devuelve mismo `mp_refund_id` sin segundo evento, dos ejecuciones concurrentes â†’ una sola ejecuciÃ³n, `PAGO_MODO=mercadopago` â†’ 503 `PROVEEDOR_NO_DISPONIBLE` y sigue `aprobada` sin fallback (borde), odontÃ³logo ajeno â†’ 403 sin invocar proveedor
- [x] 4.5 Checkpoint de revisiÃ³n humana (CRÃTICO): flujo completo de ejecuciÃ³n e idempotencia â€” **APROBADO por el usuario el 2026-11-16** (flujo (a)â€“(e) auditado en cÃ³digo y tests; 503 sin fallback con rollback a `aprobada`; replay por `mp_refund_id` sin duplicar; P12 cubierto tambiÃ©n para `/ejecutar`)

## 5. Comprobantes y PDF

- [x] 5.1 `domain/comprobantes/service.py` (`emitir_recibo_pago`, `emitir_recibo_devolucion`, idempotentes, `simulado` fijado al emitir, `tipo=recibo_interno`, `cae` null) enganchados en la rama `aprobado` del webhook y en la rama devoluciÃ³n; `test_comprobantes_emision.py`: aprobaciÃ³n emite un recibo (feliz), rechazo/expiraciÃ³n, devoluciÃ³n rechazada y cancelaciÃ³n con 0 % no emiten recibo de devoluciÃ³n (error), replay de webhook y reintento de ejecuciÃ³n no duplican; nÃºmero correlativo distinto entre dos emisiones (borde)
- [x] 5.2 `domain/comprobantes/pdf.py` (PDF 1.4 stdlib, WinAnsi) con `test_comprobantes_pdf.py`: estructura vÃ¡lida (`%PDF-1.4`, xref, `%%EOF`) y datos del recibo (feliz), leyenda "SIMULADO â€” sin valor fiscal ni movimiento de dinero" presente si `simulado = true` aunque cambie `PAGO_MODO` (borde), ausente si `simulado = false` (error)
- [x] 5.3 `api/comprobantes.py` `GET /api/comprobantes/{id}` y `/pdf`: recepcionista descarga cualquiera (`application/pdf`), odontÃ³logo ajeno â†’ 403, sin JWT â†’ 401, id inexistente â†’ 404
- [ ] 5.4 Checkpoint de revisiÃ³n humana: PDF de muestra simulado revisado a ojo

## 6. Aviso de devoluciÃ³n por mail con adjunto

- [ ] 6.1 `SmtpMailer.enviar(..., adjuntos=None)` con stdlib; `test_smtp.py`: adjunto PDF viaja como `application/pdf` (feliz), sin adjuntos el mensaje no cambia (borde), `From` sigue alineado a `MAIL_FROM` (P14)
- [ ] 6.2 Plantilla `aviso_devolucion` `v2` (monto, resultado, "(simulado)", "no se moviÃ³ dinero real"; `v1` registrada para filas viejas) en `test_plantillas.py`: ejecutada en simulado (feliz), rechazada sin monto devuelto (error), HTML escapado (borde)
- [ ] 6.3 `encolar_aviso_devolucion` con `monto/resultado/comprobante_id` invocado al ejecutar y al rechazar; worker adjunta el PDF regenerado; `test_outbox.py`/`test_worker.py`: ejecuciÃ³n encola un aviso con adjunto, rechazo sin adjunto, reintento de ejecuciÃ³n no duplica el aviso

## 7. Trazabilidad, conciliaciÃ³n y alertas

- [ ] 7.1 `GET /api/turnos/{turno_id}/trazabilidad` (scope P8): turno devuelto con pago, devoluciÃ³n, ambos recibos y eventos ordenados con actor y fecha (feliz), odontÃ³logo ajeno â†’ 403 (error), turno sin pago â†’ secciones vacÃ­as explÃ­citas (borde)
- [ ] 7.2 ConciliaciÃ³n con reembolsos (design D9) en `test_pagos_conciliacion.py`: pago `reembolsado_*` consistente sin alerta (feliz), pago `aprobado` de turno `cancelado`/`no_show` con 0 % sin devoluciÃ³n â†’ sin alerta, discrepancia de pago sigue generando `conciliado` (error), devoluciÃ³n `ejecutada` con pago `aprobado` o turno no `devuelto` â†’ alerta (borde)
- [ ] 7.3 `GET /api/devoluciones/alertas` con scope P8 y "(simulado)": recepcionista y odontÃ³logo dueÃ±o ven la alerta, odontÃ³logo ajeno no; sin JWT â†’ 401; sin discrepancias â†’ lista vacÃ­a

## 8. Seed y verificaciÃ³n integral

- [ ] 8.1 `seed_dev.py`: 1 pago aprobado con recibo + 1 devoluciÃ³n 60 % ejecutada con recibo (proveedor `simulado`, ids sintÃ©ticos, DNI ficticios P11), idempotente; actualizar `test_seed_dev.py`
- [ ] 8.2 E2E F2 en `test_f2_devolucion_e2e.py`: reserva â†’ aprobaciÃ³n simulada (recibo de pago) â†’ cancelaciÃ³n fuera de tÃ©rmino â†’ bandeja aprueba â†’ ejecuta â†’ turno `devuelto`, pago `reembolsado_parcial`, dos recibos, un `aviso_devolucion`, trazabilidad completa y conciliaciÃ³n sin alertas
- [ ] 8.3 Correr suite completa + `ruff` + `mypy` en verde y comparar contra el baseline de 1.1 (sin regresiones)

## Workflow follow-up

- RevisiÃ³n humana final (governance CRÃTICO) antes de `/opsx:archive`.
- Al archivar: marcar `[x]` C-08 en `CHANGES.md` y actualizar la nota de C-09 (productor de `aviso_devolucion` integrado).
- Commits convencionales `feat(C-08): ...` por integrante, solo con pedido explÃ­cito (U1, P7).
