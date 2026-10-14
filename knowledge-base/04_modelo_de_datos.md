# 04 — Modelo de datos

**Proyecto**: turnos-odontología · **Fecha**: 2026-10-14 · **Fuente**: `discovery/discovery.md` (§5, §7–8)
Relacionadas: `05_reglas_de_negocio.md` (constraints), `11_pagos_mercadopago.md` (pago/comprobante/devolución/auditoría).

## 1. Principios de modelado

1. **Pago y comprobante viven separados del turno** (decisión cerrada): permite conciliación con MercadoPago en v1 y emisión ARCA en v2 sin refactorizar. Patrón: comprobante + link de pago + conciliación (inspiración ARCA-API/TusFacturasAPP, ver `09_decisiones_y_supuestos.md`).
2. **Constraints de dominio en DB**, no solo validación de UI: no-pasado, no-doble-reserva, no-solapamiento por profesional (ver RN-XX en `05_reglas_de_negocio.md`).
3. **Auditoría máxima día 1**: historial de estados del turno (actor + fecha) + audit trail append-only de eventos de pago (sin UPDATE/DELETE).
4. Single-sede v1 con `odontologo_id` como eje de aislamiento; modelo que no bloquea `sede_id` futura **[v2]**.

## 2. Entidades [v1]

- **paciente**: `id, dni (único), nombre, apellido, email, telefono, consentimiento_datos (bool + fecha), created_at`. Ficha mínima, nada clínico **[v1]**.
- **odontologo** (usuario): `id, user_id, nombre, especialidad, monto_turno, monto_senia, activo`. Montos configurables por odontólogo (decisión cerrada).
- **usuario** (auth): `id, email (único), password_hash, rol (odontologo | recepcionista | admin), odontologo_id (nullable, para aislamiento), activo`. Admin/recepcionista según RBAC de `03_actores_y_roles.md`.
- **disponibilidad**: `id, odontologo_id, dia_semana, hora_inicio, hora_fin, duracion_min, tope_dia, vigente_desde, vigente_hasta`. Genera slots ofrecibles.
- **bloqueo** (pausas/feriados/bloqueos por profesional): `id, odontologo_id, desde, hasta, motivo (pausa|feriado|bloqueo|vacaciones), created_by`.
- **turno**: `id, paciente_id, odontologo_id, inicio, fin, estado, canal (web|recepcion|mail), idempotency_key (única), created_at, version (lock optimista)`. Estados: `creado → confirmado → atendido | cancelado | reprogramado | no_show | devuelto` (ver máquina en `05_reglas_de_negocio.md`).
- **turno_historial**: `id, turno_id, estado_anterior, estado_nuevo, actor_tipo, actor_id, fecha, motivo`. Append-only.
- **pago** (separado del turno): `id, turno_id, odontologo_id, monto, moneda (ARS), proveedor (mercadopago), mp_payment_id (único, nullable), mp_preference_id, estado (pendiente|aprobado|rechazado|reembolsado_parcial|reembolsado_total), idempotency_key (única), created_at`.
- **devolucion** (bandeja): `id, pago_id, turno_id, monto, porcentaje (100|60|0), motivo, estado (pendiente|aprobada|rechazada|ejecutada), aprobada_por, aprobada_at, mp_refund_id, created_at`.
- **comprobante** (separado del turno; emisión ARCA apagada en v1): `id, pago_id, turno_id, tipo (recibo_interno [v1] | factura_arca [v2]), numero, cae (nullable [v2]), emitida_at, payload_json`.
- **evento_pago** (audit trail append-only): `id, pago_id, tipo_evento (creado|webhook_recibido|aprobado|rechazado|devolucion_solicitada|devolucion_aprobada|devolucion_ejecutada|conciliado), payload_json, actor, created_at`. Sin UPDATE ni DELETE (constraint/check a nivel rol DB).
- **recordatorio_mail**: `id, turno_id, tipo (confirmacion|recordatorio|aviso_devolucion), destinatario, plantilla_version, estado (encolado|enviado|reintentando|fallido|confirmado_desde_mail|cancelado_desde_mail), intentos, token_accion (hash único, expiración), created_at`.
- **lista_espera** **[v2, modelada apagada]**: `id, odontologo_id, paciente_id, desde, hasta, estado (activa|notificada|expirada|convertida)`. Tabla creada, sin escrituras en v1 salvo flag off.
- **notificacion_whatsapp** **[v2, modelada apagada]**: `id, turno_id, plantilla_version, estado`. Tabla creada, conector apagado.

## 3. ERD (texto)

```
usuario 1──0..1 odontologo 1──N disponibilidad
odontologo 1──N bloqueo | 1──N turno N──1 paciente
turno 1──N turno_historial (append-only)
turno 1──1 pago 1──N devolucion | 1──1 comprobante | 1──N evento_pago (append-only)
turno 1──N recordatorio_mail
odontologo 1──N lista_espera [v2] | turno 1──N notificacion_whatsapp [v2]
```

## 4. Relaciones y constraints clave

- `UNIQUE (odontologo_id, inicio)` + exclusion de solapamiento por profesional (rango tstzrange, PostgreSQL `EXCLUDE USING gist`) → no-doble-reserva / no-solapamiento.
- `CHECK (inicio > now())` a nivel servicio + DB (no-pasado) — ver RN-PASADO en `05_reglas_de_negocio.md`.
- `UNIQUE (dni)` en paciente (reconocimiento por DNI en reserva).
- `UNIQUE (idempotency_key)` en turno y pago (idempotencia en cobros/devoluciones, auditoría máxima día 1).
- `evento_pago` y `turno_historial`: revoke UPDATE/DELETE al rol de app.
- Aislamiento de agenda: toda query de odontólogo filtra `odontologo_id = current_user.odontologo_id` (forzado en capa repositorio).

## 5. Seed data (dev)

- 2 odontólogos con disponibilidad L–V 9–17, duración 30 min, tope 14/día, montos turno/seña distintos.
- 1 recepcionista + 1 admin demo; 5 pacientes con DNI ficticios; 10 turnos históricos en todos los estados; 1 pago aprobado + 1 devolución 60 % ejecutada; feriado + bloqueo de ejemplo.
