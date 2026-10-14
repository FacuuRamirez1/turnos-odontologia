# 01 — Visión y objetivos

**Proyecto**: turnos-odontología · **Fecha**: 2026-10-14 · **Fuente**: `discovery/discovery.md` + `discovery/analisis-mercado.md`
**Convención de alcance**: cada ítem lleva etiqueta **[v1]** (se construye ahora) o **[v2]** (modelado pero apagado / post-v1). Ver también `06_funcionalidades.md`, `09_decisiones_y_supuestos.md`, `10_preguntas_abiertas.md`.

## 1. Propósito

Reemplazar la coordinación informal de turnos (papel, WhatsApp informal, planillas dispersas) por un sistema web simple para el **consultorio odontológico chico single-sede** argentino, que una en un mismo flujo: agenda por odontólogo, reserva online de baja fricción, seña con reglas de devolución explícitas y recordatorios bien hechos **[v1]**.

El relevamiento de mercado confirma el hueco: el mercado empuja soluciones multi-sede/enterprise (Dentalink, Doctoralia), mientras nadie une agenda por odontólogo + reserva simple + seña con devolución + recordatorios en un flujo simple para el consultorio chico (ver `09_decisiones_y_supuestos.md`).

## 2. Objetivos por actor

| Actor | Objetivo | Alcance |
|---|---|---|
| Paciente | Reservar un turno disponible sin llamar, en 3–4 pasos, con confirmación inmediata | [v1] |
| Paciente | Cancelar/reprogramar liberando el hueco, viendo las reglas de seña al momento de la acción | [v1] |
| Odontólogo | Ver su agenda del día (aislada por profesional) y atender sin choques | [v1] |
| Odontólogo | Cargar su disponibilidad (duración, tope/día, pausas, feriados, bloqueos) | [v1] |
| Odontólogo | Gestionar cancelaciones/reprogramaciones con historial de estados (actor + fecha) | [v1] |
| Recepcionista/Admin (opcional) | Operar agendas del consultorio, cancelaciones y bandeja de devoluciones con permisos explícitos | [v1] |
| Consultorio | Cobrar seña al reservar vía MercadoPago con trazabilidad y comprobantes | [v1] |
| Consultorio | Reducir ausentismo con recordatorios por mail de alta entregabilidad | [v1] |
| Consultorio | Exportar turnos y caja (CSV/PDF) y ver reportes mínimos de asistencia | [v1] |
| Consultorio | Facturar con ARCA / gestionar obras sociales | [v2] post-v1 |
| Consultorio | Recordar por WhatsApp, publicar portal de reservas, sincronizar calendario externo | [v2] |
| Consultorio | Historia clínica / odontograma completo | [v2] |

## 3. Alcance v1 (se construye)

- Reserva online flujo canónico 3–4 pasos (datos → profesional → fecha/hora → confirmación) con reconocimiento por DNI y confirmación inmediata por mail **[v1]**.
- Agenda del día por odontólogo con aislamiento por profesional y constraints de dominio anti-choque **[v1]**.
- Cancelación/reprogramación (paciente y odontólogo/admin) con liberación automática del hueco **[v1]**.
- Seña real vía MercadoPago (proveedor sugerido v1): monto del turno y de la seña configurables por odontólogo; se paga al reservar; devolución 100 % en término / 60 % fuera de término / 0 % no-show; bandeja de devoluciones con comprobante y trazabilidad **[v1]**.
- Recordatorios automáticos **por mail** (única vía v1): SPF/DKIM/DMARC, colas/reintentos con Redis, plantillas versionadas, ventana configurable, confirmar/cancelar desde el propio mail **[v1]**.
- Historial de estados por turno (actor + fecha), auditoría máxima día 1: idempotencia en cobros/devoluciones, exportación CSV/PDF, audit trail append-only de eventos de pago **[v1]**.
- Ficha de paciente mínima + historial de turnos acotado (nada clínico) **[v1]**.
- Single-sede con aislamiento de agenda por odontólogo; precio y trial públicos desde día uno **[v1]**.

## 4. Fuera de alcance v1 → [v2] (modelado pero apagado)

| Ítem | Estado v1 | Condición de encendido |
|---|---|---|
| WhatsApp (recordatorios/confirmación/bot) | Conector + plantillas modelados, apagados | v2 |
| Multi-sede | Single-sede; modelo que no bloquea multi-sede futura | v2+ |
| Sobre-turnos | Fuera de v1 consciente; slots/estados modelados | v2 |
| Lista de espera | Modelada (estados/slots), apagada | v2 |
| Obras sociales + ARCA automática | Comprobante modelado separado del turno; emisión apagada | v2 post-v1 (orden pendiente, ver `10_preguntas_abiertas.md`) |
| Calendario externo (tipo Google) | Diseñado, no construido (sync que bloquee huecos) | v2 |
| Portal/link público de reserva por consultorio | Oportunidad v2 (referencia Gendu/DentiClick/MedicAI) | v2 |
| Odontograma / periodontograma / HC completa | Fuera de v1 (excede plazo académico) | v2+ |
| Métrica propia de ausentismo | Solo si el proyecto sale del ámbito académico | v2+ |
| App móvil, campañas/IA | v2 o posterior | v2+ |

## 5. Criterios de éxito v1

1. Un paciente puede reservar → pagar seña → recibir confirmación por mail sin intervención del consultorio.
2. Ningún slot se doble-reserva aunque haya concurrencia (constraints de dominio, no solo UI).
3. Toda transición de turno y todo cobro/devolución deja rastro auditable (actor + fecha; eventos de pago append-only).
4. Los recordatorios por mail llegan (métricas de entrega) y confirmar/cancelar desde el mail actualiza la agenda.
5. El recorte se sostiene: nada de lo listado en §4 se construye en v1, solo se modela lo indicado.
