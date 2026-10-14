# Análisis de mercado — Sistemas odontológicos con gestión de turnos y agenda

**Proyecto**: turnos-odontología (consultorio odontológico, Argentina)
**Fecha de consulta de fuentes**: 2026-10-14
**Autor**: analista sénior de mercado y producto SaaS (salud digital / odontología, AR + LatAm)
**Contexto**: este informe consume `discovery/discovery.md` como definición del problema, usuarios y scope v1. No lo modifica.

> **Regla de evidencia aplicada**: todo dato proviene de fuentes verificables (sitio oficial, precios, ayuda, marketplace, reseña verificada). Cada sistema cita URL + fecha. Lo no demostrado se consigna como **"No evidenciado"**. Se distingue funcionalidad comprobada (vista en sitio/demo/documentación) de afirmación comercial del proveedor (claim sin prueba pública).

---

## A. Tabla comparativa — ordenada por relevancia para Argentina

Orden: 1–9 producto argentino o con operación local comprobada → 10–13 LatAm con encaje local → 14–18 internacionales relevantes como referencia/inspiración.

### 1. DentalSoft — Argentina

- **Empresa / país**: DentalSoft, Argentina (La Plata, Buenos Aires / Rosario, Santa Fe). Contacto: info@dentalsoft.com.ar, +54 9 3417 82-3053.
- **URL oficial**: https://dentalsoft.com.ar/ (consulta: 2026-10-14).
- **Segmento objetivo**: clínicas y consultorios odontológicos (afirmación comercial: "+300 clínicas en Argentina").
- **Modalidad**: SaaS en la nube, 100% web, sin instalación (comprobado: FAQ "funciona 100% en la nube"; acceso desde PC/tablet/celular).
- **Gestión de agenda**: comprobada — vista semanal/diaria/mensual, drag & drop con confirmación, urgencias y **sobre-turnos con detección de solapamiento**, bloqueos/feriados, horarios individuales por odontólogo, multi-sucursal, sincronización con Google Calendar por profesional.
- **Turnos digitales**: comprobado — reserva online 24/7 en 4 pasos (datos → profesional → fecha → confirmar), slots en tiempo real, reconocimiento de paciente existente por DNI, filtro por especialidad y obra social, confirmación inmediata por WhatsApp.
- **Automatización**: comprobada (plan Pro) — recordatorios automáticos por WhatsApp y e-mail con confirmación/cancelación que actualiza la agenda; recepcionista virtual 24 h (IA por WhatsApp); campañas de recuperación de inactivos; solicitud automática de reseñas Google; recordatorio automático de deudas. En plan Gestión el envío es **manual** (se abre WhatsApp con mensaje redactado). Costo de mensajes: el proveedor declara que Meta cobra 0,026 USD por mensaje WhatsApp; e-mail gratuito.
- **Gestión odontológica**: comprobada — historia clínica completa, odontograma SVG interactivo con 18 estados, notación FDI, notas por pieza, historial con profesional y fecha; módulo de ortodoncia (controles, alineadores, galería antes/después); plan de tratamiento con prioridades; consentimientos con firma; recetas digitales; órdenes; portal del paciente (plan Pro).
- **Administración**: comprobada — caja y cobros (efectivo, tarjeta, transferencia, **MercadoPago**, obra social), cierre de caja diario, egresos y anulaciones con trazabilidad, registro desde el turno con un clic; presupuestos desde catálogo con cobertura de OS aplicada y seguimiento hasta el cobro, compartidos por link; liquidaciones de profesionales (comisión % general o por tratamiento, período personalizable, PDF) y de obras sociales por OS y plan (PDF); reportes de ocupación, facturación, tratamientos por turno, ranking por profesional, ausentismo.
- **Integraciones**: comprobadas — Google Calendar (sync por profesional), WhatsApp (manual en Gestión, automático en Pro), MercadoPago (logo exhibido como medio), PDF/Excel. **No evidenciado**: API pública, AFIP/ARCA (facturación electrónica no declarada; hablan de "caja/cobros", no de CAE), integración con calendarios externos salvo Google.
- **Operación**: multi-sucursal (comprobado), roles/usuarios para secretarias con permisos configurables (comprobado), auditoría parcial (historial de odontograma con profesional/fecha; egresos/anulaciones con trazabilidad — auditoría global **No evidenciada**), exportación PDF (comprobado; Excel declarado en integraciones), migración desde Excel/CSV/otro sistema incluida (comprobado), soporte en español por WhatsApp y e-mail con equipo argentino (comprobado), implementación <24 h (afirmación comercial).
- **Seguridad y cumplimiento**: "en la nube, seguro" (afirmación comercial genérica). **No evidenciado**: cifrado, backups, política de privacidad detallada, cumplimiento Ley 25.326 de Datos Personales, Ley 26.529 de Historia Clínica, rol ante ARCA.
- **Modelo comercial**: trial/demo — demo instantánea con datos de ejemplo sin tarjeta + plan inicial gratis 3 meses (hasta 50 turnos/mes, sin imágenes). Precios publicados en ARS: Gestión $30.000/mes, Pro $60.000/mes (base 1 profesional; más profesionales = adicional; +10 profesionales plan a medida). Moneda ARS.
- **Fortalezas**: el más completo para Argentina en este relevamiento (OS + liquidaciones + MercadoPago + WhatsApp + ortodoncia + web propia con turnos).
- **Limitaciones**: facturación electrónica ARCA no declarada; auditoría/seguridad sin evidencia técnica; costo WhatsApp por mensaje; sobre-turnos incluidos (fuera de scope v1 propio).
- **Diferencial real**: liquidaciones de OS y comisiones + recepcionista virtual IA + página web con reservas incluidas.
- **Evidencia de adopción**: afirmación del proveedor "+300 clínicas en Argentina, 4,9/5 satisfacción"; testimonios con nombre/clínica/ciudad en el sitio (no verificados por tercero). Reseñas en marketplace externo: **No evidenciado**.

### 2. DentiClick — Argentina

- **Empresa / país**: DentiClick, Argentina (desarrollado por ThunderSkills).
- **URL oficial**: https://www.denticlick.app/ (consulta: 2026-10-14).
- **Segmento**: consultorios odontológicos (plan individual/multi-profesional).
- **Modalidad**: SaaS nube, sin instalación, instalable como app (PWA), multi-dispositivo (comprobado).
- **Agenda**: comprobada — vista diaria/semanal/mensual, estados, reprogramación.
- **Turnos digitales**: comprobado — mini-web propia por consultorio (`subdominio.denticlick.app`) con logo/colores, reserva 24/7 por el paciente.
- **Automatización**: **No evidenciado** (no declara recordatorios automáticos ni confirmación por WhatsApp/mail en el sitio consultado).
- **Gestión odontológica**: comprobada — odontograma interactivo (caras, tratamientos, temporal, historial con versiones), historia clínica (evoluciones, antecedentes, alertas médicas), recetas imprimibles, carga de imágenes y visor 3D de escáneres.
- **Administración**: comprobada — presupuestos con precios editables y cargo automático, cuenta corriente, pagos y recibos imprimibles; obras sociales con liquidación por OS y mes, nomenclador, exportación CSV/PDF; insumos con stock mínimo y descuento automático; estadísticas (ingresos, deuda, turnos por estado, rendimiento por profesional). **No evidenciado**: Mercado Pago, facturación electrónica ARCA.
- **Integraciones**: **No evidenciado** (no declara WhatsApp API, Google Calendar, APIs, AFIP/ARCA).
- **Operación**: multi-profesional con roles, agenda y cobros por profesional (comprobado); backup semanal automático (comprobado); soporte por chat (comprobado). Auditoría/exportación general: **No evidenciado** salvo CSV/PDF citados.
- **Seguridad y cumplimiento**: **No evidenciado** (sin documentación pública de cifrado, Ley 25.326/26.529).
- **Modelo comercial**: 1 mes gratis, sin tarjeta, "un solo precio, todo incluido". Precio numérico: **No evidenciado** en la página consultada (no publica cifra).
- **Fortalezas / diferencial**: propuesta simple "todo incluido", OS + nomenclador + insumos + visor 3D, mini-web con reservas.
- **Limitaciones**: sin automatización evidenciada; sin medios de pago ni ARCA evidenciados; precio no publicado.
- **Adopción**: panel demo con datos ficticios ("Consultorio Dr. Juárez"). Adopción real publicada: **No evidenciada**.

### 3. Dentaly — Argentina

