# Evidencia MCP Context7 + Skill `validador-escenarios-turnos` — apply de `C-10` (`frontend-reserva-publica`)

- **Fecha**: 2026-11-17
- **Change**: `C-10` (`frontend-reserva-publica`) — fase `/opsx:apply` y verificación pre-archivo
- **Configuración MCP**: `opencode.json` (`type: "local"`, `npx -y @upstash/context7-mcp`, sin secretos, `P5`)
- **Servidor conectado**: `Context7 Documentation MCP Server v4.7.2` (protocolo `2024-11-05`, transporte `stdio`)
- **Contrastado contra versiones reales del proyecto** ([frontend/package.json](../../../frontend/package.json)): `react@18.3.1`, `react-router-dom@6.28.0`, `@testing-library/react@16.3.2`, `vitest@2.1.8`, `typescript@5.6.3`.

---

## 1. Consultas reales a Context7 MCP durante `/opsx:apply`

### Consulta 1 — `react-router-dom`: `MemoryRouter`, `Routes`, `Route` y `useSearchParams`

- **Solicitudes ejecutadas**:
  - `resolve-library-id`: `{ "libraryName": "react-router-dom", "query": "MemoryRouter Routes Route useSearchParams v6.28" }` → devolvió `/websites/reactrouter` (`Versions: 6.30.3, v5, 7.13.0`, Score `73.43`) y `/remix-run/react-router` (`Versions: 7.6.2, ..., v6.3.0`, Score `74.24`).
  - `query-docs`: `{ "libraryId": "/websites/reactrouter", "query": "MemoryRouter initialEntries Routes Route v6" }`.
- **Extracto real devuelto**:
  ```tsx
  function MemoryRouter({
    basename,
    children,
    initialEntries,
    initialIndex,
    useTransitions,
  }: MemoryRouterProps): React.ReactElement
  ```
- **Aporte y verificación contra el repo**:
  - Confirmó la firma exacta de `MemoryRouter` (`initialEntries`) y `useTransitions` (nota sobre `React.startTransition`) al montar los tests de integración de `App.tsx` en [PublicRoutes.test.tsx](../../../frontend/src/PublicRoutes.test.tsx) y los tests aislados de [MailAccionPage.test.tsx](../../../frontend/src/pages/mail/MailAccionPage.test.tsx), [MisTurnosPage.test.tsx](../../../frontend/src/pages/mis-turnos/MisTurnosPage.test.tsx) y [PreciosPage.test.tsx](../../../frontend/src/pages/precios/PreciosPage.test.tsx).
  - Al contrastar con `frontend/package.json` (`"react-router-dom": "6.28.0"`), se mantuvo el criterio `D1`: importar siempre desde `"react-router-dom"` y nunca desde `"react-router"` (v7).

### Consulta 2 — `@testing-library/react`: `cleanup()` y aislamiento entre renders múltiples

- **Solicitudes ejecutadas**:
  - `resolve-library-id`: `{ "libraryName": "@testing-library/react", "query": "render cleanup fireEvent findByRole" }` → resolvió `/testing-library/react-testing-library` (`Versions: ..., v16.3.2, ...`, Score `72.86`).
  - `query-docs`: `{ "libraryId": "/testing-library/react-testing-library", "query": "cleanup multiple renders findByRole async" }`.
- **Extracto real devuelto**:
  ```ts
  export function cleanup(): void
  ```
  - *"Unmounts every React tree mounted via `render` ... and removes auto-created containers from the document, restoring isolation between tests."*
  - *"Automatic Invocation: `afterEach(() => cleanup())` when a global `afterEach` exists."*
- **Aporte y corrección concreta**:
  - En `frontend/vitest.config.ts` / test de múltiples rutas dentro de un mismo escenario (`PublicRoutes.test.tsx`: `/precios`, `/mail/confirmar`, `/mail/cancelar`, `/mis-turnos`, `/reserva`), llamó explícitamente a `cleanup()` entre renders sucesivos dentro del mismo `it(...)`, evitando colisiones en el DOM entre rutas públicas montadas secuencialmente.

---

## 2. Auditoría de `validador-escenarios-turnos` sobre código y tests de `C-10`

### Corrección de seguridad detectada durante `/opsx:apply` (Antes vs. Después)

