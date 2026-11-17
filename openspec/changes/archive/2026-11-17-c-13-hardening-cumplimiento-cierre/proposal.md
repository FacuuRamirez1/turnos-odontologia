# Proposal

## Why

El roadmap v1 llega a su último change sin un endurecimiento explícito de cumplimiento y seguridad ni una verificación de que nada de v2 se construyó por error. C-13 cierra v1 con: TLS en tránsito + cifrado declarado de sensibles en reposo, backups periódicos de PostgreSQL con prueba de restore, job de retención RN-RETENCION con política publicada, rate-limit auditado en las 6 rutas públicas, verificación de flags v2 apagados (P13/P15), seed final completo y verificación E2E de los 5 criterios de éxito v1, con los riesgos Q11/Q12 documentados como limitaciones conocidas.

## What Changes

- `proposal.md`, `design.md`, `tasks.md` + un spec de capability `hardening-cumplimiento`.
- Backend: chequeo de arranque que falle si `PAGO_MODO=mercadopago` en MVP (guard P15), middleware de rate-limit auditado en rutas públicas, job de retención RN-RETENCION, política de retención publicada, cifrado declarado de sensibles en reposo (pgcrypto) + nota de TLS en tránsito via reverse proxy/Compose.
- Infra: script de backup periódico de PostgreSQL + prueba de restore documentada y testeada.
- Seed final completo (04 §5): 10 turnos en todos los estados, 1 pago aprobado + 1 devolución 60 % ejecutada, datos demo precio/trial públicos.
- Tests: restore backup, retención, flags v2 off, checklist criterios de éxito v1.
- Documentación: riesgos Q11/Q12 como limitaciones conocidas; checklist de verificación de recorte v2 apagado.
- No se crea el endpoint sandbox `/pagos/{pago_id}/simular` fuera de `PAGO_MODO=simulado`; `lista_espera` sin escrituras; sin sobre-turnos (RN-SOBRETURNO).

## Capabilities

### New Capabilities

- `hardening-cumplimiento`: endurecimiento v1 + cumplimiento mínimo explícito + verificación de recorte (TLS/cifrado, backups+restore, retención RN-RETENCION, rate-limit público, flags v2 apagados, seed final, E2E criterios de éxito, limitaciones Q11/Q12, tests asociados).

### Modified Capabilities

- (none) — C-13 no modifica requisitos de ninguna capacidad existente; solo verifica, endurece y documenta.

## Impact

- Backend (`backend/app/`): middleware de rate-limit, job de retención, guard de arranque P15, tests de hardening.
- Infra (`docker-compose.yml`, scripts backup/restore): volumen pgdata, backup periódico.
- Seed (migración/seed final): 10 turnos, 1 pago aprobado + devolución 60 %, precios/trial públicos.
- Documentación (knowledge-base opcional si se añade): política de retención, limitaciones Q11/Q12.
- No afecta contratos de API existentes (no es BREAKING).