- **Empresa / país**: Dentaly, Argentina (soporte local declarado).
- **URL oficial**: https://www.dentaly.com.ar/ (consulta: 2026-10-14).
- **Segmento**: clínicas/consultorios odontológicos argentinos.
- **Modalidad**: SaaS nube 100%, sin instalación, multi-dispositivo (comprobado).
- **Agenda**: comprobada — agenda diaria/semanal en tiempo real.
- **Turnos digitales**: agenda 24/7 declarada; portal de reserva paciente no detallado públicamente → funcionalidad **parcialmente evidenciada**.
- **Automatización**: comprobada (declarada) — recordatorios por WhatsApp automáticos; claim "−65% ausentismo" (afirmación comercial, sin metodología publicada).
- **Gestión odontológica**: comprobada — odontograma digital interactivo (permanente y temporaria), fichas de pacientes, periodontograma (citado en planes), consentimientos con firma digital, tratamientos/especialidades.
- **Administración**: comprobada — finanzas en tiempo real (ingresos/egresos/resumen), inventario con alertas, obras sociales (citado). **No evidenciado**: Mercado Pago, señas, facturación ARCA.
- **Integraciones**: WhatsApp (declarado). Google Calendar / API / ARCA: **No evidenciado**.
- **Operación**: pacientes ilimitados (plan citado), multi-profesional (citado), dashboard diario. Roles/auditoría/exportación/soporte: **No evidenciado** en lo consultado (soporte local "argentino" es afirmación sin canal publicado en el extracto).
- **Seguridad**: **No evidenciado**.
- **Modelo comercial**: demo gratuita; planes y precios: ver página (extracto no incluye cifras) → precio numérico **No evidenciado** en este relevamiento.
- **Fortalezas**: odontología completa + finanzas + WhatsApp + nube, posicionado como reemplazo de "software legacy".
- **Limitaciones**: reserva online y cobros poco documentados; sin ARCA/MP evidenciados.
- **Adopción**: publicada: **No evidenciada** (sin cifras ni reseñas verificables halladas).

### 4. SOMOSDENTO — Argentina

- **Empresa / país**: SOMOSDENTO, Argentina (hola@somosdento.com).
- **URL oficial**: https://somosdento.com/ (consulta: 2026-10-14).
- **Segmento**: consultorios odontológicos argentinos.
- **Modalidad**: SaaS nube, sin instalaciones, multi-dispositivo 24/7 (comprobado).
- **Agenda**: comprobada — calendario mensual, generación automática por franjas, gestión de estados.
- **Turnos digitales**: comprobado — portal de turnos online con URL personalizada por profesional; el paciente reserva desde el celular sin llamar.
- **Automatización**: no declara recordatorios automáticos → **No evidenciado**.
- **Gestión odontológica**: comprobada — ficha clínica completa, odontograma digital, historia dental, tratamientos, adjuntos.
- **Administración**: comprobada (declarada) — **facturación electrónica con ARCA (ex AFIP), facturas A/B/C**, cobros, aranceles, reportes mensuales; inventario con alertas y descuento automático. Mercado Pago / señas: **No evidenciado**.
- **Integraciones**: ARCA (declarada — único argentino odontológico del relevamiento que la declara además de MedicAI/DoctorYa). WhatsApp/Google/API: **No evidenciado**.
- **Operación**: multi-profesional con aislamiento por odontólogo (comprobado); migración desde papel/otra app asistida (comprobado); soporte por WhatsApp (comprobado); demo 30 días, hasta 10 pacientes de prueba, sin tarjeta (comprobado). Roles finos/auditoría/exportación: **No evidenciado**.
- **Seguridad**: "datos seguros en la nube" (afirmación genérica). Cumplimiento normativo: **No evidenciado**.
- **Modelo comercial**: demo gratis 30 días; precio numérico **No evidenciado**.
- **Fortalezas / diferencial**: ARCA + portal por profesional + aislamiento multi-profesional + migración asistida.
- **Limitaciones**: sin automatización ni pagos online evidenciados.
- **Adopción**: testimonios con nombre/ciudad/especialidad en el sitio (p. ej. Rosario) — no verificados por tercero. Cifras de adopción: **No evidenciadas**.

### 5. DoctorYa — Argentina (salud general, con odontología)

- **Empresa / país**: DoctorYa, Argentina.
- **URL oficial**: https://doctorya.com.ar/ (consulta: 2026-10-14).
- **Segmento**: profesionales, consultorios, clínicas y sanatorios de Argentina (todas las especialidades, incluye odontología: ficha centraliza "odontogramas").
- **Modalidad**: SaaS nube, multi-dispositivo (comprobado).
- **Agenda**: comprobada — agenda por profesional y sede, programa/reagenda/cancela, vista del día con estados.
- **Turnos digitales**: comprobado — reserva online 24/7 por buscador (especialidad/ubicación) + asistente conversacional que reserva por chat.
- **Automatización**: comprobada — recordatorios automáticos por WhatsApp con confirmación/cancelación del paciente; reagendado ágil.
- **Gestión odontológica**: parcial — ficha del paciente con evoluciones, estudios, archivos (radiografías, odontogramas) (comprobado); odontograma interactivo propio: **No evidenciado** (lo archiva, no lo edita).
- **Administración**: comprobada (declarada) — obras sociales y copagos configurados por profesional; **facturación electrónica por ARCA, válida para Monotributo y RI**; reportes y estadísticas.
- **Integraciones**: WhatsApp (comprobado), ARCA (declarado). Mercado Pago / Google Calendar / API: **No evidenciado**.
- **Operación**: multi-sede y multi-agenda (comprobado en planes), base de pacientes, perfil profesional web. Roles/auditoría/exportación: **No evidenciado**. Facturación del propio servicio por ARCA (comprobado en FAQ).
- **Seguridad**: "almacenamiento seguro con copias de respaldo" (afirmación genérica). Ley 25.326/26.529: **No evidenciado**.
- **Modelo comercial**: primer mes gratis. Precios publicados en ARS (2026-10-14): Argenti $9.000/mes (1 agenda), Aurum $25.000/mes (hasta 5 agendas); plan institucional $90.000/mes. Funciones listadas idénticas por plan salvo cantidad de agendas (verificar letra chica antes de contratar).
- **Fortalezas**: WhatsApp + ARCA + OS/copagos + marketplace de pacientes + asistente conversacional, a precio agresivo.
- **Limitaciones**: sin odontograma clínico real; sin pagos online evidenciados.
- **Adopción**: testimonios en sitio; cifras: **No evidenciadas**.

### 6. MedicAI — Argentina (salud general, referencia de cumplimiento)

- **Empresa / país**: MedicAI, Argentina (empresa argentina declarada).
- **URL oficial**: https://www.medicai.com.ar/ (consulta: 2026-10-14).
- **Segmento**: profesionales de salud y salud mental con consultorio propio (todas las especialidades).
- **Modalidad**: SaaS nube (comprobado).
- **Agenda**: comprobada — turnera pública online 24 h con link para redes; genera slots; multi-profesional por médico y sede.
- **Turnos digitales**: comprobado — turnera online + integración con Google Calendar (bidireccional declarada: lo ocupado en Google no se ofrece; turnos MedicAI aparecen en el calendario).
- **Automatización**: comprobada (declarada) — recordatorios automáticos por WhatsApp y e-mail.
- **Gestión odontológica**: **No evidenciado** (historia clínica general + receta electrónica; sin odontograma/periodontograma/presupuestos dentales).
- **Administración**: comprobada (declarada) — **cobro por Mercado Pago al reservar (seña del turno)**, facturación ARCA con bandeja de turnos atendidos y CAE al instante (nada se emite solo), compatibilidad con obras sociales (OSDE, Galeno, IOMA, Medicus, Accord, OMINT, Sancor, Prevención, Hospital Italiano — lista declarada).
- **Integraciones**: Mercado Pago, Google Calendar, WhatsApp, e-mail (declaradas); receta electrónica con firma electrónica, MFA y QR (declarada); teleconsulta en navegador con IA que redacta la nota (declarada).
- **Operación**: multi-profesional y multi-sede (declarado). Roles/auditoría/exportación: **No evidenciado** en lo consultado.
- **Seguridad y cumplimiento**: lo más sólido del relevamiento local — **aprobado por Ministerio de Salud ReNaPDiS N.º 292** (verificable en argentina.gob.ar, según el proveedor), HCE inmutable según Ley 26.529 (declarado), datos cifrados Ley 25.326 (declarado). Auditoría independiente: **No evidenciada** (se toma la declaración + registro oficial como referencia, no como prueba técnica).
- **Modelo comercial**: 30 días gratis sin tarjeta. Precio publicado: $25.900 + IVA por profesional/mes (incluye IA, turnera, HCE, ARCA). Moneda ARS.
- **Fortalezas / diferencial**: único con seña por Mercado Pago al reservar + ARCA + Google Calendar + ReNaPDiS + IA clínica, todo relevante para el MVP propio.
- **Limitaciones**: sin odontología (no sirve como gestión dental completa; sirve como referencia de turnos/cobros/cumplimiento y UX).
- **Adopción**: cifras/reseñas verificables: **No evidenciadas**.

