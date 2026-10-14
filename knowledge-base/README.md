# Knowledge Base — turnos-odontología

Índice navegable. Fuente primaria: `../discovery/discovery.md` (+ `../discovery/analisis-mercado.md` para fundamentos; lo no evidenciado se marca como tal). Convención: **[v1]** se construye · **[v2]** modelado/apagado o post-v1.

| # | Archivo | Contenido |
|---|---|---|
| 01 | `01_vision_y_objetivos.md` | Propósito, objetivos por actor, alcance v1 / fuera de alcance (v2), criterios de éxito |
| 02 | `02_descripcion_general.md` | Stack (FastAPI/JWT/SQLAlchemy/PostgreSQL/Redis/Docker + React/TS/Vite), arquitectura general, MP + mail |
| 03 | `03_actores_y_roles.md` | 3 roles, tabla RBAC exigible en backend, permisos explícitos de recepcionista, rutas públicas |
| 04 | `04_modelo_de_datos.md` | Entidades (pago y comprobante separados del turno, devolución, evento auditoría), ERD en texto, constraints, seed |
| 05 | `05_reglas_de_negocio.md` | Reglas RN-XX: anticipación, duración, tope, pausas/feriados/bloqueos, liberación automática, no-pasado/no-doble/no-solape, seña 100/60/0, máquina de estados con actor+fecha |
| 06 | `06_funcionalidades.md` | Épicas A–G e historias: reserva 3–4 pasos + DNI + confirmación, agenda, seña, mail, reportes, ficha mínima, exportación |
| 07 | `07_flujos_principales.md` | Reserva end-to-end, cancelación con devolución, reprogramación, recordatorio por mail (Redis, confirmar/cancelar desde el mail), webhook MP + conciliación |
| 08 | `08_arquitectura_propuesta.md` | Patrones, directorios, JWT, env vars, Compose, SPF/DKIM/DMARC a nivel config |
| 09 | `09_decisiones_y_supuestos.md` | Decisiones D1–D13 con fundamento de mercado + supuestos marcados con **Suposición:** |
| 10 | `10_preguntas_abiertas.md` | Monto fijo, proveedor MP, orden de v2, inconsistencias, ítems [DISCOVERY] |
| 11 | `11_pagos_mercadopago.md` | MP a fondo: checkout, webhooks, idempotencia, bandeja, comprobantes, conciliación, audit trail |

**Decisiones cerradas (resumen)**: v1 completo junto · velocidad sin romper trazabilidad · auditoría máxima día 1 · enfoque B v1/v2 · montos configurables por odontólogo, seña al reservar, 100/60/0 · MP sugerido v1 · mail-only v1 · single-sede · sin sobre-turnos · OS/ARCA v2 post-v1 · precio/trial públicos.
