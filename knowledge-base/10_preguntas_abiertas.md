# 10 — Preguntas abiertas

**Proyecto**: turnos-odontología · **Fecha**: 2026-10-14
Todo lo aquí listado **no bloquea v1** salvo marca explícita. Prefijo **[DISCOVERY]** = baja confianza heredada que el roadmap debe resolver.

## 1. Pagos (bloquean detalle de Épica D)

1. Monto fijo de la seña pendiente de definición (proveedor MP ya sugerido; montos configurables por odontólogo ya decididos). ¿Monto inicial sugerido por defecto?
2. Cerrar proveedor MercadoPago: ¿credenciales de prueba vs. producción, quién es titular de la cuenta, cómo se concilia?
3. Reprogramación con diferencia de monto (turno más caro/barato): ¿se cobra/paga diferencia o se mantiene seña original?
4. ¿Devolución del 60 % automática o con aprobación manual en bandeja? (propuesta: automática si < umbral, manual si ≥ umbral — umbral a definir).

## 2. Orden de v2 (post-v1)

5. ¿En qué orden vuelven: lista de espera, sobre-turnos, WhatsApp (conector ya modelado), calendario externo, portal público de reserva, odontograma/periodontograma — o se descartan?
6. OS/ARCA en v2 post-v1: ¿orden interno (emisión, CAE, liquidación OS) y con qué padrón/nomenclador?

## 3. Reglas y producto

7. Valores por defecto: anticipación mínima (24 h propuesta), ventana de recordatorio (24 h propuesta), TTL de pre-reserva, reintentos de mail.
8. Métrica de ausentismo (solo si sale del ámbito académico): ventana, denominador, reportes mínimos.
9. Precio y trial públicos: cifras y límites del trial (referencias: DentalSoft $30.000/$60.000, MedicAI $25.900+IVA, Gendu $0/$9.100, DoctorYa desde $9.000 — todos ARS a fecha 2026-10-14, verificar vigencia).
10. Recepción por teléfono (recepcionista reserva a nombre del paciente): ¿flujo exacto y qué datos mínimos exige?

## 4. Inconsistencias / vacíos detectados

11. **[DISCOVERY]** Sin validación con usuarios reales del supuesto de adopción frente a WhatsApp (riesgo principal sin probar).
12. **[DISCOVERY]** Sin dictamen legal sobre Ley 25.326/26.529 y rol ante ARCA (diseño de cumplimiento mínimo ≠ validez jurídica).
13. Odonthia/DentalCore citados por fuente tercera (NacarOS) sin verificación directa: requieren demo antes de usarse como benchmark.
14. Precios de Dentalink/DentiDesk/Doctoralia-AR/Dentaly-cifra/SOMOSDENTO-cifra: **No evidenciados** (a cotización); no usar como referencia numérica.