### 7. Gendu — Argentina (turnos multivertical + Mercado Pago)

- **Empresa / país**: Gendu (desarrollado por Dinammica), Argentina.
- **URL oficial**: https://www.gendu.com.ar/ (consulta: 2026-10-14). Vertical salud: https://www.gendu.com.ar/planes/centros-medicos
- **Segmento**: negocios con atención por turnos (centros médicos, odontología, psicología, estética, tatuajes).
- **Modalidad**: SaaS nube (comprobado).
- **Agenda**: comprobada — agenda online, multi-profesional con acceso independiente, gestión de disponibilidad por médico/consultorio/duración.
- **Turnos digitales**: comprobado — página de reservas 24/7 personalizada (foto, redes, contacto, SEO), reservas sin crear cuenta compleja.
- **Automatización**: comprobada — recordatorios automáticos por WhatsApp y mail, confirmaciones; marketing (descuentos de cumpleaños).
- **Gestión odontológica**: parcial — historia clínica (declarada en vertical médica) e historia del paciente; odontograma/presupuestos dentales: **No evidenciado**.
- **Administración**: comprobada (declarada) — **cobros con Mercado Pago (pago anticipado o en el momento)**, pagos por transferencia, aranceles por consulta, gestión de obras sociales; reportes y estadísticas.
- **Integraciones**: Mercado Pago, WhatsApp, e-mail, calendario (agregar turno a calendario) (comprobadas/declaradas). ARCA/API/Google sync: **No evidenciado**.
- **Operación**: usuarios/profesionales múltiples (comprobado), base de clientes, historial de turnos. Roles/auditoría/exportación: **No evidenciado**.
- **Seguridad**: **No evidenciado**.
- **Modelo comercial**: plan Básico ARS $0 (agenda online, turnos ilimitados, recordatorios por mail, base de clientes, historial); plan Comercial ARS $9.100/mes (precios a fecha de consulta; verificar vigencia). Sin comisiones por reserva, sin permanencia (declarado). Moneda ARS.
- **Fortalezas**: entrada gratuita real + Mercado Pago + WhatsApp + vertical médica/odontológica.
- **Limitaciones**: sin odontograma ni ARCA evidenciados; historia clínica básica frente a un dental puro.
- **Adopción**: testimonios con nombre/especialidad/ciudad en el sitio (Cardiólogo BA, Clínica Córdoba — no verificados). Cifras: **No evidenciadas**.

### 8. iTurnos — Argentina (turnera genérica)

- **Empresa / país**: iTurnos, Argentina.
- **URL oficial**: https://iturnos.ar/ (consulta: 2026-10-14).
- **Segmento**: comercios, instituciones, profesionales, salud (consultorios, clínicas, laboratorios).
- **Modalidad**: SaaS nube + app mobile iOS/Android (comprobado).
- **Agenda**: comprobada — agendas múltiples (1/3/5 agendas según plan), turnos ilimitados, usuarios ilimitados.
- **Turnos digitales**: comprobado — reserva web 24/7/365, sitio web de una página incluido, reprogramación/anulación por el paciente.
- **Automatización**: comprobada (parcial) — confirmación y recordatorio por e-mail (48 h antes incluidos); agregue a calendarios Gmail/Yahoo/Outlook; reporte diario y mensual de ausentismo. SMS: opcional con costo. WhatsApp automático: **No evidenciado**.
- **Gestión odontológica**: **No evidenciado** (sin ficha/odontograma/presupuestos).
- **Administración**: reportes de ausentismo (comprobado). Caja/cobros/OS/ARCA/MP: **No evidenciado**.
- **Integraciones**: e-mail, calendarios externos (declaradas); SMS opcional; dominios/G Suite opcionales. API/WhatsApp/MP/ARCA: **No evidenciado**.
- **Operación**: multi-agenda/usuarios ilimitados (comprobado). Roles/auditoría/exportación/soporte: **No evidenciado** en lo consultado.
- **Seguridad**: **No evidenciado**.
- **Modelo comercial**: abono mensual por cantidad de agendas + IVA: 1 agenda AR $25.000/mes, 3 agendas AR $75.000/mes, 5 agendas AR $125.000/mes (a fecha de consulta). Moneda ARS.
- **Fortalezas**: simple, barato por agenda, multi-rubro, app móvil.
- **Limitaciones**: sin nada clínico ni administrativo dental; sin WhatsApp ni pagos.
- **Adopción**: logos de clientes ("confían en iTurnos") sin cifras. Datos verificables: **No evidenciados**.

### 9. Docturno — Argentina (marketplace + agenda médica)

- **Empresa / país**: Docturno, Argentina (fundada 2015, Buenos Aires; 8 empleados según Tracxn).
- **URL oficial**: https://www.docturno.com/ (consulta: 2026-10-14). Fuente secundaria: https://platform.tracxn.com (ficha Docturno).
- **Segmento**: profesionales y centros de salud que publican agenda; pacientes que reservan por especialidad/clínica/ubicación.
- **Modalidad**: SaaS web/marketplace (comprobado: fichas por centro con profesionales, horarios, coberturas, botón "agendar turno", enlace WhatsApp del profesional).
- **Agenda**: comprobada (parcial) — grilla por profesional con días/horarios, cobertura por profesional.
- **Turnos digitales**: comprobado — reserva online por ficha pública.
- **Automatización**: **No evidenciado** (sin recordatorios/confirmaciones publicados).
- **Gestión odontológica**: **No evidenciado** (publica odontólogos pero sin ficha clínica).
- **Administración**: gestión de coberturas/planes por profesional (comprobado). Caja/cobros/MP/ARCA: **No evidenciado** (algún profesional integra Mercado Pago por su cuenta para consulta online — no es función de la plataforma).
- **Integraciones**: link a WhatsApp del profesional (comprobado). API/ARCA/MP/Google: **No evidenciado**.
- **Operación**: multi-profesional/multi-centro por diseño marketplace (comprobado). Roles/auditoría/exportación/soporte: **No evidenciado**.
- **Seguridad**: **No evidenciado**.
- **Modelo comercial**: planes/ayuda/términos enlazados; precio público: **No evidenciado** en lo consultado.
- **Fortalezas**: captación (marketplace) + grilla de coberturas argentina real.
- **Limitaciones**: no es gestión odontológica; sin automatización ni administración.
- **Adopción**: fichas activas de centros (Esquel Diagnóstico, CMP, Omega Salud Mar del Plata, Centro Médico Corrientes — verificadas en el sitio). Cifras agregadas: **No evidenciadas**.

### 10. Doctoralia — Internacional (España; opera en Argentina)

- **Empresa / país**: Doctoralia Internet S.L., España (Grupo Docplanner). Opera en AR (doctoraliar.com), MX, CL, BR, PE, CO, ES, IT, etc.
- **URL oficial**: https://pro.doctoralia.es/ , https://www.doctoraliar.com/ (consulta: 2026-10-14).
- **Segmento**: especialistas, centros médicos, todas las especialidades.
- **Modalidad**: SaaS nube + marketplace (comprobado).
- **Agenda**: comprobada — agenda unificada multicanal, horarios presenciales/online, bloqueos, permisos para recepción, multi-dispositivo.
- **Turnos digitales**: comprobado — reserva 24/7, widget web, reservas desde Instagram/Facebook/Google Perfil/Doctoralia.
- **Automatización**: comprobada — recordatorios por e-mail/WhatsApp/SMS/push, confirmación/modificación/cancelación por el paciente, **lista de espera inteligente** que rellena huecos, campañas e-mail/SMS, reseñas automáticas, check-in automatizado.
- **Gestión odontológica**: parcial — expediente clínico digital + recetas (comprobado); odontograma/periodontograma/presupuestos dentales: **No evidenciado**.
- **Administración**: comprobada (declarada) — **pagos online** (con partner, comisión reducida según plan; útil como referencia de seña anti-no-show), videoconsulta, chat especialista-paciente, informes en tiempo real. ARCA/MP/obras sociales argentinas: **No evidenciado**.
- **Integraciones**: WhatsApp/SMS/e-mail/push, Google, redes sociales, widget (comprobadas); aseguradoras (España; en AR equivale a "obras sociales", sin evidencia local); API: **No evidenciado**.
- **Operación**: multi-sede/centros (planes para centros), roles de recepción, estadísticas avanzadas (comprobado). Auditoría/exportación: **No evidenciado**.
- **Seguridad**: RGPD europeo aplicable; Ley 25.326/ARCA locales: **No evidenciado**.
- **Modelo comercial**: trial/versión gratuita (declarada). Precios de referencia publicados por país (no hay precio AR publicado; se cita ES/MX/CL como referencia, moneda local): ES Starter 89 €/mes + IVA; MX Plus $1.620 + IVA/mes; CL Plus $69.000 CLP/mes (12 cuotas). **Precio Argentina: No evidenciado** (a cotizar).
- **Fortalezas**: estándar oro en turnos/automatización/marketplace; lista de espera; pagos anti-no-show.
- **Limitaciones**: sin odontología; sin encaje ARCA/MP/OS; precio enterprise para consultorio chico.
- **Adopción**: marketplace AR activo con fichas y opiniones (verificable en doctoraliar.com). Cifras globales del grupo: de público conocimiento pero fuera de este relevamiento sin fuente primaria citada → no se consignan.

