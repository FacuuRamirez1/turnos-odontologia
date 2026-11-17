# Design

## Context

C-13 es el último change del roadmap (FASE 6 — Cierre, gobernanza ALTO). Todas las capacidades de dominio (turnos, pagos, mails, reportes, agenda) ya están implementadas en cambios previos (C-01 → C-12 archivados). No hay nuevo modelo de datos de dominio ni cambio de contrato de API. La propuesta (proposal.md) detalla el "qué"; este documento detalla el "cómo" del endurecimiento y verificación. Ver CHANGES.md §C-13 y knowledge-base 01 §4–5, 02 §5, 08 §7, 10 §4.

## Goals / Non-Goals

**Goals:**
- Endurecer v1 con cumplimiento mínimo explícito: cifrado en tránsito/en reposo, backups con restore, retención RN-RETENCION, rate-limit auditado en rutas públicas.
- Verificar recorte v2: flags apagados, endpoint sandbox ausente fuera de simulado, lista_espera sin escrituras, sin sobre-turnos.
- Cargar seed final completo y verificar E2E los 5 criterios de éxito v1.
- Documentar Q11/Q12 como limitaciones conocidas.
- Dejar tests de hardening (restore, retención, flags off, checklist criterios de éxito).

**Non-Goals:**
- No se añade lógica de dominio nueva ni se modifican contratos de API existentes.
- No se construye MercadoPago real, WhatsApp, ARCA, sobre-turnos ni lista de espera con escrituras (v2, fuera de alcance v1).
- No se emite dictamen legal sobre Ley 25.326/26.529 (Q12 queda como limitación documentada).

## Decisions

### Capa de cifrado: pgcrypto para campos sensibles en reposo
**Decisión:** Usar pgcrypto (ya disponible en el servicio db de Compose con extensión pgcrypto) para cifrar campos sensibles (p. ej. DNI, email, teléfono) en reposo; la clave de cifrado se provee por env var, nunca hardcodeada (P5).
**Alternativa considerada:** Cifrado a nivel de aplicación con librería Python. Descartada porque pgcrypto ya está en el stack y deja el cifrado declarativo cerca del dato.
**Razón:** Menor superficie de código nuevo y alineado con 08 §7 (cifrado declarado de sensibles en reposo).

### TLS en tránsito
**Decisión:** Documentar que el reverse proxy/Compose expone HTTPS en despliegue; en dev local (Compose sin proxy) se acepta la excepción controlada y documentada.
**Alternativa considerada:** Terminar TLS en FastAPI. Descartada porque el stack usa reverse proxy externo y el cambio sería de infra, no de app.

### Backups PostgreSQL
**Decisión:** Script de backup periódico del volumen pgdata (pg_dump) ejecutado desde un contenedor de servicio o cron del host, con prueba de restore automatizada en tests.
**Alternativa considerada:** Backups lógicos vía SQL. Descartada porque pg_dump del volumen es más simple y cubre el esquema completo.

### Job de retención RN-RETENCION
**Decisión:** Job periódico (worker Redis/scheduler) que aplique la política publicada y deje rastro append-only de registros conservados/eliminados/anonimizados.
**Alternativa considerada:** Borrado inmediato sin rastro. Descartado por P9 (append-only, historial de estados, auditoría).

### Rate-limit en rutas públicas
**Decisión:** Middleware de rate-limit sobre las 6 rutas públicas de 03 §3 con registro de cada intento (éxito/rechazo) en auditoría.
**Alternativa considerada:** Rate-limit solo por IP sin rastro. Descartado porque C-13 exige auditoría.

### Guard de arranque P15
**Decisión:** Al arrancar, si se detecta PAGO_MODO=mercadopago en contexto MVP, el servicio falla en arranque; el endpoint sandbox solo se registra cuando PAGO_MODO=simulado.
**Razón:** P15 prohíbe modo simulado en producción y el sandbox endpoint no debe existir fuera de simulado.

## Risks / Trade-offs

- [Riesgo] Cifrado de campos sensibles requiere migración de datos existentes y rotación de clave. → Mitigación: se aplica en seed final y migración versionada (P3); clave por env var.
- [Riesgo] Backups y restore dependen del entorno de despliegue (volumen pgdata). → Mitigación: prueba de restore en tests de integración contra Compose.
- [Riesgo] Q11/Q12 son limitaciones conocidas, no resolubles en v1 académico. → Mitigación: documentadas explícitamente; no bloquean el cierre.
- [Trade-off] No se implementa RLS a nivel de DB (se evaluó en C-02 y se re-evalúa aquí). → El aislamiento sigue siendo app-enforced via repositorio + require_role (P8).

## Migration Plan

1. Aplicar migración Alembic versionada para campos sensibles cifrados (si aplica) — cero create_all en runtime (P3).
2. Desplegar script de backup + prueba de restore en CI/entorno de despliegue.
3. Activar job de retención con política publicada.
4. Cargar seed final idempotente (ON CONFLICT DO NOTHING por email/DNI).
5. Ejecutar tests de hardening (restore, retención, flags off, checklist criterios de éxito).
6. Rollback: revertir migración y desactivar job de retención; los tests de flags v2 off no tienen efecto de rollback (son de verificación).

## Open Questions

- Ninguna abierta que cambie specs, diseño o tareas. Q11/Q12 quedan documentadas como limitaciones conocidas (ver 10 §4).
