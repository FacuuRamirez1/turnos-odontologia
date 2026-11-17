# hardening-cumplimiento

## Purpose

Define los requisitos de comportamiento del endurecimiento v1 y la verificación de cumplimiento mínimo (cifrado, backups, retención, rate-limit, flags v2 apagados, seed final y criterios de éxito) que C-13 debe cumplir antes de cerrar el roadmap.

## Requirements

### Requirement: Cifrado en tránsito y en reposo

El sistema SHALL declarar cifrado de datos sensibles en reposo (pgcrypto sobre campos sensibles) y exigir TLS en tránsito (reverse proxy o Compose con HTTPS en entorno de despliegue); en dev local se documenta la excepción controlada.

#### Scenario: Datos sensibles cifrados en reposo

- **WHEN** se consulta un campo declarado sensible de un usuario/paciente
- **THEN** el valor almacenado en PostgreSQL está cifrado con pgcrypto y solo se descifra en la capa de aplicación autorizada

#### Scenario: TLS en tránsito requerido

- **WHEN** el despliegue no es dev local
- **THEN** todas las rutas expuestas por el reverse proxy/Compose usan HTTPS y rechazan HTTP plano

### Requirement: Backups periódicos de PostgreSQL con prueba de restore

El sistema SHALL ejecutar backups periódicos del volumen pgdata y disponer de un procedimiento documentado y testeado de restore que verifique integridad del backup.

#### Scenario: Backup periódico ejecutado

- **WHEN** pasa la ventana de backup configurada
- **THEN** se genera un archivo de backup del volumen pgdata sin errores

#### Scenario: Prueba de restore exitosa

- **WHEN** se restaura un backup sobre una base vacía
- **THEN** las tablas y datos se recuperan y el sistema arranca sobre el backup restaurado

### Requirement: Job de retención RN-RETENCION con política publicada

El sistema SHALL ejecutar un job periódico de retención que aplique la política publicada (plazos de conservación de turnos, mails, eventos de pago e historial) y elimine o anonimice según la política.

#### Scenario: Job de retención ejecuta según política

- **WHEN** se dispara el job de retención
- **THEN** aplica la política publicada y deja rastro de qué registros se conservaron/eliminaron/anonimizaron

### Requirement: Rate-limit auditado en rutas públicas

El sistema SHALL aplicar rate-limit en las 6 rutas públicas definidas en 03 §3 y dejar rastro de cada intento (exitoso o rechazado).

#### Scenario: Rate-limit rechaza exceso en ruta pública

- **WHEN** un cliente excede el límite de peticiones en una ruta pública
- **THEN** el sistema responde con error de rate-limit y registra el intento en el rastro de auditoría

#### Scenario: Ruta pública dentro del límite

- **WHEN** un cliente está dentro del límite de una ruta pública
- **THEN** el sistema procesa la petición normalmente y registra el intento

### Requirement: Verificación de flags v2 apagados

El sistema SHALL verificar que WHATSAPP_ENABLED=false, ARCA_ENABLED=false, PAGO_MODO no sea mercadopago en MVP, el endpoint sandbox /pagos/{pago_id}/simular no exista fuera de PAGO_MODO=simulado, lista_espera sin escrituras y sin sobre-turnos (RN-SOBRETURNO).

#### Scenario: Flags v2 apagados en arranque

- **WHEN** el sistema arranca en modo MVP/dev
- **THEN** WHATSAPP_ENABLED=false, ARCA_ENABLED=false y PAGO_MODO=simulado

#### Scenario: Endpoint sandbox inexistente fuera de simulado

- **WHEN** PAGO_MODO no es simulado
- **THEN** el endpoint POST /pagos/{pago_id}/simular no está registrado

#### Scenario: Sin sobre-turnos (RN-SOBRETURNO)

- **WHEN** dos peticiones concurrentes intentan reservar el mismo slot
- **THEN** solo una se confirma y la otra recibe error de no-disponibilidad (constraint de dominio)

#### Scenario: Lista de espera sin escrituras

- **WHEN** se opera en v1
- **THEN** no hay escrituras en tabla de lista de espera (capacidad modelada, apagada)

### Requirement: Seed final completo

El sistema SHALL cargar un seed final con 10 turnos en todos los estados, 1 pago aprobado + 1 devolución 60 % ejecutada, y datos demo de precio/trial públicos.

#### Scenario: Seed final con todos los estados de turno

- **WHEN** se aplica el seed final
- **THEN** existen 10 turnos cubriendo creados, confirmados, atendidos, cancelados, reprogramados, no_show y devueltos

#### Scenario: Pago aprobado con devolución 60 %

- **WHEN** se aplica el seed final
- **THEN** existe 1 pago aprobado y 1 devolución del 60 % ejecutada con comprobante

### Requirement: Verificación E2E de los 5 criterios de éxito v1

El sistema SHALL verificar E2E: reserva→seña simulada→mail sin intervención; no doble-reserva concurrente; rastro auditable total; confirmar/cancelar desde mail; recorte sostenido (nada de v2 construido en v1).

#### Scenario: Flujo reserva-seña-mail sin intervención

- **WHEN** un paciente reserva y paga seña simulada
- **THEN** recibe confirmación por mail sin intervención del consultorio

#### Scenario: Recorte sostenido (nada de v2 en v1)

- **WHEN** se inspecciona el build v1
- **THEN** no hay implementación de WhatsApp, ARCA, sobre-turnos, lista de espera con escrituras ni MercadoPago real

### Requirement: Riesgos Q11/Q12 documentados como limitaciones conocidas

El sistema SHALL documentar Q11 (sin validación con usuarios reales) y Q12 (sin dictamen legal Ley 25.326/26.529) como limitaciones conocidas.

#### Scenario: Limitaciones Q11/Q12 documentadas

- **WHEN** se revisa la documentación de cierre v1
- **THEN** Q11 y Q12 aparecen como limitaciones conocidas sin válidad jurídica ni validación de usuarios reales
