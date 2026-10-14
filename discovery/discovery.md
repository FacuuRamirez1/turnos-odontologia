# Discovery — Turnos Odontología

**Fecha**: 2026-10-14
**Actualizado 2026-10-14 con hallazgos de analisis-mercado.md**
**Fuentes investigadas**: Q&A pura inicial (sin URLs de competidores) + `discovery/analisis-mercado.md` (relevamiento del 2026-10-14 sobre 18 sistemas con URLs y fecha de consulta verificables; lo no demostrado públicamente se marca como "No evidenciado").

## 1. Problema que resuelve

Los consultorios odontológicos coordinan turnos por papel, WhatsApp informal y planillas dispersas, lo que genera turnos perdidos, dobles gestiones y tiempo administrativo que le quita horas a la atención. El relevamiento de mercado confirma que el consultorio chico single-sede que trabaja así está desatendido: el mercado empuja soluciones multi-sede/enterprise, mientras nadie une en un mismo flujo simple la agenda por odontólogo, la reserva online de baja fricción, la seña con reglas de devolución y los recordatorios bien hechos.

## 2. Usuarios / roles

- **Paciente**: reserva un turno disponible sin llamar, cancela o reprograma para liberar su horario. Se reconoce al paciente existente por DNI para acelerar la reserva.
- **Odontólogo**: ve su agenda del día, gestiona cancelaciones y reprogramaciones, carga su disponibilidad. En v1 single-sede rige el **aislamiento de agenda por odontólogo**: cada odontólogo opera sobre su propia agenda y disponibilidad (pausas, feriados, bloqueos incluidos) sin ver ni modificar la de otros, salvo rol autorizado.
- **Admin / Recepcionista (opcional)**: rol delegado con **permisos explícitos** — carga disponibilidad, gestiona cancelaciones y reprogramaciones, consulta las agendas del consultorio y la bandeja de devoluciones; no administra usuarios ni configuración de pagos. Si el consultorio no tiene recepcionista, el odontólogo absorbe esas funciones sin que el sistema lo trabe.

## 3. Casos de uso

1. Como paciente, quiero reservar un turno disponible para no llamar por teléfono, en un **flujo canónico de 3–4 pasos** (datos → profesional → fecha/hora → confirmación, estándar observado en el mercado), con reconocimiento por DNI si ya soy paciente y **confirmación inmediata** por mail en v1.
2. Como paciente, quiero cancelar/reprogramar para liberar mi turno, con liberación automática del hueco y reglas de seña visibles al momento de la acción.
3. Como odontólogo, quiero ver la agenda del día (solo la mía, aislada por profesional) para atender sin choques.
4. Como odontólogo, quiero gestionar cancelaciones y reprogramaciones de turnos, con historial de estados por turno (actor + fecha) que deje trazabilidad de cada cambio.

## 4. Competidores / soluciones existentes

No hay sistema actual que migrar: cada odontólogo se organiza como puede (papel, WhatsApp, memoria). El relevamiento en `analisis-mercado.md` identifica el mercado real contra el que compite la adopción, con este **top 5 sugerido para demo** (orden de demo propuesto por el informe; todo dato es declaración del proveedor salvo que se indique comprobación, y lo no verificado se marca como tal):

