# 06 — Funcionalidades (épicas e historias)

**Proyecto**: turnos-odontología · **Fecha**: 2026-10-14 · **Fuente**: `discovery/discovery.md` (§3, §5–6)
Relacionadas: `01_vision_y_objetivos.md`, `05_reglas_de_negocio.md`, `07_flujos_principales.md`.
Etiqueta de alcance en cada historia: **[v1]** / **[v2]**.

## Épica A — Reserva online [v1]

- **A1**: como paciente, reservo en flujo canónico 3–4 pasos (datos → profesional → fecha/hora → confirmación) para no llamar **[v1]**.
- **A2**: como paciente existente, me reconocen por DNI y se precargan mis datos **[v1]**.
- **A3**: recibo confirmación inmediata por mail al reservar **[v1]**.
- **A4**: pago la seña al reservar (MercadoPago) viendo monto del turno y de la seña antes de pagar **[v1]**.
- **A5**: si el pago falla, mi slot no queda bloqueado para otros (expiración de pre-reserva) **[v1]** — ver `07_flujos_principales.md`.

## Épica B — Cancelación y reprogramación [v1]

- **B1**: como paciente, cancelo/reprogramo liberando el hueco automáticamente **[v1]**.
- **B2**: veo las reglas de seña (100/60/0) **antes** de confirmar la cancelación **[v1]**.
- **B3**: como odontólogo/recepcionista, cancelo/reprogramo turnos con motivo y queda historial actor+fecha **[v1]**.

## Épica C — Agenda del odontólogo [v1]

- **C1**: veo mi agenda del día aislada por profesional, sin choques **[v1]**.
- **C2**: cargo mi disponibilidad (duración, tope/día, pausas, feriados, bloqueos) **[v1]**.
- **C3**: marco atendido / no-show al finalizar el horario **[v1]**.
- **C4**: sobre-turnos **[v2]** (fuera de v1 consciente). **C5**: drag & drop **[v2]** (techo DentalSoft, no exigible v1).

## Épica D — Seña, devoluciones y comprobantes [v1]

- **D1**: configuro mi monto de turno y de seña (por odontólogo) **[v1]**.
- **D2**: opero la bandeja de devoluciones (aprobar/rechazar/ejecutar) con trazabilidad completa **[v1]**.
- **D3**: recibo comprobante (recibo interno v1) por pago y por devolución **[v1]**.
- **D4**: concilio pagos contra reportes de MercadoPago **[v1]** — ver `11_pagos_mercadopago.md`.
- **D5**: factura ARCA automática **[v2]** post-v1. **D6**: obras sociales/liquidaciones **[v2]**.

## Épica E — Recordatorios por mail [v1]

- **E1**: se envían recordatorios automáticos en ventana configurable (p. ej. 24 h) **[v1]**.
- **E2**: confirmo/cancelo desde el propio mail y la agenda se actualiza **[v1]**.
- **E3**: si el mail rebota, hay reintentos con backoff y el fallo queda visible (entregabilidad: SPF/DKIM/DMARC, métricas) **[v1]**.
- **E4**: recordatorios por WhatsApp **[v2]** (conector modelado, apagado).

## Épica F — Ficha paciente, reportes y exportación [v1]

- **F1**: ficha de paciente mínima (contacto, DNI, consentimiento) + historial de turnos acotado, nada clínico **[v1]**.
- **F2**: reportes mínimos de asistencia/ausentismo (conteos por estado y período) **[v1]**.
- **F3**: exportación CSV/PDF de turnos y caja **[v1]**.
- **F4**: métrica propia de ausentismo con metodología publicada — **solo si el proyecto sale del ámbito académico [v2+]** (los claims de mercado tipo "−65 %" son afirmación comercial **No evidenciada**).
- **F5**: odontograma/periodontograma/HC completa **[v2]**.

## Épica G — Roles, sedes y crecimiento [v1/v2]

- **G1**: rol recepcionista con permisos explícitos y aislamiento de agenda **[v1]**.
- **G2**: single-sede con modelo que no bloquea multi-sede **[v1]**.
- **G3**: lista de espera (modelada, apagada) **[v2]** · **G4**: portal público de reserva **[v2]** · **G5**: calendario externo **[v2]** · **G6**: multi-sede plena **[v2+]**.