### 11. Dentalink — Chile / LatAm (líder regional dental)

- **Empresa / país**: Dentalink (Engenis SpA), Chile; opera en +20 países, incluye LatAm y España.
- **URL oficial**: http://www.softwaredentalink.com/ y https://www.softwaredentalink.com/es/planes (consulta: 2026-10-14).
- **Segmento**: consultorios y clínicas dentales de cualquier tamaño.
- **Modalidad**: SaaS 100% nube, sin instalación, vía Chrome (comprobado).
- **Agenda**: comprobada — control de agenda, agendamiento, multi-centro, tareas automáticas de citas, carga masiva de pacientes.
- **Turnos digitales**: comprobado — agendamiento online.
- **Automatización**: comprobada — confirmación de citas, notificaciones automáticas, campañas por e-mail, encuestas, panel de tareas críticas; **Contact Center con IA 24/7 por WhatsApp y llamadas** que agenda/confirma/reprograma (declarado en sección IA); telemedicina; IA de notas clínicas por voz (−70% documentación, claim comercial), análisis de RX por IA, simulador de sonrisa, resumen clínico en 1 clic (declarados; eficacia **no verificada por tercero**).
- **Gestión odontológica**: comprobada — ficha/historia clínica digital, odontograma y periodontograma, módulos de ortodoncia y estética facial, plantillas, documentos personalizables, carga de imágenes/documentos, firma, consentimientos, videos 3D (algunos como adicionales según plan).
- **Administración**: comprobada — control de pagos, pagos presenciales y online, cobro en cuotas, financiamiento a pacientes, control de caja y gastos, cálculo de pago a odontólogos, gestión de convenios/seguros con reembolso en línea, inventario, informes de gestión y analítica.
- **Integraciones**: e-mail (comprobado); WhatsApp IA (declarado); facturación electrónica adaptable por país — en España VeriFactu (declarado); en Chile SII; **ARCA/MP para Argentina: No evidenciado**.
- **Operación**: multisucursal/multicentro, roles multi-usuario, chat interno (comprobados); migración y soporte sin costo adicional (declarado); actualizaciones gratuitas (declarado). Auditoría/exportación: **No evidenciado** en lo consultado.
- **Seguridad**: RGPD/VeriFactu en ES (declarado); para AR (Ley 25.326/26.529): **No evidenciado**.
- **Modelo comercial**: sin contratos/plazos mínimos (declarado); demo/acceso de prueba coordinado con ventas (comprobado). Precios: **no publicados, a cotización** (planes Esencial/Pro/Titanium). Pagos recurrentes mensuales/semestrales/anuales (declarado). Moneda según país.
- **Fortalezas**: el dental más completo de LatAm; IA integrada en agenda y clínica; convenios/seguros; escala probada.
- **Limitaciones**: precio opaco; encaje AR (ARCA/MP/OS) no evidenciado; porte enterprise para consultorio único.
- **Adopción**: proveedor declara +15.000 clientes, +12M pacientes únicos, +45M citas/año, +20 países (afirmación del proveedor, sin auditoría citada). Reseñas: Capterra (ES/AR) con ficha existente pero sin nota reproducida aquí por no haberse verificado el puntaje a fecha → **nota no consignada**.

### 12. DentiDesk — Chile / LatAm (dental + académico)

- **Empresa / país**: DentiDesk, Chile (Antonio Bellet 193, Providencia, Santiago; contacto@dentidesk.com, +56 9 7588 1906).
- **URL oficial**: https://www.dentidesk.cl/ y https://dentidesk.com/ (consulta: 2026-10-14).
- **Segmento**: clínicas dentales, centros médicos, sindicatos, universidades (DentiDesk Académico, MedicalDesk).
- **Modalidad**: SaaS nube (comprobado).
- **Agenda**: comprobada — agenda avanzada personalizable, modifica/reprograma, notas y recordatorios, app iOS.
- **Turnos digitales**: agenda online declarada; portal paciente detallado: **No evidenciado**.
- **Automatización**: envíos por correo migrados a AWS y CAPTCHA (changelog); recordatorios automáticos por canal: **No evidenciado** con precisión (no se afirma WhatsApp automático).
- **Gestión odontológica**: comprobada — historial médico completo, fichas especializadas (odontograma, disfunción, endodoncia, periodoncia, cirugía ortognática, ortodoncia), nomenclaturas chilena/internacional/universal, presupuestos con grupos de precios, firma en evoluciones, órdenes RX/laboratorio, recetas, consentimientos.
- **Administración**: comprobada — facturación propia integrada al SII (Chile), reportes financieros/administrativos (+20 tipos), gestión multisucursal, inventario.
- **Integraciones**: tributaria por país (SII en Chile; "integración fiscal de tu país" como claim — **ARCA: No evidenciado**), correo AWS. WhatsApp/API/Google/MP: **No evidenciado**.
- **Operación**: multisucursal, roles, reportes, app; demo gratis 15 días con acceso completo (comprobado). Auditoría/exportación: parcial (firma en evoluciones, trazabilidad de presupuestos citada en changelog; exportación general **No evidenciada**).
- **Seguridad**: **No evidenciado** (sin documentación pública hallada).
- **Modelo comercial**: trial 15 días; precios: **no publicados, a cotizar**.
- **Fortalezas**: profundidad clínica y académica; trazabilidad de evoluciones/presupuestos; multi-país LatAm.
- **Limitaciones**: sin WhatsApp/pagos evidenciados; sin ARCA; precio opaco.
- **Adopción**: ficha Capterra CL existente (puntaje no reproducido sin verificación); despliegue académico (UNAB citado en blog). Cifras: **No evidenciadas**.

### 13. AgendaPro — Chile / LatAm (multivertical belleza-salud)

- **Empresa / país**: AgendaPro Inc., Chile (opera en MX, AR, CO; contacto AR +54 11 5032 6351).
- **URL oficial**: https://agendapro.com/es (consulta: 2026-10-14).
- **Segmento**: salones, spa, estética, barberías y salud (fisio, psicología, nutrición, clínicas).
- **Modalidad**: SaaS nube (comprobado).
- **Agenda**: comprobada — gestión de citas y calendarios, multi-sucursal.
- **Turnos digitales**: comprobado — sitio de reservas 24/7, reservas online, Google Reserve, LinkPro.
- **Automatización**: comprobada — recordatorios automáticos por WhatsApp y e-mail; **Sofía (IA para agendar)** y **Julia (IA para ventas)** (declaradas); marketing/e-mailing, lealtad/giftcards, marketplace.
- **Gestión odontológica**: parcial — ficha del cliente, historial de servicios, control de sesiones/tratamientos (comprobado); odontograma interactivo: **No evidenciado** (fuente tercera NacarOS afirma que AgendaPro "anexa un odontograma no interactivo" — se consigna como afirmación de tercero, no verificada en el sitio oficial).
- **Administración**: comprobada — pagos electrónicos y con terminal, cierres de caja, registro/reportes de pagos, pago de sesiones, comisiones, rentabilidad, ingresos/egresos; facturación (declarada sin detalle fiscal AR).
- **Integraciones**: WhatsApp, Google (Reserve/My Business), pagos electrónicos/terminal (declaradas). Mercado Pago / ARCA / API: **No evidenciado** en lo consultado.
- **Operación**: multi-sucursal, CRM, inventario con alertas, informes 360 con IA, academia/onboarding, soporte 24/7 (declarados). Roles/auditoría/exportación: **No evidenciado** en detalle.
- **Seguridad**: **No evidenciado**.
- **Modelo comercial**: prueba gratis (declarada). Precios AR: **No evidenciado** en la página consultada (una fuente tercera cita plan Premium $1.500 MXN para equipo de 4 — no verificado en oficial → no se adopta como dato). Claims de escala (+20.000 negocios, +135.000 citas — cifras del sitio a fecha, tomar como afirmación del proveedor).
- **Fortalezas**: automatización + IA + marketing + pagos, con presencia AR.
- **Limitaciones**: sin odontología real; sin ARCA/MP evidenciados.
- **Adopción**: claims del proveedor arriba citados; reseñas verificables: **No evidenciadas** en este relevamiento.