1. **DentalSoft** (Argentina, https://dentalsoft.com.ar/) — benchmark funcional argentino más completo: agenda con drag & drop, sobre-turnos con detección de solapamiento, odontograma de 18 estados, caja con MercadoPago, liquidaciones de obras sociales y profesionales, recordatorios manuales vs. automáticos según plan, web propia con turnos. Precios publicados a fecha de consulta: Gestión $30.000/mes, Pro $60.000/mes (ARS); claim "+300 clínicas" como afirmación del proveedor, **No evidenciado** por tercero.
2. **MedicAI** (Argentina, salud general, https://www.medicai.com.ar/) — referencia de cobros y cumplimiento para el MVP: turnera pública con link, Google Calendar bidireccional declarado, **seña por Mercado Pago al reservar**, bandeja ARCA con CAE declarada, recordatorios WhatsApp/mail, HCE con IA. Precio publicado $25.900 + IVA por profesional/mes; aprobación ReNaPDiS N.º 292 declarada por el proveedor (verificable en registro oficial según el proveedor; auditoría técnica independiente: **No evidenciada**).
3. **Dentalink** (Chile/LatAm, http://www.softwaredentalink.com/) — techo dental regional: agenda multi-centro, odontograma/periodontograma, convenios, caja y comisiones, Contact Center con IA 24/7 declarado. Precios a cotización (**No evidenciado** en público); claims de escala (+15.000 clientes y similares) como afirmación del proveedor, **No evidenciados** por auditoría.
4. **DoctorYa** (Argentina, https://doctorya.com.ar/) — referencia de turnos/ARCA a precio agresivo: agenda por profesional/sede, reserva por buscador + chat, recordatorios WhatsApp con confirmación, OS/copagos, facturación ARCA declarada para Monotributo/RI. Precios publicados a fecha: $9.000/$25.000/$90.000 ARS según plan; odontograma interactivo propio **No evidenciado** (archiva odontogramas, no los edita, según lo relevado).
5. **Gendu** (Argentina, https://www.gendu.com.ar/) — referencia de simplicidad y precio: página de reservas 24/7, recordatorios WhatsApp/mail, cobro anticipado con Mercado Pago declarado, historia básica, reportes. Plan Básico $0 y Comercial $9.100 ARS a fecha de consulta; historia clínica odontológica completa **No evidenciada**.

Suplentes para una segunda ronda: DentiClick (mini-web + OS/nomenclador), SOMOSDENTO (ARCA dental declarada + portal por profesional) y Doctoralia (lista de espera y pagos anti-no-show como inspiración enterprise; precio Argentina **No evidenciado**). Si aparece un referente nuevo, se scrapea y anexa en `discovery/sources/`.

## 5. Funcionalidades necesarias

- Alta de disponibilidad por odontólogo, con duración estándar, tope de turnos por día, **pausas, feriados y bloqueos** por profesional.
- Reserva de turno online por el paciente con el **flujo canónico de 3–4 pasos**, reconocimiento por DNI y confirmación inmediata.
- Cancelación y reprogramación (paciente y odontólogo/admin) con liberación automática del hueco y anticipación mínima configurable.
- Agenda del día por odontólogo, aislada por profesional y a prueba de choques (constraints de dominio, no solo validación de UI).
- Recordatorios automáticos **por mail** (única vía en v1) con spec de entregabilidad: **SPF/DKIM/DMARC, colas y reintentos con Redis, plantillas versionadas, ventana de envío configurable** (p. ej. 24 h) y **confirmar/cancelar desde el propio mail** actualizando la agenda.
- Pagos/señas online en v1: monto fijo que se paga al reservar vía **MercadoPago (proveedor sugerido v1; monto del turno y de la seña configurables por odontólogo)**, con **bandeja de devoluciones, comprobantes y trazabilidad**; **pago y comprobante se modelan como entidades separadas del turno** para no refactorizar cuando ARCA entre en v2.
- **Historial de estados por turno** (creado/confirmado/cancelado/reprogramado/devuelto, con actor + fecha).
- **Exportación CSV/PDF** de turnos y caja.
- **Reportes mínimos de asistencia/ausentismo** con **métrica propia (solo si el proyecto sale del ámbito académico)** (los claims de mercado del tipo "−65% ausentismo" se consignan como afirmación comercial sin metodología publicada: **No evidenciado**).
- **Ficha de paciente mínima + historial de turnos acotado** en v1 (datos de contacto, DNI, turnos pasados/futuros; nada clínico).
- Permisos de recepcionista y aislamiento de agenda ya descritos en el punto 2.

## 6. Funcionalidades opcionales

- **Ficha paciente mínima + historial de turnos acotado: entra en v1** (ver punto 5). El **odontograma y el periodontograma quedan para v2** (el mercado los pone como piso clínico, pero exceden el plazo académico).
- **Lista de espera: modelada pero apagada para v2** (estados/slots preparados para rellenar huecos; inspiración Doctoralia, cuya lista de espera inteligente es funcionalidad declarada en su sitio, eficacia **No evidenciada** por demo propia). Los **sobre-turnos siguen fuera de v1** de forma consciente.
- Integración con **WhatsApp: eliminada de v1, con conector y plantillas modelados pero apagados para v2** (el mercado la da por sentada; se diseña para activarla sin migraciones).
- **Calendario externo (tipo Google): v2 diseñado, no construido** (sync que bloquee huecos ocupado/no disponible).
- **Link/portal público de reserva por consultorio: oportunidad v2** (página24/7 con SEO básico, referencia Gendu/DentiClick/MedicAI — alcance declarado por esos proveedores).
- Multi-sede / multi-odontólogo pleno (se diseña para no bloquearlo a futuro, no se construye), obras sociales y facturación ARCA automática (v2 post-v1, una vez finalizado v1), historia clínica completa, app móvil, campañas/IA: v2 o posterior.

## 7. Reglas de negocio

- Anticipación mínima para cancelar (configurable, ej. 24hs).
- Duración estándar del turno y tope de turnos por día, más **pausas, feriados y bloqueos** por odontólogo que quitan slots ofrecibles.
- El hueco liberado por cancelación vuelve a estar disponible automáticamente.
- **Constraints de dominio** (no como mera validación de UI): no se puede reservar en el pasado, no se puede doble-reservar el mismo slot, no se solapan turnos del mismo profesional.
- **Máquina de estados del turno** (p. ej. creado → confirmado → atendido / cancelado / reprogramado / no-show / devuelto), donde **cada transición guarda actor + fecha** y alimenta el historial del punto 5.
- Política de seña (monto del turno y de la seña configurables por odontólogo; se paga al reservar):
  - Cancela en término → se devuelve el monto completo.
  - Cancela fuera de término → se devuelve el 60% del monto.
  - No se presenta al turno → no se devuelve monto.
  - Toda devolución pasa por la **bandeja de devoluciones con comprobante y trazabilidad** (quién la aprobó, cuándo, por qué monto); **el pago y el comprobante viven separados del turno** para permitir conciliación con MercadoPago y, en v2, emisión ARCA sin refactorizar.

## 8. Integraciones

- **Mail para recordatorios automáticos** (única vía de recordatorio en v1) con la spec del punto 5: SPF/DKIM/DMARC, colas/reintentos en Redis, plantillas, ventana configurable y confirmar/cancelar desde el mail.
- **MercadoPago como proveedor sugerido para la seña online en v1** (referencia: cobro al reservar declarado por MedicAI, caja con MP en DentalSoft, cobro anticipado en Gendu — todo declaración de esos proveedores); **montos del turno y de la seña configurables por odontólogo**.
- **Sin WhatsApp en v1** (decisión consciente de recorte de scope): se deja el **conector y las plantillas modelados pero apagados** para v2 (WhatsApp Business API), tomando como UX esperado los recordatorios con confirmación que declaran DentalSoft/DoctorYa/MedicAI.
- **Calendario externo como v2 diseñado, no construido** (sin sync en v1).
- **Sin obras sociales ni ARCA en v1**: el **comprobante se modela separado del turno** (patrón comprobante + link de pago + conciliación) aunque la emisión quede apagada; la facturación electrónica automática es v2 post-v1 (una vez finalizado v1).
- Sin integraciones con app móvil ni APIs clínicas en v1.

## 9. Restricciones

- Proyecto académico con plazo del cuatrimestre.
- Stack obligatorio:
  - Backend: Python, FastAPI, JWT para autenticación, SQLAlchemy, PostgreSQL, Redis para lo asíncrono, Docker / Docker Compose.
  - Frontend: React, TypeScript, Vite.
- V1 single-sede (al salir multi-sede del scope), con aislamiento de agenda por odontólogo desde el día uno.
- Cumplimiento y seguridad mínimos desde v1: **consentimiento del paciente** para el tratamiento de sus datos, **política de retención** de datos y turnos, **cifrado** declarado de datos sensibles, **backups** periódicos y **trazabilidad de devoluciones**; el mercado local casi nunca documenta estos puntos (cifrado, backups, Ley 25.326 de Datos Personales y Ley 26.529 de Historia Clínica figuran como **No evidenciados** en la mayoría de los relevados), por lo que se diseñan explícitamente aunque el dictamen legal exceda el alcance académico.
- Principio de evidencia: la **métrica propia de ausentismo se implementa solo si el proyecto sale del ámbito académico** (no se adoptan claims de proveedores sin metodología); **precio y trial públicos desde el día uno (decisión confirmada)** (el mercado premia precio público y trial sin tarjeta, y penaliza la cotización opaca).

## 10. Riesgos

- **Supuesto sin probar (principal, reformulado con el mercado)**: que pacientes y odontólogos adopten el sistema frente al **hábito del WhatsApp informal más los incumbentes que ya ofrecen WhatsApp automático** (DentalSoft Pro con recepcionista virtual, DoctorYa y MedicAI con recordatorios/confirmación por WhatsApp, Dentalink con Contact Center IA — todo declarado por esos proveedores, con eficacia **No evidenciada** por auditoría). El riesgo ya no es solo "la costumbre", sino competir contra automatización instalada — no validado con usuarios reales.
- **Riesgo**: los mails de recordatorio pueden caer en spam si no se configura bien el envío — se mitiga con la spec SPF/DKIM/DMARC + colas/reintentos + métricas de entrega del punto 5.
- **Riesgo**: la fricción del pago de seña al reservar puede bajar la conversión si el flujo no es simple — se mitiga con el flujo canónico 3–4 pasos y la referencia de baja fricción (Gendu/MedicAI, según lo declarado por esos proveedores).
- **Riesgo**: scope v1 todavía exigente (pagos + recordatorios + roles + trazabilidad + reportes) para el plazo académico si no se prioriza el corte — el recorte se mantiene: sin WhatsApp, sin multi-sede, sin sobre-turnos, sin odontograma, sin ARCA/OS en v1.
- **Riesgo**: operar datos de salud sin cifrado, backups, retención y consentimiento explícitos expone al consultorio; el silencio normativo del mercado no lo vuelve opcional.

## 11. Preguntas abiertas

- Del pago queda definido: **monto del turno y de la seña configurables por odontólogo** (proveedor fijado como sugerido: MercadoPago en v1).
- Obras sociales y ARCA quedan **fuera de v1 y van a v2 post-v1 (una vez finalizado v1)** con comprobante modelado por separado — orden en v2 pendiente (emisión, CAE, liquidación OS).
- ¿En qué orden vuelven en v2 la lista de espera modelada, los sobre-turnos, el WhatsApp (conector ya modelado), el calendario externo, el portal público de reserva y el odontograma/periodontograma, o se descartan definitivamente?
- La **métrica propia de ausentismo va solo si el proyecto sale del ámbito académico** — definición pendiente (ventana, denominador, reportes mínimos) para no repetir claims sin metodología.
- **Precio y trial públicos desde el día uno: SÍ (decisión confirmada).**
