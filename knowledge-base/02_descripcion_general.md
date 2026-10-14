# 02 — Descripción general del sistema

**Proyecto**: turnos-odontología · **Fecha**: 2026-10-14 · **Fuente**: `discovery/discovery.md` (§8–9)
Relacionadas: `01_vision_y_objetivos.md`, `08_arquitectura_propuesta.md`, `11_pagos_mercadopago.md`.

## 1. Qué es

Aplicación web para gestión de turnos de un consultorio odontológico single-sede **[v1]**: los pacientes reservan online y pagan seña; los odontólogos gestionan disponibilidad y agenda; el rol admin/recepcionista (opcional) opera las agendas y la bandeja de devoluciones. Sin app móvil en v1.

## 2. Stack (obligatorio, restricción académica)

| Capa | Tecnología | Notas |
|---|---|---|
| Backend | Python + FastAPI | API REST + webhooks (MercadoPago, mail inbound) |
| Auth | JWT | Access tokens; refresh según `08_arquitectura_propuesta.md` |
| ORM | SQLAlchemy | Constraints de dominio a nivel DB (unicidad de slot, no-solapamiento) |
| DB | PostgreSQL | Transaccional; audit trail append-only |
| Async/colas | Redis | Colas + reintentos de mails; ventana de recordatorios; idempotencia |
| Infra | Docker / Docker Compose | Un compose para dev; env vars documentadas en `08_arquitectura_propuesta.md` |
| Frontend | React + TypeScript + Vite | SPA; flujo de reserva 3–4 pasos |
| Pagos **[v1]** | MercadoPago (proveedor sugerido v1) | Checkout + webhooks + conciliación; detalle en `11_pagos_mercadopago.md` |
| Mail **[v1]** | Proveedor SMTP con SPF/DKIM/DMARC | Única vía de recordatorio en v1; colas/reintentos en Redis |

## 3. Arquitectura general (resumen)

```
Paciente (SPA) ──HTTPS──▶ FastAPI ──▶ PostgreSQL (turnos, pagos, comprobantes, auditoría)
Odontólogo/Admin ──JWT──▶   │    ├──▶ Redis (colas mail, reintentos, locks/idempotencia)
                            │    ├──▶ MercadoPago API (checkout) ◀── webhooks MP ──┘
                            └──▶ SMTP saliente (recordatorios) + inbound (confirmar/cancelar desde el mail)
```

- Monolito modular en backend (ver estructura en `08_arquitectura_propuesta.md`); frontend SPA desacoplado.
- Pagos y comprobantes como entidades separadas del turno (puente ARCA v2 sin refactorizar).
- Conector de WhatsApp **[v2]** y sync de calendario externo **[v2]**: interfaces modeladas, implementaciones apagadas.

## 4. Integraciones

| Integración | Alcance | Estado |
|---|---|---|
| MercadoPago (checkout + webhooks + devoluciones) | Seña al reservar; bandeja de devoluciones; conciliación | [v1] (monto a definir, ver `10_preguntas_abiertas.md`) |
| Mail transaccional + recordatorios | Confirmación inmediata, recordatorios con confirmar/cancelar desde el mail, avisos de devolución | [v1] con spec de entregabilidad |
| WhatsApp Business API | Conector + plantillas modelados | [v2] apagado |
| Calendario externo (tipo Google) | Sync que bloquee huecos ocupado/no disponible | [v2] diseñado, no construido |
| ARCA / Obras sociales | Comprobante separado del turno; emisión automática | [v2] post-v1 |
| App móvil / APIs clínicas | — | Fuera de v1 |

## 5. Cumplimiento y seguridad mínimos desde v1

Consentimiento del paciente para tratamiento de datos; política de retención; cifrado declarado de datos sensibles; backups periódicos; trazabilidad de devoluciones. El mercado local casi nunca documenta estos puntos (cifrado, backups, Ley 25.326 y Ley 26.529 figuran como **No evidenciado** en la mayoría de los relevados), por lo que se diseñan explícitamente aunque el dictamen legal exceda el alcance académico. Detalle en `08_arquitectura_propuesta.md` y supuestos en `09_decisiones_y_supuestos.md`.