### 14. NacarOS — Argentina (dental, precio publicado en USD)

- **Empresa / país**: NacarOS, Argentina (orientado a BA/Córdoba/Rosario).
- **URL oficial**: https://www.nacaros.com/software-dental-argentina (consulta: 2026-10-14).
- **Segmento**: consultorios odontológicos argentinos (incluye quien alquila sillón).
- **Modalidad**: SaaS nube, multi-dispositivo (comprobado/declarado).
- **Agenda**: agenda declarada (detalle funcional no verificado en profundidad) → **parcialmente evidenciada**.
- **Turnos digitales**: reserva/turnos declarados; portal: **No evidenciado** en detalle.
- **Automatización**: declarada — **WhatsApp con IA** (confirmaciones y solicitud de turnos) (declarado en el sitio).
- **Gestión odontológica**: declarada — odontograma 34 FDI + periodontograma con dictado por voz, visor Rx/fotos, recetas PDF, alergias visibles, evoluciones con fecha/responsable.
- **Administración**: declarada — registro de cobros (transferencia, **Mercado Pago**), cierre de caja.
- **Integraciones**: Mercado Pago, WhatsApp IA (declaradas). ARCA/API/Google: **No evidenciado**.
- **Operación**: migración desde Excel/papel gratis (declarada). Roles/auditoría/exportación/soporte: **No evidenciado** en lo consultado (soporte por WhatsApp declarado en plan Free).
- **Seguridad**: documento/teléfono/notas "cifrados en la base" (declarado; sin prueba técnica). Ley 25.326/26.529: **No evidenciado**.
- **Modelo comercial**: Plan Básico gratis permanente hasta 20 pacientes; Plan Pro $14,99 USD/mes (~$22.600 ARS según el sitio); 30 días gratis sin tarjeta; sin contrato/permanencia, cancela en 1 clic (declarado).
- **Fortalezas**: precio publicado imbatible + MP + WhatsApp IA + dictado por voz.
- **Limitaciones**: todo lo clínico/administrativo es declaración del proveedor sin demo verificada en este relevamiento; sin ARCA/OS.
- **Adopción**: cifras/reseñas: **No evidenciadas**.

### 15. Odonthia — Argentina (dental freemium + IA por créditos)

- **Empresa / país**: Odonthia, Argentina.
- **URL oficial**: https://odonthia.com/planes (fuente indirecta: comparativa publicada por NacarOS que cita documentación pública de Odonthia verificada el 09–13/09/2026; sitio oficial no consultado en profundidad en este relevamiento).
- **Datos consignados con cautela**: gestión del consultorio **gratis sin límite de pacientes** (afirmación de tercero basada en documentación pública); IA cobrada aparte por créditos desde US$29/mes fuera de Argentina (ídem). Resto de dimensiones: **No evidenciado** en este relevamiento (requiere verificación directa antes de afirmar).
- **Relevancia**: modelo freemium agresivo local; exige demo de verificación antes de usarlo como benchmark de precio.

### 16. Fresha — Reino Unido / internacional (marketplace belleza-salud)

- **Empresa / país**: Fresha, Reino Unido (opera globalmente).
- **URL oficial**: https://www.fresha.com/en-GB/pricing (consulta: 2026-10-14).
- **Segmento**: salones, spa, barberías, clínicas estéticas/salud (no dental-específico).
- **Modalidad**: SaaS nube + marketplace + app de reservas (comprobado).
- **Agenda**: comprobada — calendario por profesional (Independent 1 columna / Team múltiples).
- **Turnos digitales**: comprobado — link directo, Facebook/Instagram/Google, marketplace Fresha, app.
- **Automatización**: mensajes y marketing e-mail incluidos con límites (100 mensajes / 50 e-mails en Independent); AI Concierge 24/7 (USD 99,95/local/mes) (comprobado en pricing). WhatsApp nativo: **No evidenciado**.
- **Gestión odontológica**: **No evidenciado** (sin odontograma/HCE dental).
- **Administración**: comprobada — pagos anticipados, cargos por no-show/cancelación, pagos online (2,79% + $0,20) y presenciales (2,29% + $0,20), lealtad, impulso de reseñas Google, insights. Mercado Pago / ARCA / obras sociales: **No evidenciado**.
- **Integraciones**: Facebook/Instagram/Google/marketplace (comprobadas); pagos propios. API/Data Connector como add-on USD 295/local/mes (comprobado). WhatsApp/ARCA/MP: **No evidenciado**.
- **Operación**: multi-local, roles por add-ons (Team Connect, Insights), reportes (comprobado). Auditoría/exportación: **No evidenciado** en detalle.
- **Seguridad**: estándares internacionales propios; Ley 25.326/ARCA: **No evidenciado**.
- **Modelo comercial**: suscripción por profesional bookable + prueba 7 días: Independent $19,95/mes, Team $14,95/mes por miembro (pricing oficial a fecha). **Comisión 20% (mín. $6) por cliente nuevo vía marketplace**; recurrentes sin fee. Moneda USD.
- **Fortalezas**: Marketplace que trae pacientes + pagos con no-show fees (inspiración directa para la seña) + pricing transparente.
- **Limitaciones**: sin odontología, sin encaje AR, comisión agresiva si se usa captación.
- **Adopción**: marketplace global activo (verificable); cifras agregadas no consignadas sin fuente primaria.

### 17. SimplyBook.me — Internacional (turnera genérica, referencia HIPAA)

- **Empresa / país**: SimplyBook.me (opera globalmente; enfoque salud/belleza/educación).
- **URL oficial**: https://simplybook.me/en y vertical dental https://simplybook.me/en/online-appointment-software-for-medical-companies-clinics-doctors-and-healthcare/dental-appointment-software (consulta: 2026-10-14).
- **Segmento**: clínicas médicas/dentales, servicios con cita.
- **Modalidad**: SaaS nube (comprobado).
- **Agenda**: comprobada — horarios, pausas, feriados por staff, multi-sucursal con dashboard centralizado, geolocalizador por sucursal.
- **Turnos digitales**: comprobado — web de reservas personalizable 24/7, widget web, Facebook/Instagram/Google/Booking.page.
- **Automatización**: comprobada — recordatorios SMS/e-mail, notificaciones "Book Soon", formularios de intake, login de clientes.
- **Gestión odontológica**: parcial — vertical dental con ficha/pagos/reseñas; odontograma/HCE dental: **No evidenciado**.
- **Administración**: comprobada (parcial) — pagos online al reservar y POS; reportes/KPI. ARCA/MP/OS: **No evidenciado**.
- **Integraciones**: Google/Outlook sync bidireccional, pagos, intake forms (comprobadas); **HIPAA compliance + cifrado estándar** (declarado — referencia de seguridad). WhatsApp nativo/ARCA/MP: **No evidenciado**.
- **Operación**: multi-sucursal, gestión de empleados, app admin, video-tutoriales, live-chat 24/7 (declarados). Roles/auditoría/exportación: **No evidenciado** en detalle.
- **Seguridad**: HIPAA + cifrado (declarado). Ley 25.326/26.529 AR: **No evidenciado**.
- **Modelo comercial**: plan gratuito (hasta 50 reservas/mes según comparativa de su blog) + prueba premium 14 días; precio numérico del plan pago: **No evidenciado** en lo consultado (requiere pricing oficial por tamaño).
- **Fortalezas**: turnera más configurable + higiene de seguridad (HIPAA) + pagos al reservar (inspiración para seña).
- **Limitaciones**: sin odontología ni encaje AR.
- **Adopción**: casos (Mandel Dermatology, citado por el proveedor). Cifras agregadas: **No evidenciadas**.

### 18. DriCloud / XDentalCloud — España / EE. UU. (médico + dental, referencia IA/cumplimiento)

