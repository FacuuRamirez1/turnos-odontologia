# 09 — Decisiones y supuestos

**Proyecto**: turnos-odontología · **Fecha**: 2026-10-14 · **Fuente**: `discovery/discovery.md` + `discovery/analisis-mercado.md` (consulta 2026-10-14)
Relacionadas: todos los archivos de la KB. Lo **No evidenciado** se marca como tal; lo opinable sin evidencia va a `10_preguntas_abiertas.md`.

## 1. Decisiones cerradas (no reabrir)

| # | Decisión | Fundamento (mercado) |
|---|---|---|
| D1 | v1 completo junto: reserva + agenda + seña real MP + mail (P2=b) | El diferencial es la unión de los cuatro en un flujo; por oleadas se pierde la propuesta de valor. Riesgo asumido: scope exigente para el cuatrimestre (ver `discovery.md` §10) |
| D2 | Velocidad con sesgo a entrega sin romper trazabilidad de pagos (P5=c) | Recortar UX/clínica, jamás idempotencia ni audit trail |
| D3 | Auditoría máxima día 1: historial estados + idempotencia cobros/devoluciones + CSV/PDF + audit trail append-only (P-fin=c) | Ningún relevado ofrece auditoría global exportable (DentalSoft: parcial; resto: **No evidenciado**); es diferencial barato |
| D4 | Enfoque B: todo documentado con etiquetas v1/v2 | Evita scope creep manteniendo el diseño futuro visible |
| D5 | MercadoPago proveedor sugerido v1; montos turno/seña configurables por odontólogo | MP es el medio común: caja con MP en DentalSoft, cobro al reservar en MedicAI, anticipado en Gendu (declaraciones de esos proveedores). Monto fijo pendiente → `10_preguntas_abiertas.md` |
| D6 | Devolución 100 % en término / 60 % fuera / 0 % no-show; se paga al reservar | Política propia; **No evidenciado** que alguien la implemente así (vacío detectado en C.3 del análisis) |
| D7 | Mail-only en v1; WhatsApp conector modelado apagado v2 | Recorte consciente: el mercado da WhatsApp por sentado pero tiene costo por mensaje (DentalSoft declara 0,026 USD/msg de Meta) y el mail bien hecho es vacío (C.3.3) |
| D8 | Single-sede con aislamiento por odontólogo; multi-sede v2+ | Ataca al consultorio chico desatendido (C.3.6); el mercado empuja enterprise |
| D9 | Sin sobre-turnos v1; lista de espera modelada apagada v2 | Recorte consciente; inspiración Doctoralia (lista inteligente declarada, eficacia **No evidenciada**) |
| D10 | OS y ARCA en v2 post-v1; comprobante separado del turno desde v1 | Nadie une agenda→seña→factura→OS (C.3.2); el patrón comprobante+link+conciliación evita refactorizar. Orden en v2 pendiente |
| D11 | Precio y trial públicos desde día uno (confirmada) | El mercado premia precio público y trial sin tarjeta y penaliza cotización opaca (C.1.6) |
| D12 | Métrica de ausentismo solo si sale del ámbito académico | Claims tipo "−65 %" son afirmación comercial sin metodología: **No evidenciado** |
| D13 | Pago y comprobante como entidades separadas del turno | Puente ARCA/MP (C.4); referencia patrón ARCA-API/TusFacturasAPP |

## 2. Supuestos (marcados, a validar)

- **Suposición:** pacientes y odontólogos adoptarán el sistema frente al hábito de WhatsApp informal + incumbentes con WhatsApp automático — no validado con usuarios reales (riesgo principal, `discovery.md` §10).
- **Suposición:** el mail con confirmar/cancelar compensa la falta de WhatsApp en v1 si la entregabilidad es alta (SPF/DKIM/DMARC + métricas).
- **Suposición:** la fricción de pagar seña al reservar no baja la conversión si el flujo es de 3–4 pasos (referencia declarada Gendu/MedicAI, eficacia **No evidenciada** por auditoría).
- **Suposición:** montos configurables por odontólogo bastan como flexibilidad comercial v1 (sin seña porcentual ni por tratamiento).
- **Suposición:** el alcance (D1) entra en el cuatrimestre manteniendo los recortes; si no, el corte cae sobre reportes/F4-UX, nunca sobre pagos/auditoría (D2).
- **Suposición:** el dictamen legal (Ley 25.326/26.529, rol ante ARCA) excede el alcance académico; se diseña cumplimiento mínimo explícito sin pretender validez jurídica.
