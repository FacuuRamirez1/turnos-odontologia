# Change: C-11 — `frontend-agenda-backoffice`

## Why

Con `C-08` (bandeja de devoluciones, comprobantes PDF, alertas y trazabilidad) y `C-10` (cara pública) ya archivados, el equipo de clínica todavía carece de interfaz para operar el backoffice completo: en `/agenda` solo puede consultar turnos y marcar `atendido`/`no_show` (`C-07F`), mientras que `/bandeja` sigue siendo un placeholder, no existe UI para ABM de disponibilidad/bloqueos (`C-04`), cancelación/reprogramación con motivo e historial (`B3`), reserva telefónica (`Q10`) ni revisión/ejecución de devoluciones con recibos PDF (`D2`, `F1`).

## What Changes

- **Bandeja de devoluciones y conciliación (`/bandeja`)**: filtrar devoluciones por estado, visualizar alertas de conciliación (`/api/devoluciones/alertas`), aprobar manualmente (`monto_confirmado`, respetando `Q4`), rechazar con motivo obligatorio y ejecutar vía proveedor simulado con banner `"(simulado)"` (`P10`/`P15`).
- **Trazabilidad navegable (`turno ↔ pago ↔ devolución ↔ comprobante`)**: panel compartible que consume `GET /api/turnos/{id}/trazabilidad` y `GET /api/comprobantes/{id}/pdf` mostrando eventos append-only e historial con actor y fecha (`B3`, `P9`).
- **Backoffice operativo en `/agenda`**:
  - Cancelación de turnos `confirmado` con pre-cotización (`100 % / 60 % / 0 %`) y motivo; reprogramación con aviso `Q3` de conservación de seña e `Idempotency-Key`.
  - Gestión ABM de franjas semanales (`/api/staff/disponibilidad`) y bloqueos (`/api/staff/bloqueos`) scopeada al profesional efectivo.
  - Reserva telefónica (`/api/reservas/telefonica`, `Q10`) habilitada exclusivamente para `recepcionista` y `admin` (bloqueada/oculta para `odontologo` según matriz `03 §2` y `P8`), exigiendo DNI + email + `consentimiento_datos = true` (`P11`).
- **Navegación staff y refuerzo RBAC UI (`P8`)**: enlaces `/agenda` y `/bandeja` en `AppShell`, ruta protegida `/bandeja`, y aviso claro del scope/prohibiciones del rol (`recepcionista` sin gestión de usuarios/roles, configuración de pagos/`PAGO_MODO`, ni ARCA).

## Capabilities

### New Capabilities
- `frontend-agenda-backoffice`: Interfaz React + TypeScript estricto para agenda operativa staff, disponibilidad/bloqueos, reserva telefónica `Q10`, bandeja de devoluciones simuladas (`P15`), comprobantes PDF y trazabilidad auditable (`P8`, `P9`).

### Modified Capabilities
- *(Ninguna — extiende la SPA protegida de `C-07F` sin romper contratos existentes de `/agenda` y `/login`.)*

## Impact

- **Backend**: cero cambios de schema ni nuevas rutas (`P3`, `P12`); consume exclusivamente endpoints archivados de `C-03`, `C-04`, `C-05`, `C-06`, `C-07`, `C-08`.
- **Frontend**: `frontend/src/api/{client,backoffice,types,index}.ts`, `frontend/src/components/{AppShell,TrazabilidadPanel,DisponibilidadBloqueosPanel,ReservaTelefonicaPanel}.tsx`, `frontend/src/pages/{agenda/AgendaPage,bandeja/BandejaPage}.tsx`, `frontend/src/App.tsx`, más suite TDD en Vitest/RTL.
- **Dependencias**: `C-05`, `C-08` (ambos archivados).
