# Tasks: `C-11` — `frontend-agenda-backoffice`

> TDD estricto (`U2`: RED → GREEN → TRIANGULATE con 3 escenarios: feliz, error de negocio y borde) y TypeScript estricto sin `any` (`P1`).

## 1. Cliente API Backoffice y Contratos Estrictos (`P1`, `P2`, `P8`)

- [x] 1.1 Agregar `apiBlobFetch` en `frontend/src/api/client.ts` (descarga autenticada con manejo de `401`) y definir interfaces/type guards estrictos en `frontend/src/api/types.ts` para devoluciones, alertas de conciliación, comprobantes, trazabilidad (`TrazabilidadTurno`), disponibilidad y bloqueos. Verificación: `npm --prefix frontend run typecheck`.
- [x] 1.2 Implementar `frontend/src/api/backoffice.ts` (+ re-exports en `frontend/src/api/index.ts`) y tests TDD en `frontend/src/api/backofficeClient.test.ts` cubriendo 3 escenarios (feliz: serialización de devoluciones/aprobar/rechazar/ejecutar, trazabilidad, PDF Blob, disponibilidad/bloqueos y reserva telefónica con `Idempotency-Key`; error: rechazo `403`/`422` propagado con detalle de backend; borde: formato inesperado o caída de red rechazados de forma tipada). Verificación: `npm --prefix frontend run test -- backofficeClient`.

## 2. Bandeja de Devoluciones, Alertas y Trazabilidad Navegable (`/bandeja`, `D2`, `F1`, `P10`, `P15`)

- [x] 2.1 Crear `frontend/src/components/TrazabilidadPanel.tsx` renderizando cadena `turno → pago → devolución → comprobantes` (descarga PDF), `eventos_pago` y `historial` con actor+fecha (`P9`) y marca `"(simulado)"` (`P15`). Verificación: cubierto por tests en `BandejaPage.test.tsx` y `AgendaBackoffice.test.tsx`.
- [x] 2.2 Implementar `BandejaPage` (`frontend/src/pages/bandeja/BandejaPage.tsx`) y tests TDD en `frontend/src/pages/bandeja/BandejaPage.test.tsx` cubriendo 3 escenarios (feliz: filtro por estado, aprobar con `monto_confirmado`, ejecutar en modo simulado mostrando `mp_refund_id` y abrir trazabilidad/ficha/PDF; error de negocio: `422 MONTO_NO_COINCIDE` o rechazo con motivo vacío bloqueado sin mutar estado; borde: alerta de conciliación visible y `503 PROVEEDOR_NO_DISPONIBLE` sin fallback cliente). Verificación: `npm --prefix frontend run test -- BandejaPage`.

## 3. Backoffice en Agenda: Disponibilidad/Bloqueos, Reserva Telefónica y Cancelar/Reprogramar Staff

- [x] 3.1 Crear `frontend/src/components/DisponibilidadBloqueosPanel.tsx` para listar, crear y eliminar lógicamente franjas semanales (`/api/staff/disponibilidad`) y bloqueos (`/api/staff/bloqueos`) con validación de rangos horarios antes de enviar. Verificación: `npm --prefix frontend run test -- AgendaBackoffice`.
- [x] 3.2 Crear `frontend/src/components/ReservaTelefonicaPanel.tsx` habilitado solo para `recepcionista`/`admin` (`Q10`: DNI + email + consentimiento bloqueante `P11`, prohibido para `odontologo` según `03 §2` y `P8`), e integrar en `AgendaPage.tsx` acciones de cancelar (cotización + motivo), reprogramar (`Q3`) y botón de trazabilidad (`B3`). Verificación: tests TDD en `frontend/src/pages/agenda/AgendaBackoffice.test.tsx` cubriendo feliz, error de negocio (`consentimiento=false` / `409`) y borde (aislamiento de rol `odontologo` vs `recepcionista`).

## 4. Navegación Staff, Prohibiciones por Rol y Verificación Integrada

- [x] 4.1 Actualizar `frontend/src/components/AppShell.tsx` (enlaces `/agenda` y `/bandeja`, alcance del rol sin accesos a usuarios/roles, `PAGO_MODO` ni ARCA) y `frontend/src/App.tsx` (ruta protegida `/bandeja`). Verificación: `npm --prefix frontend run test -- AgendaBackoffice BandejaPage`.
- [x] 4.2 Ejecutar validación integral tras finalizar implementación (`python -m pytest backend/app/tests -q`, `npm --prefix frontend run typecheck`, `npm --prefix frontend run lint`, `npm --prefix frontend run test`, `npm --prefix frontend run build`, `openspec validate --all --json`) y registrar evidencia en `docs/skills-mcp/evidencias/mcp-c11-apply.md`. Verificación: todos los comandos terminan con código de salida `0`.

## Workflow follow-up

- Al verificar todo en verde, sincronizar `openspec/specs/frontend-agenda-backoffice/spec.md`, archivar `c-11-frontend-agenda-backoffice` y marcar `[x]` en `CHANGES.md`.
