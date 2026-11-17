# Limitaciones conocidas v1 — Q11 y Q12 (C-13 task 7.6)

## Q11 — Sin validación con usuarios reales

**Estado:** Limitación conocida, no bloqueante para v1.

El supuesto de adopción del paciente frente al canal digital (reserva online + mail vs. WhatsApp informal) no ha sido validado con usuarios reales del consultorio objetivo. El riesgo principal sin probar es la baja adopción del flujo de reserva pública.

**Mitigación v1:** Diseño de baja fricción (3–4 pasos, reconocimiento por DNI, confirmación inmediata por mail). Reevaluar en v2 con métricas de uso reales.

**Referencia:** `10_preguntas_abiertas.md` §4.11.

## Q12 — Sin dictamen legal Ley 25.326/26.529

**Estado:** Limitación conocida, no bloqueante para v1.

El diseño de cumplimiento mínimo (consentimiento bloqueante, política de retención, cifrado declarado de sensibles, backups) no cuenta con dictamen legal sobre la Ley 25.326 de protección de datos personales ni la Ley 26.529 (arancelamiento/obra social). El cumplimiento diseñado ≠ validez jurídica.

**Mitigación v1:** Documentar explícitamente como limitación; obtener dictamen legal antes de producción real.

**Referencia:** `10_preguntas_abiertas.md` §4.12.

## Alcance

Ambas limitaciones quedan registradas en la documentación de cierre v1 y no bloquean el cierre del roadmap. Se revisan en v2.
