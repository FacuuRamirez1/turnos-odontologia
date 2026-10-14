# 07 — Flujos principales

**Proyecto**: turnos-odontología · **Fecha**: 2026-10-14 · **Fuente**: `discovery/discovery.md` (§3, §5, §7–8)
Relacionadas: `05_reglas_de_negocio.md`, `11_pagos_mercadopago.md`, `08_arquitectura_propuesta.md`.

## F1. Reserva end-to-end [v1]

1. Paciente ingresa datos (DNI → reconocimiento si existe) → elige profesional → elige fecha/hora entre slots ofrecibles (RN-DURACION/TOPE/PAUSAS) → ve monto turno + seña → confirma.
2. Backend crea `turno` en estado `creado` con `idempotency_key` + pre-reserva del slot con TTL (expira si no hay pago; RN-LIBERACION).
3. Se crea `pago` pendiente + preferencia de MercadoPago; el paciente paga (checkout MP).
4. Webhook MP (firma + idempotencia, ver `11_pagos_mercadopago.md`) → pago `aprobado` → turno `confirmado` → mail de confirmación inmediata.
5. Si el pago es rechazado o expira la pre-reserva: turno `cancelado` (motivo: pago fallido), slot liberado, aviso por mail.

## F2. Cancelación con devolución [v1]

1. Paciente (web o link del mail) u odontólogo/recepcionista inicia cancelación; el sistema muestra la regla aplicable **antes** de confirmar: en término → 100 % (RN-SENIA-100), fuera de término → 60 % (RN-SENIA-60).
2. Al confirmar: turno `cancelado`, slot liberado en el mismo commit (RN-LIBERACION), `devolucion` creada en `pendiente` con porcentaje calculado.
3. Rol autorizado aprueba en bandeja (actor + fecha + monto) → ejecución contra MP (`mp_refund_id`) → devolucion `ejecutada` → turno `devuelto` → mail con comprobante.
4. Toda devolución es idempotente (reintentos seguros) y deja eventos append-only (RN-BANDEJA, RN-AUDIT).

## F3. Reprogramación [v1]

1. Se elige el turno `confirmado` + nuevo slot libre (validado contra RN-PASADO/DOBLE/SOLAPE/ANTICIPACION).
2. En un solo acto: turno pasa a `reprogramado` con historial (actor + fecha) y se crea el nuevo turno `confirmado` heredando el `pago` (sin nuevo cobro; si hay diferencia de monto → pregunta abierta en `10_preguntas_abiertas.md`).
3. Mails: aviso de cambio + recordatorio reprogramado a la nueva ventana.

## F4. Recordatorio por mail [v1]

1. Job Redis (scheduler) detecta turnos `confirmado` dentro de la ventana configurable (p. ej. 24 h) sin recordatorio enviado.
2. Encola en Redis con plantilla versionada; envío SMTP; reintentos con backoff (3 intentos) → estados `encolado|enviado|reintentando|fallido`.
3. El mail incluye **confirmar** y **cancelar** (tokens firmados, un uso, expiración corta): confirmar → turno sigue `confirmado` + marca `confirmado_desde_mail`; cancelar → deriva a F2 mostrando la regla de seña.
4. Métricas de entrega (enviados, rebotes, aperturas si el proveedor las da) visibles para el consultorio; spec SPF/DKIM/DMARC a nivel config (ver `08_arquitectura_propuesta.md`).
5. WhatsApp **[v2]**: mismo evento, conector apagado; al encenderse, reutiliza `turno_id` + `plantilla_version` sin migraciones.

## F5. Webhook MercadoPago + conciliación [v1]

1. `POST /webhooks/mercadopago` valida firma → registra `evento_pago(webhook_recibido)` → procesa por `mp_payment_id` con idempotencia (replay seguro).
2. Concilia: `pago.estado` vs. estado MP; discrepancias → alerta en bandeja + evento `conciliado` con detalle.
3. Devoluciones ejecutadas contra API MP con `idempotency_key`; `mp_refund_id` guardado; reintentos solo re-ejecutan consulta, nunca duplican (ver `11_pagos_mercadopago.md`).