- **Hallazgo (`P12` — rutas públicas cerradas)**: el primer borrador de fase 2 en `CheckoutSimuladoPage.tsx` y `public.ts` invocaba `getEstadoPago(pagoId)` (`GET /api/pagos/{pago_id}`) para leer la seña después de simular. Al auditar el backend ([pagos.py](../../../backend/app/api/pagos.py)) y la lista cerrada de rutas públicas (`03 §3`), `GET /api/pagos/{pago_id}` es **staff-only** (`P8`/`P12`), por lo que un paciente anónimo habría recibido `401 Unauthorized`.
- **Corrección aplicada**:
  1. Se eliminó `getEstadoPago`, `EstadoPago` e `isEstadoPago` del cliente público ([public.ts](../../../frontend/src/api/public.ts), [types.ts](../../../frontend/src/api/types.ts), [index.ts](../../../frontend/src/api/index.ts)).
  2. `ReservaPage.tsx` pasa `monto_senia` desde el arancel público en los query params hacia `/checkout-simulado`, y `CheckoutSimuladoPage.tsx` usa exclusivamente la respuesta server-side de `POST /api/pagos/{pago_id}/simular` (`estado_pago`, `estado_turno`, `marca`), sin abrir nuevas rutas públicas ni mutar estados en cliente (`P10`/`P15`).

### Reporte de validación final sobre la implementación y suite de pruebas

```markdown
## Resultado de validación — validador-escenarios-turnos (Post-apply)
**Change**: C-10 frontend-reserva-publica
**Fecha**: 2026-11-17
**Validador**: validador-escenarios-turnos

### Veredicto
✅ Aprobado

### Reglas de negocio verificadas en código y tests
| Regla | Cobertura verificada (UI + Tests) | Referencia |
|---|---|---|
| RN-DOBLE | `ReservaPage` captura `409 SLOT_OCUPADO`, regresa al Paso 3 conservando DNI/datos y recarga disponibilidad | `ReservaPage.test.tsx`, `ReservaPage.tsx` |
| RN-SOLAPE | Slots tomados muestran disponibilidad actualizada y rechazo `409` reintentable sin pérdida de estado | `ReservaPage.tsx`, `MisTurnosPage.tsx` |
| RN-LIBERACION | Rechazar/Expirar en `/checkout-simulado` informa liberación automática y enlaza a `/reservar` | `CheckoutSimuladoPage.test.tsx`, `CheckoutSimuladoPage.tsx` |
| RN-PASADO | Selector de fecha bloquea fechas pasadas (`esFechaPasada`, `min={todayLocal()}`) en reserva y reprogramación | `PasoFechaHora.tsx`, `MisTurnosPage.tsx` |
| RN-ANTICIPACION | Slots dentro de `ANTICIPACION_MIN_HORAS` se deshabilitan (`fueraDeAnticipacion`); cancelación muestra cotización `100 % / 60 % / 0 %` antes de confirmar | `reservaUtils.ts`, `MisTurnosPage.test.tsx` |
| RN-SENIA-PAGO | Paso 4 y `/precios` muestran `monto_turno` y `monto_senia` pre-confirmación; reprogramación muestra aviso `Q3` sin calcular montos en cliente | `PasoResumen.tsx`, `PreciosPage.test.tsx`, `MisTurnosPage.test.tsx` |
| RN-PAGO-SIMULADO | Header `Idempotency-Key`, banner `"(simulado)"` + leyenda no fiscal, solo `POST /api/pagos/{pago_id}/simular` con `checkout_token` | `CheckoutSimuladoPage.test.tsx`, `publicClient.test.ts` |
| RN-ESTADOS | Sin transición en cliente; `/mail/confirmar`, `/mail/cancelar`, `/mis-turnos` y `/checkout-simulado` reflejan estados del servidor; `GET /api/pagos/{id}` staff-only eliminado (`P12`) | `MailAccionPage.test.tsx`, `PublicRoutes.test.tsx` |
| RN-CONSENTIMIENTO | Paso 1 bloquea avance si `consentimiento_datos = false` sin llamar a `POST /api/reservas` | `ReservaPage.test.tsx` |

### Ambigüedades abiertas respetadas (sin inventar reglas)
- **Q1 / Q9**: `PreciosPage` muestra `trial.dias` desde backend sin inventar límite cuando llega `null`.
- **Q3**: `MisTurnosPage` informa explícitamente conservación de seña original en MVP sin calcular recargos en frontend.

### Próximo paso
Todos los checks en verde; listo para `/opsx:archive c-10-frontend-reserva-publica` previa confirmación del equipo.
```
