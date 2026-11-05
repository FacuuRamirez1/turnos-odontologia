# Tasks

> Precondición de Strict TDD: **no cumplida**. `frontend/package.json` no define script `test` ni hay runner (Vitest/Jest/RTL) instalado. El módulo Strict TDD solo aplica con runner disponible; el gate de verificación de este change es `typecheck + lint + build` más los escenarios funcionales de la spec. No se agregan dependencias de test para no ampliar alcance.

## 1. Capa de contratos y cliente HTTP

- [x] 1.1 Crear `frontend/src/api/types.ts` con los contratos espejo (`LoginRequest/Response`, `MeResponse`, `TurnoAgenda`, `Paciente`, `TurnoAcotado`, `EstadoTurno`, envelopes de error) sin `any` y con nulabilidad exacta.
- [x] 1.2 Crear `frontend/src/api/errors.ts` + `client.ts`: `apiFetch<T>` con base URL relativa, `credentials: "include"`, Bearer opcional, `AbortSignal`, parseo JSON seguro, `ApiError` con `status/code/detail` y evento central de 401.
- [x] 1.3 Crear `api/auth.ts`, `api/agenda.ts`, `api/pacientes.ts` y actualizar `api/index.ts` con funciones tipadas para cada endpoint existente.
- [x] 1.4 Verificar contrato: `npm run typecheck` en `frontend/` sin errores.

## 2. Sesión JWT (login, bootstrap, logout)

- [x] 2.1 Crear `auth/AuthProvider.tsx` con estado `loading|anonymous|authenticated`, access token en memoria, bootstrap por `POST /api/auth/refresh`, `/me`, login y logout; listener del evento 401.
- [x] 2.2 Crear `pages/login/LoginPage.tsx` con validación inline, error de 401/429 y estado de envío; sin persistir tokens.
- [x] 2.3 Crear `components/ProtectedRoute.tsx` y cablear rutas `/login` y `/agenda` con React Router 6 (`BrowserRouter`, `Routes`, `Navigate`).
- [x] 2.4 Verificar escenarios 1–3 de la spec (login feliz, credenciales inválidas, recarga con refresh, 401 central) y `typecheck/lint`.

## 3. Shell y diseño visual

- [x] 3.1 Crear `styles/global.css` con tokens nombrados (porcelain/ink/pine/mint/amber/danger), escala tipográfica, foco visible, `prefers-reduced-motion` y layout responsive.
- [x] 3.2 Crear `components/AppShell.tsx` (cabecera con identidad/rol, logout, contenido) y `components/StatusBadge.tsx` (texto + color, estado desconocido).
- [x] 3.3 Actualizar `main.tsx`/`App.tsx` para importar estilos, montar `BrowserRouter` + `AuthProvider` y redirigir la raíz a `/agenda`.
- [x] 3.4 Revisar contra `frontend-design`: sin defaults prohibidos, una sola transición orquestada, copy en voz activa y contraste AA.

## 4. Agenda del día

- [x] 4.1 Crear `pages/agenda/AgendaPage.tsx`: `useSearchParams` para `fecha` y `odontologo_id`, defaults locales, selector fijo para odontólogo y validación UUID para recepción/admin.
- [x] 4.2 Implementar fetch de `GET /api/agenda` con `AbortController`, estados loading/empty/error/retry y render de filas con hora local, estado y canal.
- [x] 4.3 Implementar acciones `Atendido`/`No show` solo para `confirmado`, con guarda temporal para no-show, refetch en paralelo y mensajes 422/403.
- [x] 4.4 Verificar escenarios de agenda (aislamiento por rol, UUID inválido, vacío, error, acciones) y `typecheck/lint`.

## 5. Ficha de paciente e historial

- [x] 5.1 Crear `components/FichaPacientePanel.tsx`: selección de turno, `Promise.all` de paciente + historial, estados loading/error/empty y cierre con Escape/botón.
- [x] 5.2 Renderizar contacto, consentimiento (sí/no + fecha) e historial acotado; no persistir datos ni mostrar campos fuera del contrato.
- [x] 5.3 Integrar selección de fila con la agenda y refrescar ficha/historial tras mutaciones de estado.
- [x] 5.4 Verificar escenarios de ficha (apertura, 403/404, cierre descarta datos) y `typecheck/lint`.

## 6. Gate de calidad y cierre

- [x] 6.1 Ejecutar `cd frontend && npm run typecheck && npm run lint && npm run build`; corregir cualquier error o warning hasta exit code 0.
- [x] 6.2 Verificar ausencia de `any`, de `localStorage/sessionStorage` para tokens/datos de paciente, y de llamadas a endpoints inexistentes (`grep`/revisión).
- [x] 6.3 Ejecutar `openspec validate c-07-frontend-interfaz-agenda --strict` y corregir artefactos si falla.
- [x] 6.4 Archivar el change (`openspec archive c-07-frontend-interfaz-agenda`) y actualizar `CHANGES.md`: insertar `C-07F frontend-interfaz-agenda` en FASE 2.5, marcar completado y registrar el follow-up `GET /api/odontologos`; aclarar que `C-07` sigue siendo `pagos-mp-checkout-webhook`.

## Workflow follow-up

- Guardar en Engram `opsx/c-07-frontend-interfaz-agenda/apply` y `.../archive` con decisiones, brechas y próximos pasos.
- No commitear ni pushear sin pedido explícito (U1).