- **Empresa / país**: DriCloud (Massive Bionics LLC, EE. UU.; equipo ES); fundado 2012; XDentalCloud = vertical dental.
- **URL oficial**: https://dricloud.com/ , https://dricloud.com/empresa , https://dricloud.com/gestion-clinica (consulta: 2026-10-14).
- **Segmento**: clínicas/consultas multi-especialidad + dental (hasta 300 personas por cliente, según el proveedor).
- **Modalidad**: SaaS nube privada por clínica, sobre Microsoft Azure (declarado).
- **Agenda**: comprobada (declarada) — multi-sede/multi-consulta sincronizada, cita online 24/7.
- **Turnos digitales**: comprobado (declarado) — reservas desde la web directo a agenda.
- **Automatización**: declarada — recordatorios; CRM médico con automatizaciones web→reserva; IA "Escucha Clínica" que redacta la HCE por voz; informes en 1 clic; chatbot web.
- **Gestión odontológica** (XDentalCloud): historia configurable por especialidad, consentimientos para firmar, receta electrónica privada, pruebas/laboratorios, telemedicina, portal del paciente Vitales, módulos de urgencias/quirófano/hospitalización activables sin costo extra (declarados). Odontograma detallado: **No evidenciado** en lo consultado.
- **Administración**: declarada — producción/facturación en tiempo real, reporte financiero por paciente, liquidación a profesionales, stock con autor por movimiento, flujo de pacientes; facturación electrónica VeriFactu/TicketBAI (ES).
- **Integraciones**: SMS/WhatsApp/e-mail, Top Doctors, Zoho CRM, VidSigner firma remota, TicketBAI (declaradas). Mercado Pago / ARCA / Google Calendar: **No evidenciado**.
- **Operación**: multi-sede, fichaje del personal, estadísticas exportables a Excel (declaradas); importación desde Excel gratuita (declarada); demo completa sin tarjeta en 2 minutos (declarada). Roles/auditoría: **No evidenciado** en detalle.
- **Seguridad y cumplimiento**: RGPD/LOPD/HIPAA, Azure, disponibilidad 99,98% (declarados); garantía RGPD y contrato publicados (declarados). Ley 25.326/26.529 AR y ARCA: **No evidenciado**.
- **Modelo comercial**: planes claros sin alta ni permanencia (declarado); precio numérico: **No evidenciado** en lo consultado (requiere página de precios).
- **Fortalezas**: referencia de arquitectura (nube privada, multi-módulo incluido, IA clínica, CRM) y de cumplimiento europeo.
- **Limitaciones**: sin encaje AR; sin odontograma verificado; precio no relevado.
- **Adopción**: proveedor declara 8.000+ clientes en 14 países, 12 años, +50 especialidades; reseñas 5★ citadas (Contacto Visión y Belleza, Todosaluddental) y premios Software Advice — todo afirmación del proveedor sin auditoría citada.

### Referencia adicional EE. UU. (no puntuada en matriz, solo para calibrar techo enterprise)

- **Open Dental** (EE. UU., 2003): gestión dental completa, altamente personalizable, odontograma 3D, ortodoncia, seguros/billing USA; ~$199/mes por ubicación + eServices; calificaciones ~4,5/5 en directorios. Fuente: https://www.opendental.com/ (consulta: 2026-10-14). Sin encaje AR (seguros USA ≠ obras sociales; sin ARCA/MP/WhatsApp). Se cita como techo funcional, no como alternativa viable para el consultorio argentino.
- **Curve Dental / Dentrix Ascend / CareStack / tab32** (EE. UU.): nube all-in-one con imaging, eClaims, IA; precios publicados parciales (tab32 desde $125–225/mes; CareStack ~$698+/mes; Curve/Ascend a cotización) y ratings Capterra 4,1–4,8. Fuentes: https://www.curvedental.com/pricing , https://tab32.com/dentrix-ascend-alternative , https://www.capterra.com/compare/2329-177828/Dentrix-vs-Dentrix-Ascend (consulta: 2026-10-14). Sin encaje AR. Inspiración para UX de agenda/planes de tratamiento/facturación integrada, no para cumplimiento local.

---

## B. Matriz de puntuación 0–5 (pesos del brief) + ranking

**Escala**: 0 = ausente/sin evidencia; 1 = mención marginal; 2 = básico; 3 = sólido; 4 = avanzado; 5 = referente.
**Pesos**: Turnos y automatización (T) 25% · Clínica odontológica (C) 20% · Integraciones locales y WhatsApp (I) 15% · Administración/cobros/facturación (A) 15% · Experiencia paciente (E) 10% · Seguridad/exportación/trazabilidad (S) 10% · Precio/adopción (P) 5%.
**Fórmula**: `Ponderado = 0,25·T + 0,20·C + 0,15·I + 0,15·A + 0,10·E + 0,10·S + 0,05·P`.
**Criterio**: solo puntúa lo evidenciado; los claims sin prueba no suben nota (se penaliza encaje AR no evidenciado en I/S).

| # | Sistema | T (25%) | C (20%) | I (15%) | A (15%) | E (10%) | S (10%) | P (5%) | **Ponderado** |
|---|---------|---------|---------|---------|---------|---------|---------|---------|----------------|
| 1 | DentalSoft (AR) | 5 | 5 | 3 | 4 | 5 | 2 | 3 | **4,25** |
| 2 | Dentalink (CL/LatAm) | 5 | 5 | 2 | 5 | 4 | 2 | 1 | **3,95** |
| 3 | DoctorYa (AR) | 4 | 2 | 4 | 3 | 4 | 2 | 5 | **3,30** |
| 4 | MedicAI (AR) | 4 | 1 | 4 | 4 | 3 | 4 | 3 | **3,25** |
| 5 | Dentaly (AR) | 4 | 4 | 2 | 3 | 3 | 1 | 2 | **3,05** |
| 6 | DentiClick (AR) | 3 | 4 | 1 | 3 | 4 | 2 | 2 | **2,85** |
| 7 | SOMOSDENTO (AR) | 3 | 3 | 2 | 4 | 3 | 1 | 2 | **2,75** |
| 8 | Gendu (AR) | 4 | 1 | 3 | 3 | 4 | 1 | 5 | **2,85** |
| 9 | AgendaPro (CL/LatAm) | 4 | 1 | 2 | 3 | 4 | 1 | 2 | **2,55** |
| 10 | DentiDesk (CL/LatAm) | 3 | 5 | 1 | 3 | 2 | 2 | 1 | **2,80** |
| 11 | Doctoralia (INT/AR) | 5 | 1 | 2 | 3 | 5 | 2 | 1 | **2,95** |
| 12 | NacarOS (AR) | 3 | 3 | 3 | 2 | 2 | 2 | 5 | **2,75** |
| 13 | Fresha (UK) | 4 | 0 | 1 | 4 | 4 | 1 | 3 | **2,30** |
| 14 | SimplyBook.me (INT) | 4 | 1 | 1 | 2 | 4 | 3 | 3 | **2,50** |
| 15 | DriCloud/XDental (ES) | 3 | 3 | 1 | 3 | 3 | 3 | 1 | **2,60** |
| 16 | iTurnos (AR) | 3 | 0 | 1 | 1 | 3 | 0 | 4 | **1,55** |
| 17 | Docturno (AR) | 2 | 0 | 1 | 1 | 3 | 0 | 2 | **1,20** |
| — | Odonthia (AR) | — | — | — | — | — | — | — | **No puntuada (evidencia insuficiente — requiere demo)** |

**Ranking (por ponderado)**: 1) DentalSoft 4,25 · 2) Dentalink 3,95 · 3) DoctorYa 3,30 · 4) MedicAI 3,25 · 5) Dentaly 3,05 · 6) Doctoralia 2,95 · 7) DentiClick 2,85 = Gendu 2,85 · 9) DentiDesk 2,80 · 10) SOMOSDENTO 2,75 = NacarOS 2,75 · 12) DriCloud 2,60 · 13) AgendaPro 2,55 · 14) SimplyBook.me 2,50 · 15) Fresha 2,30 · 16) iTurnos 1,55 · 17) Docturno 1,20.

> Nota metodológica: el peso del brief (25% turnos + 20% clínica + 15% integraciones locales) premia el encaje argentino. Por eso un dental puro chileno (DentiDesk) puntúa alto en clínica pero cae en integraciones locales, y un turnero genérico barato (iTurnos) cae por falta de clínica/administración. Gendu empata con DentiClick por precio + MP + WhatsApp pese a su clínica débil. Odonthia no se puntúa para no premiar lo no verificado.

---

## C. Análisis competitivo

### C.1. Estándares de mercado (lo que el paciente/consultorio ya espera)

