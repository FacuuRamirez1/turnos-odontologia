# Proposal

## Why

Los endpoints de autenticación JWT (C-03), agenda del día (C-05) y ficha de paciente (C-06) ya existen y están cubiertos por tests, pero `frontend/src` sigue siendo el scaffolding de C-01: no hay forma de iniciar sesión, consultar la agenda ni abrir una ficha desde el navegador. Sin una interfaz acotada, el sistema no se puede operar ni demostrar end-to-end aunque el backend esté completo. Este change construye la primera rebanada vertical de operador (login → agenda → ficha) antes de invertir en pagos (C-07) o en el backoffice completo (C-11).

## What Changes

- **Sesión de operador**: pantalla de login contra `POST /api/auth/login`, bootstrap de sesión contra `POST /api/auth/refresh` (cookie HttpOnly), identidad contra `GET /api/auth/me` y logout contra `POST /api/auth/logout`. El access token vive solo en memoria; nunca en `localStorage`/`sessionStorage`.
- **Capa API tipada**: contratos TypeScript que reflejan exactamente los schemas Pydantic existentes (`LoginResponse`, `MeResponse`, `TurnoAgendaOut`, `PacienteRead`, `TurnoAcotado`), cliente `fetch` único con `credentials: "include"`, inyección de Bearer, `AbortSignal`, y parseo del envelope de error (`{error, detail, path}`, `{code, detail}` y validación FastAPI).
- **Agenda del día**: selección de fecha + profesional, consulta `GET /api/agenda?fecha&odontologo_id`, estados de carga/vacío/error, filas con horario local, estado y canal. Para rol `odontologo` el `odontologo_id` se toma de `/me` y no es editable; para `recepcionista`/`admin` se solicita el UUID del profesional (ver brecha de contrato abajo).
- **Acciones staff**: botones `Atendido` y `No show` solo para turnos `confirmado`, contra `POST /api/agenda/{id}/atendido` y `POST /api/agenda/{id}/no-show`, con refetch de agenda e historial y mensaje explícito ante 422/403.
- **Ficha de paciente**: al seleccionar un turno se abren en paralelo `GET /api/pacientes/{id}` y `GET /api/pacientes/{id}/turnos`; se muestran contacto, consentimiento e historial acotado, sin persistir datos de paciente en el navegador.
- **Sistema visual y accesibilidad**: layout de "bitácora clínica" (riel horario, tipografía de alto contraste, estados con texto+color), responsive, foco visible, labels explícitos, `aria-live` para errores y objetivos táctiles de 44 px.
- **Sin cambios de backend**: no se agregan endpoints, tablas, migraciones ni dependencias npm. Se consumen los contratos existentes y se documentan las brechas (directorio de odontólogos, CORS) sin inventar alcance (P14).

## Capabilities

### New Capabilities

- `frontend-interfaz-agenda`: comportamiento verificable de la SPA de operador — sesión JWT en memoria con refresh, consulta de agenda aislada por profesional, apertura de ficha mínima, acciones de estado permitidas y garantías de TypeScript estricto/accesibilidad.

### Modified Capabilities

- Ninguna. Se consumen sin cambiar los REQUIREMENTS de `auth-jwt-rbac` (C-03), `reserva-turnos-estados` (C-05) y `ficha-paciente-consentimiento` (C-06); el backend sigue siendo la autoridad de RBAC y aislamiento (P8).

## Impact

- **Código**: `frontend/src/api/*`, `frontend/src/auth/*`, `frontend/src/components/*`, `frontend/src/pages/agenda/*`, `frontend/src/pages/login/*`, `frontend/src/styles/*`, `frontend/src/App.tsx`, `frontend/src/main.tsx`, `frontend/src/vite-env.d.ts`; ajuste opcional de `frontend/vite.config.ts`/`.env.example` para dejar explícito el proxy same-origin.
- **Backend**: cero cambios. La UI no relaja ninguna regla: RBAC, aislamiento `odontologo_id`, gate de consentimiento y rate-limit siguen enforced en FastAPI (P8, P12).
- **Dependencias**: ninguna nueva; `react-router-dom` 6.28 ya está declarado.
- **Brecha de contrato documentada**: no existe `GET /api/odontologos` para poblar un selector; recepción/admin deben ingresar el UUID del profesional. Se resuelve en un change posterior, no aquí.
- **Calidad**: gate `cd frontend && npm run typecheck && npm run lint && npm run build` sin errores ni warnings. No hay runner de tests de frontend instalado, por lo que el modo Strict TDD no aplica (se documenta en design).
- **Skills/MCP**: se aplican las skills propias `frontend-design`, `vercel-react-best-practices`, `auth-implementation-patterns` y el flujo `openspec-*`; se usan los MCP `context7` (documentación React Router v6) y `engram` (memoria de decisiones). Detalle explícito en `design.md`.
