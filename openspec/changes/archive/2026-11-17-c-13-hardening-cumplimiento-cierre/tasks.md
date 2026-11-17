# Tasks

## 1. Cifrado en tránsito y en reposo

- [x] 1.1 Añadir extensión pgcrypto al servicio db de Compose y campo de cifrado por env var; verificar que pgcrypto está disponible en el contenedor db
- [x] 1.2 Crear migración Alembic versionada que declare campos sensibles cifrados (DNI, email, teléfono) con pgcrypto; verificar `alembic upgrade head` aplica sin errores y cero create_all en runtime
- [x] 1.3 Documentar TLS en tránsito vía reverse proxy/Compose (excepción controlada en dev local); verificar que el documento de despliegue menciona HTTPS obligatorio fuera de dev

## 2. Backups periódicos de PostgreSQL con prueba de restore

- [x] 2.1 Crear script de backup periódico del volumen pgdata (pg_dump); verificar que genera un archivo de backup sin errores
- [x] 2.2 Crear procedimiento documentado de restore y prueba automatizada; verificar que restaurar sobre una base vacía recupera tablas y datos y el sistema arranca

## 3. Job de retención RN-RETENCION con política publicada

- [x] 3.1 Publicar política de retención (plazos de conservación de turnos, mails, eventos de pago e historial); verificar que el documento existe y está versionado
- [x] 3.2 Implementar job periódico (worker Redis/scheduler) que aplique la política y deje rastro append-only; verificar que el job ejecuta y registra registros conservados/eliminados/anonimizados

## 4. Rate-limit auditado en rutas públicas

- [x] 4.1 Identificar las 6 rutas públicas de 03 §3 y aplicar middleware de rate-limit; verificar que cada ruta pública tiene rate-limit activo
- [x] 4.2 Registrar cada intento (éxito/rechazo) en auditoría; verificar que el rastro de auditoría contiene los intentos de rate-limit

## 5. Verificación de flags v2 apagados (guard P15)

- [x] 5.1 Implementar guard de arranque que falle si PAGO_MODO=mercadopago en contexto MVP; verificar que el servicio no arranca con PAGO_MODO=mercadopago en MVP
- [x] 5.2 Verificar que el endpoint sandbox POST /pagos/{pago_id}/simular solo se registra cuando PAGO_MODO=simulado; verificar que no existe fuera de simulado
- [x] 5.3 Verificar WHATSAPP_ENABLED=false, ARCA_ENABLED=false, PAGO_MODO=simulado en arranque; verificar que los flags están apagados en el build v1

## 6. Seed final completo (04 §5)

- [x] 6.1 Cargar seed final idempotente con 10 turnos en todos los estados; verificar que existen 10 turnos cubriendo creados, confirmados, atendidos, cancelados, reprogramados, no_show y devueltos
- [x] 6.2 Cargar 1 pago aprobado + 1 devolución 60 % ejecutada con comprobante; verificar que el pago y la devolución existen con trazabilidad
- [x] 6.3 Cargar datos demo de precio/trial públicos; verificar que precio y trial públicos están disponibles desde día uno

## 7. Verificación E2E de los 5 criterios de éxito v1 + limitaciones Q11/Q12

- [x] 7.1 Test E2E: reserva→seña simulada→mail sin intervención del consultorio; verificar que el mail de confirmación se envía
- [x] 7.2 Test E2E: no doble-reserva concurrente (constraint de dominio); verificar que solo una petición confirma el mismo slot
- [x] 7.3 Test E2E: rastro auditable total (actor+fecha; eventos de pago append-only); verificar que existe rastro de transiciones y pagos
- [x] 7.4 Test E2E: confirmar/cancelar desde mail actualiza la agenda; verificar que el turno cambia de estado desde el mail
- [x] 7.5 Test E2E: recorte sostenido (nada de v2 construido en v1); verificar que no hay WhatsApp, ARCA, sobre-turnos, lista_espera con escrituras ni MP real
- [x] 7.6 Documentar Q11 (sin validación usuarios reales) y Q12 (sin dictamen legal Ley 25.326/26.529) como limitaciones conocidas; verificar que aparecen en la documentación de cierre

## 8. Tests de hardening (restore, retención, flags v2 off, checklist criterios de éxito)

- [x] 8.1 Test de restore backup; verificar que el backup se restaura y el sistema arranca
- [x] 8.2 Test de retención; verificar que el job aplica la política publicada
- [x] 8.3 Test de flags v2 off; verificar WHATSAPP_ENABLED=false, ARCA_ENABLED=false, PAGO_MODO=simulado
- [x] 8.4 Test checklist criterios de éxito v1; verificar que los 5 criterios pasan