1. **Reserva online 24/7 con slots en tiempo real**: estándar en 13/18 sistemas (DentalSoft, DentiClick, Dentaly, SOMOSDENTO, DoctorYa, MedicAI, Gendu, iTurnos, Docturno, Doctoralia, Dentalink, AgendaPro, Fresha, SimplyBook). Flujo canónico en 3–4 pasos (datos → profesional → fecha/hora → confirmación) con reconocimiento por DNI y confirmación inmediata. Quien no lo tiene, no compite.
2. **Agenda por profesional con vistas día/semana/mes + bloqueos + reprogramación con liberación automática del hueco**: estándar en dentales puros y turneras. Drag & drop (DentalSoft), detección de solapamiento y urgencias/sobre-turnos (DentalSoft, Doctoralia-lista de espera, Fresha/SimplyBook-relleno) son el techo.
3. **Recordatorios automáticos multicanal**: estándar regional = WhatsApp + e-mail (+ SMS/push en enterprise). DentalSoft, Dentaly, DoctorYa, MedicAI, Gendu, Dentalink, AgendaPro, Doctoralia, Fresha, SimplyBook lo declaran. La diferencia está en si la respuesta del paciente actualiza la agenda sola (DentalSoft Pro, Doctoralia, Dentalink IA) o requiere operador (DentalSoft Gestión-manual).
4. **Ficha + odontograma + presupuestos + cobros en un solo lugar**: estándar dental (DentalSoft, DentiClick, Dentaly, SOMOSDENTO, Dentalink, DentiDesk, NacarOS). Odontograma interactivo FDI con historial por pieza y periodontograma es el piso clínico; ortodoncia/estética, firma de consentimientos y recetas son el techo.
5. **Marketplace/perfil público para captar**: estándar en Doctoralia, Fresha, Docturno, DoctorYa, Gendu (página/SEO), DentalSoft (web propia), DentiClick (mini-web). El consultorio espera "que me encuentren y reserven sin llamarme".
6. **Precios publicados y trial sin tarjeta**: estándar de conversión (DentalSoft, Gendu, NacarOS, MedicAI, Fresha, SimplyBook, DentiClick-mes gratis, DentiDesk-15 días, SOMOSDENTO-30 días). Dentalink/DentiDesk/Doctoralia-AR rompen el estándar (a cotización) y generan fricción.

### C.2. Diferenciadores reales (comprobados, no slogans)

- **Encaje argentino total**: solo DentalSoft combina OS + liquidaciones + Mercado Pago + WhatsApp + web con turnos. DoctorYa/MedicAI aportan ARCA + OS/copagos; SOMOSDENTO aporta ARCA dental; Gendu aporta MP + WhatsApp barato; MedicAI aporta seña al reservar + Google Calendar + ReNaPDiS.
- **Cobro de seña al reservar**: solo MedicAI (MP al reservar) y Fresha/SimplyBook (pagos anticipados / no-show fees) lo tienen operativo. En dentales argentinos puros es vacío: DentalSoft cobra en caja pero no declara seña online al reservar. Esto valida la apuesta del Discovery (seña monto fijo) como diferencial local.
- **IA aplicada**: Dentalink (Contact Center 24/7 + notas por voz + RX), AgendaPro (Sofía/Julia), DoctorYa (asistente conversacional), DentalSoft (recepcionista virtual), MedicAI/DriCloud (nota clínica por voz). Ninguno publica métricas auditadas; son diferenciadores de marketing hasta que se prueben.
- **Cumplimiento**: MedicAI (ReNaPDiS 292 + Ley 26.529/25.326 declarados) y DriCloud (RGPD/HIPAA/Azure) son los únicos que hablan el idioma regulatorio. El resto del mercado argentino opera en silencio normativo (riesgo y oportunidad).
- **Trazabilidad clínica**: DentiDesk (firma en evoluciones, presupuestos protegidos), DentalSoft (historial por pieza con profesional/fecha, anulaciones con trazabilidad), DentiClick (historial con versiones). Nadie ofrece auditoría global exportable con estándar forense.

### C.3. Vacíos frecuentes en Argentina (oportunidades)

1. **Seña online con reglas de devolución (100%/60%/0%)**: nadie la implementa con la política del Discovery. Oportunidad directa.
2. **ARCA + Mercado Pago + obras sociales en un mismo flujo dental**: fragmentado (ARCA en SOMOSDENTO/MedicAI/DoctorYa; MP en DentalSoft/Gendu/MedicAI/NacarOS; OS en DentalSoft/DentiClick/Dentaly/SOMOSDENTO/DoctorYa). Nadie une los tres en agenda→reserva→seña→factura→liquidación OS.
3. **Recordatorios por e-mail bien hechos (entregabilidad, no spam)**: todos priorizan WhatsApp (con costo por mensaje); el e-mail es ciudadano de segunda. El Discovery apuesta a mail en v1 — hay espacio para hacerlo mejor (SPF/DKIM/DMARC, plantillas, reintentos, métricas) mientras se diseña para sumar WhatsApp en v2 sin romper.
4. **Transparencia de precios y evidencia**: precios ocultos (Dentalink, DentiDesk, Doctoralia AR, Dentaly, SOMOSDENTO), métricas sin metodología ("−65/−82% ausentismo"), testimonios sin verificación. Un producto con precio público, changelog y métricas propias gana confianza.
5. **Seguridad y privacidad explicadas**: cifrado, backups, roles, exportación, retención, consentimiento (Ley 25.326) y HCE (Ley 26.529) casi nunca documentados. Trazabilidad de cancelaciones/devoluciones de seña, esencial para disputas, ausente.
6. **Single-sede simple y barato**: el mercado empuja multi-sede/enterprise. Un v1 single-sede, con diseño que no bloquee multi-sede futura, ataca al consultorio chico desatendido (el de papel/WhatsApp informal del Discovery).
7. **Sobre-turnos y WhatsApp como deuda explícita**: el mercado los da por sentados; el Discovery los excluye de v1 conscientemente. La oportunidad es diseñar el modelo (slots, estados, lista de espera) para activarlos en v2 sin migraciones.

### C.4. Oportunidades de innovación (compatibles con el stack FastAPI/React y el plazo académico)

- **Motor de seña**: pago al reservar (Mercado Pago), estados (en término 100% / fuera de término 60% / no-show 0%), liberación automática del hueco, bandeja de devoluciones y comprobantes. Inspiración: MedicAI (cobro al reservar) + Fresha (no-show fees) + ARCA-API/TusFacturasAPP (factura + link de pago).
- **Recordatorios por mail de alta entregabilidad**: Redis para colas/reintentos, plantillas, ventana configurable (p. ej. 24 h), estados confirmado/cancelado que liberan el slot. Diseñar el conector para WhatsApp Business API en v2 (DentalSoft/DoctorYa muestran el UX esperado).
- **Disponibilidad por odontólogo + agenda del día a prueba de choques**: reglas del Discovery (sin pasado, sin doble-reserva, tope/duración, anticipación mínima) como constraints de dominio, no como validación de UI. Inspiración UX: DentalSoft (drag & drop, chips), DoctorYa (vista del día con estados), SimplyBook (pausas/feriados por staff).
- **Trazabilidad mínima viable**: cada turno con historial de estados (creado/confirmado/cancelado/reprogramado/devuelto) con actor y fecha; exportación CSV/PDF de turnos y caja. Supera al 80% local sin costo enterprise.
- **Puente ARCA/MP**: aunque ARCA quede fuera de v1, modelar comprobante/pago como entidades separadas del turno (patrón ARCA-API: comprobante + link de pago + conciliación) para no refactorizar en v2.

---

## D. Recomendación final

### D.1. Cinco competidores prioritarios para demo (orden de demo sugerido)

