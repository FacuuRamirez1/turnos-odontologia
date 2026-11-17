# Design: `C-11` — `frontend-agenda-backoffice`

## Context

`C-11` completa la cara interna del consultorio conectando la SPA autenticada (`C-07F`) con los endpoints archivados de `C-04` (`/api/staff/disponibilidad`, `/api/staff/bloqueos`), `C-05` (`/api/reservas/telefonica`, `cotizar-cancelacion`, `cancelar`, `reprogramar`), `C-06` (`/api/pacientes/{id}`) y `C-08` (`/api/devoluciones*`, `/api/comprobantes*`, `/api/turnos/{id}/trazabilidad`).

Actualmente:
- `frontend/src/pages/bandeja/BandejaPage.tsx` es un placeholder de 3 líneas sin ruta en `App.tsx`.
- `frontend/src/components/AppShell.tsx` no tiene navegación hacia `/bandeja` ni explica límites de rol.
- `frontend/src/pages/agenda/AgendaPage.tsx` solo lista turnos y ejecuta `atendido` / `no_show`, sin cancelar/reprogramar con motivo, sin trazabilidad visible, sin ABM de disponibilidad/bloqueos ni reserva telefónica `Q10`.

## Goals / Non-Goals

### Goals
- Construir un cliente HTTP autenticado tipado en `frontend/src/api/backoffice.ts` sin `any` (`P1`) reutilizando `apiFetch` (`auth: true`) y un helper `apiBlobFetch` en `client.ts` para descargar recibos PDF con `Bearer` token y manejo centralizado de `401`.
- Implementar `/bandeja` (`BandejaPage`) con flujo completo `pendiente → aprobada/rechazada → ejecutada`, confirmación explícita de `monto_confirmado` (`Q4`), alertas de conciliación y banner `"(simulado)"` (`P15`).
- Construir `TrazabilidadPanel` reutilizable desde `/bandeja` y `/agenda`, exhibiendo actor + fecha (`P9`), comprobantes e historial `B3`.
- Enriquecer `/agenda` (`AgendaPage`) con `DisponibilidadBloqueosPanel`, `ReservaTelefonicaPanel` (solo `recepcionista` / `admin`, `P8`), y acciones inline para cancelar (cotización + motivo) y reprogramar (slot disponible + aviso `Q3`).
- Garantizar cumplimiento UI + tests de las prohibiciones de recepcionista/odontólogo (`03 §2`, `P8`).

### Non-Goals
- **No** modificar ni crear nuevos endpoints de backend (todo `C-04`/`C-05`/`C-08` ya está en `main`).
- **No** implementar reportes/exportaciones ni caja (`C-12`).
- **No** habilitar edición de usuarios/roles, configuración de pagos/`PAGO_MODO` ni ARCA (`P8`, `P13`).
- **No** calcular ni auto-aprobar devoluciones en frontend (`Q4`).

## Decisions

### D1. Helper compartido `apiBlobFetch` para descarga PDF autenticada
- **Decisión**: Agregar `apiBlobFetch(path, signal?)` en `frontend/src/api/client.ts` compartiendo resolución de `API_BASE_URL`, envío de `Authorization: Bearer <token>` (`credentials: "include"`) y disparo de `AUTH_UNAUTHORIZED_EVENT` ante `401`.
- **Por qué**: El endpoint `GET /api/comprobantes/{id}/pdf` responde bytes `application/pdf` (C-08 grupo 5), por lo que un `<a href>` directo no enviaría el access token en memoria (`C-07F`). Un helper en `client.ts` evita duplicar lógica de auth/errores.

### D2. Separación de paneles en `/agenda` y navegación protegida en `AppShell`
- **Decisión**: Mantener `AgendaPage` legible delegando formularios complejos a subcomponentes PascalCase dedicados: `DisponibilidadBloqueosPanel`, `ReservaTelefonicaPanel` y `TrazabilidadPanel`.
- **Control RBAC (`P8`)**: `ReservaTelefonicaPanel` solo se habilita para `rol === "recepcionista" || rol === "admin"`; para `odontologo` el botón/sección queda oculto e informa claramente la restricción, mientras el backend igualmente responde `403` si alguien intentara invocarlo. En `AppShell`, agregar enlaces `<NavLink>` a `/agenda` y `/bandeja` (`react-router-dom@6.28.0`) y omitir cualquier entrada a usuarios/roles, config MP/`PAGO_MODO` o ARCA.

### D3. Flujo de devoluciones y confirmación explícita de monto (`Q4`, `P10`, `P15`)
- **Decisión**: En `BandejaPage`, aprobar una devolución `pendiente` abre un paso de confirmación donde el operador ingresa/verifica `monto_confirmado` antes de enviar `POST /api/devoluciones/{id}/aprobar`. Rechazar exige `motivo` no vacío. Ejecutar invoca `POST /api/devoluciones/{id}/ejecutar` sin transiciones locales; ante `503 PROVEEDOR_NO_DISPONIBLE` muestra mensaje claro sin fallback (`P15`).

### D4. Cancelación y reprogramación staff con cotización previa y aviso `Q3`
- **Decisión**: Al cancelar un turno `confirmado` en `AgendaPage`, la UI primero consulta `GET /api/reservas/{id}/cotizar-cancelacion` (usando Bearer staff) para mostrar `porcentaje` aplicable (`100 % / 60 % / 0 %`) y capturar `motivo` opcional antes de `POST /api/reservas/{id}/cancelar`. Al reprogramar, muestra aviso explícito `Q3` (*"En esta versión se conserva la seña original sin cargos ni recálculos adicionales"*), permite seleccionar fecha/hora vía `GET /api/disponibilidad` y envía `POST /api/reservas/{id}/reprogramar` con `Idempotency-Key` único.

## Risks / Trade-offs

- **Desfase de zona horaria al editar/crear disponibilidad y bloqueos**: `DisponibilidadCreate` espera `hora_inicio` / `hora_fin` (`HH:MM`) y `BloqueoCreate` espera `desde` / `hasta` ISO-8601. *Mitigación*: normalizar inputs HTML `date`/`time`/`datetime-local` con zona local explícita al armar payloads ISO.
- **UUID manual de profesional para recepcionista/admin**: Dado que `C-07F` prohíbe un endpoint listado de profesionales en staff (`openspec/specs/frontend-interfaz-agenda/spec.md`), `AgendaPage` sigue tomando `effectiveOdontologoId` para `DisponibilidadBloqueosPanel` y `ReservaTelefonicaPanel` (permitiendo además editar el `odontologo_id` en el formulario telefónico si hiciera falta, validado con `isUuid`).

## Open Questions

- **`Q3` (diferencia de monto al reprogramar)**: Se delega en el backend (`reservas.py` hereda `pago_id`) y se exhibe aviso informativo en UI sin recalcular importes.
- **`Q4` (auto-aprobación devolución 60 %)**: Toda devolución queda `pendiente` y exige aprobación manual con `monto_confirmado`.
- **`Q10` (reserva telefónica por recepcionista)**: Cubierta con `POST /api/reservas/telefonica` solicitando profesional, horario futuro, DNI, nombre, apellido, email y `consentimiento_datos = true` (`P11`).
