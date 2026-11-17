# Proposal

## Why

La v1 ya registra turnos, pagos, devoluciones y mails, pero el consultorio no puede consultar ni sacar esos datos: no hay reportes de asistencia/ausentismo ni exportación de turnos y caja (épica F2–F3, RN-AUDIT). La exportación auditable es el diferencial barato de D3 y bloquea a C-13 (cierre v1).

## What Changes

- Endpoints staff de reporte de **asistencia** (conteos por estado de turno y período) y de **caja** (pagos aprobados y devoluciones ejecutadas por período), con aislamiento por odontólogo (P8).
- Exportación **CSV y PDF** de turnos y de caja con filtros por odontólogo y período; exportación de **auditoría** (`turno_historial` + `evento_pago`, append-only) en CSV.
- Marca "(simulado)" en reportes de caja y exportaciones cuando `PAGO_MODO=simulado` (D14, P15).
- Reuso de las métricas de entrega de mail de C-09 como bloque del reporte (sin métrica propia de ausentismo: D12/Q8 excluida).
- UI mínima en `frontend/src/pages/reportes`: filtros, vista de conteos y descarga.
- Sin migraciones: solo lectura sobre tablas existentes.

## Capabilities

### New Capabilities
- `reportes-exportaciones`: reportes de asistencia y caja, exportaciones CSV/PDF de turnos, caja y auditoría, con RBAC y aislamiento por profesional.

### Modified Capabilities
<!-- Ninguna: no cambian requisitos de capacidades existentes. -->

## Impact

- Backend: nuevo `app/api/reportes.py` (router `/api/reportes`), `app/domain/reportes/` (consultas, CSV, PDF), registro en `main.py`. Se reutiliza `domain/notificaciones/metricas.py`.
- Frontend: `pages/reportes/ReportesPage.tsx`, módulo API tipado nuevo (sin `any`, P1).
- Rutas protegidas con `require_role`; **no** se agregan rutas públicas (P12). Sin dependencias nuevas (PDF con el mismo enfoque mínimo de `comprobantes/pdf.py`).
- Datos de pacientes: exportaciones sin datos clínicos; solo DNI ficticios en seeds (P11).