1. **DentalSoft** (https://dentalsoft.com.ar/) — demo instantánea con datos de ejemplo + planes Gestión/Pro. Ver: agenda drag & drop, sobre-turnos, odontograma 18 estados, caja con Mercado Pago, liquidaciones OS/profesionales, recordatorios manual vs automático, web con turnos. Es el benchmark funcional argentino más completo.
2. **MedicAI** (https://www.medicai.com.ar/) — trial 30 días. Ver: turnera pública + Google Calendar bidireccional, **seña por Mercado Pago al reservar**, bandeja ARCA con CAE, recordatorios WhatsApp/mail, HCE con IA. Es la referencia de cobros/cumplimiento para el MVP.
3. **Dentalink** (http://www.softwaredentalink.com/) — demo coordinada con ventas. Ver: agenda multi-centro, confirmación/notificaciones, odontograma/periodontograma, convenios, caja/gastos/comisiones, IA (Contact Center, notas por voz). Es el techo LatAm dental.
4. **DoctorYa** (https://doctorya.com.ar/) — registro gratis, primer mes gratis. Ver: agenda por profesional/sede, reserva por buscador + chat, recordatorios WhatsApp con confirmación, OS/copagos, ARCA Monotributo/RI, reportes. Es la referencia de turnos/ARCA a precio agresivo ($9.000–$25.000 ARS).
5. **Gendu** (https://www.gendu.com.ar/) — cuenta gratis (plan $0) + Comercial $9.100 ARS. Ver: página de reservas 24/7, recordatorios WhatsApp/mail, cobro MP anticipado, historia básica, reportes. Es la referencia de simplicidad/precio y de UX de reserva de baja fricción.
- **Suplentes**: DentiClick (mini-web + OS/nomenclador), SOMOSDENTO (ARCA dental + portal por profesional), Doctoralia (lista de espera + pagos anti-no-show como inspiración enterprise).

### D.2. Tres referencias de UX a imitar (con qué robar de cada una)

1. **DentalSoft — agenda y caja**: semana con drag & drop y confirmación, chips por día, urgencias con detección de solapamiento, caja del día con métodos (incl. Mercado Pago) y cierre en segundos, liquidaciones con vista previa y PDF. Robar: densidad de agenda + trazabilidad caja→turno.
2. **MedicAI — reserva con seña y cumplimiento**: turnera pública con link, Google Calendar que bloquea huecos, cobro MP al reservar, bandeja "turnos atendidos → facturar → CAE", receta/HCE en una pantalla. Robar: flujo reserva→pago→comprobante sin fricción y lenguaje regulatorio claro.
3. **Doctoralia / Fresha — automatización anti-no-show**: recordatorios multicanal con confirmar/cancelar/reprogramar por el paciente, **lista de espera que rellena huecos** (Doctoralia), cargos por no-show y link de pago (Fresha). Robar: estados y microcopy de confirmación; diseñar la lista de espera como apagada en v1 pero modelada.

### D.3. MVP sugerido (consistente con `discovery/discovery.md`)

**Imprescindibles (v1)**:
- Alta de disponibilidad por odontólogo (duración estándar, tope/día, pausas/feriados) + agenda del día sin choques (sin pasado, sin doble-reserva).
- Reserva online por el paciente (3–4 pasos, reconocimiento por DNI) + cancelación/reprogramación (paciente y odontólogo/admin) con **liberación automática del hueco** y anticipación mínima configurable.
- **Seña de monto fijo pagada al reservar** (Mercado Pago como proveedor sugerido) con política del Discovery: en término 100%, fuera de término 60%, no-show 0%; bandeja de devoluciones y comprobantes.
- **Recordatorios automáticos por mail** (única vía v1; Redis para colas/reintentos; plantillas; entregabilidad SPF/DKIM/DMARC) con confirmar/cancelar que actualiza la agenda.
- Roles paciente / odontólogo / admin-recepcionista (opcional, sin trabar si no existe); single-sede; historial de estados por turno (actor + fecha); reportes mínimos de asistencia; exportación CSV/PDF.

**Diferenciadores v1** (lo que el mercado local no une):
- Motor de seña con reglas de devolución + trazabilidad + conciliación MP; e-mail de alta entregabilidad con métricas; modelo de datos preparado para ARCA (comprobante separado del turno) aunque la emisión quede apagada; UX de reserva de baja fricción (referencia Gendu/MedicAI) con robustez de agenda (referencia DentalSoft).

**Postergables (v2+, diseñar para no bloquear)**:
- **WhatsApp** (recordatorios, confirmación, bot/asistente) — decisión consciente del Discovery; dejar conector y plantillas modeladas.
- **Sobre-turnos y lista de espera** — modelar estados/slots para activarlos sin migración.
- Multi-sede/multi-odontólogo pleno, obras sociales y facturación ARCA automática, historia clínica/odontograma completo, Google Calendar sync, app móvil, campañas/IA.

---

## Fuentes (verificables, consulta 2026-10-14)

1. DentalSoft — https://dentalsoft.com.ar/ (funcionalidades, agenda, odontograma, caja/MP, OS/liquidaciones, WhatsApp, planes $30.000/$60.000 ARS, demo, +300 clínicas claim).
2. DentiClick — https://www.denticlick.app/ (agenda, mini-web reservas, odontograma, OS/nomenclador, insumos, mes gratis).
3. Dentaly — https://www.dentaly.com.ar/ (agenda, odontograma, finanzas, WhatsApp −65% claim, demo).
4. SOMOSDENTO — https://somosdento.com/ (agenda, portal por profesional, ficha/odontograma, ARCA A/B/C, inventario, demo 30 días).
5. DoctorYa — https://doctorya.com.ar/ (agenda/sedes, reserva + chat, WhatsApp, ficha/odontogramas, OS/copagos, ARCA, planes $9.000/$25.000/$90.000 ARS).
6. MedicAI — https://www.medicai.com.ar/ (turnera, Google Calendar, WhatsApp/mail, MP al reservar, ARCA/CAE, OS listadas, ReNaPDiS 292, $25.900+IVA).
7. Gendu — https://www.gendu.com.ar/ + https://www.gendu.com.ar/planes/centros-medicos (agenda multi-profesional, reservas 24/7, WhatsApp/mail, MP, historia, planes $0/$9.100 ARS).
8. iTurnos — https://iturnos.ar/ (agendas 1/3/5 a $25.000/$75.000/$125.000 + IVA, e-mail 48 h, app, reportes ausentismo).
9. Docturno — https://www.docturno.com/ (fichas verificadas: Esquel Diagnóstico, CMP, Omega Salud, Centro Médico Corrientes) + ficha Tracxn (AR, 2015, 8 empleados).
10. Doctoralia PRO — https://pro.doctoralia.es/productos/funcionalidades , https://pro.doctoralia.es/precios/para-especialistas (89 €/mes ES), https://pro.doctoralia.cl/precios (69.000 CLP Plus), https://pro.doctoralia.com.mx/precios/medicos-y-especialistas ($1.620 MXN Plus), https://www.doctoraliar.com/ (marketplace AR).
11. Dentalink — http://www.softwaredentalink.com/ + https://www.softwaredentalink.com/es/planes (+15.000 clientes/+12M pacientes/+45M citas/+20 países claim; planes Esencial/Pro/Titanium a cotización; IA).
12. DentiDesk — https://www.dentidesk.cl/ + https://dentidesk.com/ (agenda, fichas/odontograma, SII, multisucursal, trial 15 días, contacto Santiago).
13. AgendaPro — https://agendapro.com/es (agenda, reservas 24/7, WhatsApp/mail, Sofía/Julia IA, pagos, soporte 24/7, contacto AR).
14. NacarOS — https://www.nacaros.com/software-dental-argentina (Free hasta 20 pacientes, Pro $14,99 USD, WhatsApp IA, MP, dictado por voz) — incluye comparativa con AgendaPro/Dentalink/Odonthia/DentalCore citada con cautela.
15. Fresha — https://www.fresha.com/en-GB/pricing (Independent $19,95 / Team $14,95, 20% marketplace, pagos 2,79%/2,29%, AI Concierge $99,95).
16. SimplyBook.me — https://simplybook.me/en + vertical dental https://simplybook.me/en/online-appointment-software-for-medical-companies-clinics-doctors-and-healthcare/dental-appointment-software (agenda multi-sucursal, recordatorios, pagos al reservar, HIPAA).
17. DriCloud — https://dricloud.com/ + https://dricloud.com/empresa + https://dricloud.com/gestion-clinica (8.000+ clientes/14 países claim, Azure, RGPD/HIPAA, VeriFactu, IA Escucha Clínica, demo sin tarjeta).
18. Referencias complementarias — Open Dental https://www.opendental.com/ ; Curve https://www.curvedental.com/pricing ; tab32 https://tab32.com/dentrix-ascend-alternative ; Capterra https://www.capterra.com/compare/2329-177828/Dentrix-vs-Dentrix-Ascend ; ARCA-API https://arca.api.com.ar/ ; TusFacturasAPP https://www.tusfacturas.app/integracion-mercadopago-pago-online.html (patrón factura ARCA + link MP, útil para v2).
19. Contexto del proyecto — `discovery/discovery.md` (2026-10-14; recordatorios por mail, seña monto fijo 100%/60%/0%, single-sede v1, sin WhatsApp ni sobre-turnos en v1).

## Limitaciones del relevamiento

- **Precios no publicados**: Dentalink, DentiDesk, Doctoralia AR, Dentaly (cifra), SOMOSDENTO (cifra), DriCloud, SimplyBook.me (plan pago), Odonthia (requiere verificación directa). Se consigna "No evidenciado" en vez de estimar.
- **Sin acceso a demos privadas**: funciones tras login (roles finos, auditoría, exportación total, cifrado, backups) se marcan "No evidenciado" aunque el marketing las sugiera.
- **Testimonios y métricas de adopción** ("+300 clínicas", "−82% ausencias", "+15.000 clientes") son afirmaciones del proveedor sin auditoría citada; no se tratan como prueba.
- **Odonthia y DentalCore** (mencionados por fuente tercera NacarOS) requieren verificación directa en sus sitios antes de puntuarse o citarse como benchmark de precio.
- **Normativa**: ReNaPDiS/Ley 26.529/Ley 25.326/ARCA se toman de la declaración del proveedor + registro oficial cuando se cita; no sustituyen dictamen legal.
