# 05 — Reglas de negocio

**Proyecto**: turnos-odontología · **Fecha**: 2026-10-14 · **Fuente**: `discovery/discovery.md` (§7)
Relacionadas: `04_modelo_de_datos.md`, `07_flujos_principales.md`, `11_pagos_mercadopago.md`.
Código: **RN-XX**. Todas **[v1]** salvo marca explícita.

## 1. Disponibilidad y slots

- **RN-DURACION [v1]**: cada odontólogo define duración estándar del turno (minutos). Los slots ofrecibles son múltiplos exactos desde `hora_inicio`.
- **RN-TOPE [v1]**: tope de turnos por día por odontólogo; alcanzado el tope, no se ofrecen más slots ese día.
- **RN-PAUSAS [v1]**: pausas, feriados y bloqueos por profesional quitan slots ofrecibles (tabla `bloqueo`: pausa|feriado|bloqueo|vacaciones).
- **RN-ANTICIPACION [v1]**: anticipación mínima configurable para reservar y para cancelar/reprogramar (p. ej. 24 h). Fuera de término aplica RN-SENIA-60.
- **RN-LIBERACION [v1]**: el hueco liberado por cancelación/reprogramación vuelve a estar disponible automáticamente (mismo commit que cambia el estado).

## 2. Constraints de dominio (DB, no solo UI)

- **RN-PASADO [v1]**: prohibido reservar en el pasado (`inicio > now()`).
- **RN-DOBLE [v1]**: prohibida la doble-reserva del mismo slot (`UNIQUE (odontologo_id, inicio)`).
- **RN-SOLAPE [v1]**: prohibido solapar turnos del mismo profesional (exclusión de rangos).
- **RN-AISLAMIENTO [v1]**: un odontólogo solo opera su agenda/disponibilidad (`odontologo_id` forzado); ver RBAC en `03_actores_y_roles.md`.

## 3. Seña y devoluciones (decisión cerrada)

- **RN-SENIA-PAGO [v1]**: la seña se paga al reservar vía MercadoPago (proveedor sugerido v1). Monto del turno y de la seña configurables por odontólogo. Sin pago aprobado, la reserva no queda confirmada (ver flujo en `07_flujos_principales.md`).
- **RN-SENIA-100 [v1]**: cancela en término (dentro de anticipación) → devolución del 100 %.
- **RN-SENIA-60 [v1]**: cancela fuera de término → devolución del 60 %.
- **RN-SENIA-0 [v1]**: no-show → 0 % devolución.
- **RN-BANDEJA [v1]**: toda devolución pasa por la bandeja con comprobante y trazabilidad (quién aprobó, cuándo, qué monto). Idempotencia en cobros y devoluciones (auditoría máxima día 1).
- **RN-COMPROBANTE [v1/v2]**: en v1 se emite recibo interno; el comprobante vive separado del turno para que ARCA **[v2]** no exija refactorización.

## 4. Máquina de estados del turno [v1]

```
creado → confirmado → atendido
   │          ├──→ cancelado → devuelto (100/60/0 según RN-SENIA-*)
   │          ├──→ reprogramado → confirmado (nuevo slot)
   │          └──→ no_show (0 %)
```

- **RN-ESTADOS [v1]**: cada transición guarda **actor + fecha** en `turno_historial` (constraints de dominio: trigger/check que rechaza transiciones sin actor).
- Transiciones permitidas (origen → destino, actor): creado→confirmado (sistema/MP webhook); confirmado→cancelado (paciente/odontólogo/recepcionista); confirmado→reprogramado (idem, exige nuevo slot libre en el mismo acto); confirmado→atendido (odontólogo/recepcionista); confirmado→no_show (odontólogo/recepcionista, posterior a `fin`); cancelado→devuelto (sistema tras devolución ejecutada).
- **RN-SOBRETURNO [v2]**: sin sobre-turnos en v1 (recorte consciente). **RN-ESPERA [v2]**: lista de espera modelada, apagada.

## 5. Recordatorios [v1]

- **RN-RECORDATORIO [v1]**: ventana de envío configurable (p. ej. 24 h antes); mail con confirmar/cancelar que actualiza la agenda; reintentos con backoff en Redis (ver `07_flujos_principales.md`).

## 6. Cumplimiento [v1]

- **RN-CONSENTIMIENTO [v1]**: sin consentimiento registrado no se persiste ficha de paciente.
- **RN-RETENCION [v1]**: política de retención de datos y turnos publicada y aplicada por job.
- **RN-AUDIT [v1]**: eventos de pago append-only; exportación CSV/PDF de turnos y caja disponible para roles autorizados.
