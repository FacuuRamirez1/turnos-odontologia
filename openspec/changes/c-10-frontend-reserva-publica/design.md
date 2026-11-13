# Design: `C-10` — `frontend-reserva-publica`

> **Estado**: Change **preparado** (solo planificación OPSX; no implementado ni archivado).

## Context

`C-10` expone la cara pública del sistema de turnos odontológicos para que un paciente (`R1`) pueda reservar un turno, pagar la seña en modo simulado (`D14` / `PAGO_MODO=simulado`), gestionar acciones desde links de correo (`/mail/confirmar`, `/mail/cancelar`), consultar sus turnos (`/mis-turnos` con `dni + token`) y revisar tarifas/trial (`/precios`) sin exponer datos de otros pacientes ni romper la fuente de verdad en servidor.

Estado actual verificado en el repositorio:
- **Backend (`C-05`, `C-07`, `C-09` archivados)**: existen `GET /api/disponibilidad`, `POST /api/reservas` (`ReservaCreate` / `ReservaOut`), `GET/POST /api/reservas/{turno_id}/cotizar-cancelacion|cancelar|reprogramar`, `GET /api/mis-turnos`, `POST /api/pagos/{pago_id}/simular`, `GET /api/pagos/{pago_id}`, `POST /api/webhooks/mercadopago` y `GET /api/mail/confirmar|cancelar`.
- **Frontend (`C-07F` archivado)**: `frontend/package.json` usa React `18.3.1`, `react-router-dom` `6.28.0`, TypeScript `5.6.3` estricto (`no any`) y Vite `6.0.3`. `main.tsx` monta `<BrowserRouter>` y `api/client.ts` provee `apiFetch<T>(path, { auth })` (requiere `auth: false` para llamadas públicas). `pages/reserva/ReservaPage.tsx` es actualmente un placeholder mínimo.
- **Brechas de contrato detectadas al inspeccionar el código real**:
  1. `ReservaOut` en `backend/app/api/reservas.py` no incluye `pago_id`, pero el endpoint sandbox `POST /api/pagos/{pago_id}/simular` lo requiere en la ruta, y `PagoSimuladoAdapter.generar_checkout` arma `?token=...` sin `pago_id`.
  2. `PUBLIC_ROUTES` en `backend/app/api/__init__.py` reserva `"GET /precios"`, pero aún no existe un router `precios.py` ni su endpoint en `/api/precios`.
  3. `GET /api/mail/confirmar` y `GET /api/mail/cancelar` actualmente devuelven `HTMLResponse` directo en lugar de una respuesta JSON consumible por la SPA en `/mail/confirmar` y `/mail/cancelar`.

## Goals / Non-Goals

### Goals
- Entregar una SPA pública accesible sin login para las 6 rutas públicas permitidas (`03 §3`, `P12`) más la pantalla sandbox `/checkout-simulado` (`D14`, `P15`).
- Mantener tipado estricto TypeScript (`P1`: prohibido `any`, componentes en PascalCase) y validación de payload en backend (`P2`: `extra="forbid"`).
- Garantizar que **ningún cambio de estado de pago o turno** ocurre en el cliente: toda confirmación pasa por `POST /api/pagos/{pago_id}/simular` -> `POST /api/webhooks/mercadopago` (server-to-server, `P10`) y se refleja consultando `GET /api/pagos/{pago_id}`.
- Mostrar de forma explícita la marca **`"(simulado)"`** en todo comprobante/banner/estado de pago cuando `PAGO_MODO=simulado` (`P15`).
- Proteger privacidad y consentimiento: `consentimiento_datos` obligatorio (`P11`, `RN-CONSENTIMIENTO`), `GET /api/mis-turnos` con `dni + token` (`P12`), y mensajes de error sin filtrar datos de terceros.
- Cubrir la verificación con tests unitarios/componentes/integración (Vitest + React Testing Library + backend pytest de las brechas de contrato).

### Non-Goals
- **No** integrar checkout real de MercadoPago (`PAGO_MODO=mercadopago` es v2, `P13`).
- **No** implementar panel de agenda/backoffice ni bandeja de devoluciones (`C-11`).
- **No** agregar funcionalidades v2: WhatsApp, ARCA/AFIP, lista de espera con escritura, sobreturnos o multi-sede (`P13`).
- **No** autenticar pacientes con contraseña propia ni permitir consulta de `/mis-turnos` solo con DNI (`P12`).

## Decisions

### D1. Enrutamiento SPA con `react-router-dom@6.28.0` (validado con Context7 MCP)
- **Decisión**: Todas las importaciones de routing y lectura de query params (`BrowserRouter`, `Routes`, `Route`, `useSearchParams`, `useNavigate`, `Link`) se importarán desde **`"react-router-dom"`**, manteniendo compatibilidad exacta con `frontend/package.json` (`"react-router-dom": "6.28.0"`).
- **Por qué (evidencia MCP)**: La consulta a Context7 (`/remix-run/react-router`) mostró snippets de v7 importando desde `"react-router"`. Como el proyecto fija `6.28.0` en `react-router-dom`, seguir el paquete v6 evita errores de compilación `tsc --noEmit` y runtime.
- **Rutas públicas en `App.tsx`** (separadas de rutas autenticadas de backoffice):
  - `/reservar` → `ReservaPage` (wizard 4 pasos).
  - `/checkout-simulado` → `CheckoutSimuladoPage` (lee `?pago_id=&token=` vía `useSearchParams`).
  - `/mail/confirmar` y `/mail/cancelar` → `MailAccionPage` (lee `?token=` vía `useSearchParams`).
  - `/mis-turnos` → `MisTurnosPage` (formulario `dni + token` o `?dni=&token=` por URL).
  - `/precios` → `PreciosPage` (tarifas vigentes y prueba inicial D11).

### D2. Wizard de reserva en 4 pasos y manejo de estado local sin confirmación optimista
- **Decisión**: Estructurar `ReservaPage` en 4 pasos secuenciales con estado tipado discriminado:
  1. **Datos y Consentimiento**: `dni`, `nombre`, `apellido`, `email`, `telefono` y checkbox obligatorio `consentimiento_datos` (`P11` / `RN-CONSENTIMIENTO`: si es `false`, bloquea avance y muestra aviso claro; nunca envía `false` esperando confirmar turno). Si se implementa precarga segura por reconocimiento, solo ocurre dentro de una sesión/flujo acotado sin exponer listados de pacientes ajenos.
  2. **Profesional**: selección desde lista pública de profesionales/aranceles (`GET /api/precios`) mostrando `monto_turno` y `monto_senia` antes de confirmar (`A4`).
  3. **Fecha y Horario**: consulta `GET /api/disponibilidad?odontologo_id=&fecha=`, deshabilita fechas pasadas (`RN-PASADO`) y advierte ventana mínima de anticipación (`RN-ANTICIPACION`).
  4. **Resumen y Creación**: muestra monto total, seña a abonar, regla de liberación automática (`RN-LIBERACION`) y marca `(simulado)` si aplica. Al confirmar, llama `POST /api/reservas` (`auth: false`).
- **Manejo de 409 / expiración / rechazo (`A5`)**: Un `409 Conflict` (slot tomado o regla de solape/doble reserva) o un rechazo/expiración en checkout simulado devuelve al usuario al Paso 3 conservando los datos del Paso 1 y recargando disponibilidad fresca.

### D3. Flujo de Checkout Simulado (`P10`, `P15`, `D14`)
- **Decisión**: Tras `POST /api/reservas`, si la respuesta incluye `checkout_url` / `checkout_token` y `pago_id`, la SPA navega a `/checkout-simulado?pago_id={pago_id}&token={checkout_token}` (o usa el `state` tipado de navegación respaldado por query params para tolerar F5).
- `CheckoutSimuladoPage` exhibe el banner destacado **`"Checkout Simulado (simulado)"`**, el monto de la seña y 3 acciones explícitas: **Aprobar**, **Rechazar** y **Expirar**.
- Cada botón ejecuta `POST /api/pagos/{pago_id}/simular` (`auth: false`) con `{ accion, checkout_token }` y luego consulta `GET /api/pagos/{pago_id}` para reflejar el estado persistido en DB tras la ejecución del webhook server-to-server. Si falta `token` o el `checkout_token` ya fue consumido (HTTP `409`/`404`/`422`), muestra error claro sin permitir doble cobro (`P4`).

### D4. Costuras mínimas necesarias en Backend (sin reescribir `C-07`)
Para conectar la SPA con datos reales sin inventar datos mock en producción ni violar `P2`/`P10`/`P12`:
1. **`ReservaOut.pago_id` y `PagoSimuladoAdapter.generar_checkout`**: Agregar `pago_id: UUID | None = None` en `ReservaOut` (`backend/app/api/reservas.py`) y pasar `pago_id` en la query string de `checkout_url` (`/checkout-simulado?pago_id=...&token=...`) en `PagoSimuladoAdapter` (`backend/app/infra/pago_simulado/adapter.py`).
2. **`GET /api/precios` (`D11`, `03 §3.6`)**: Agregar router `backend/app/api/precios.py` registrado bajo `/api` con schema Pydantic `extra="forbid"` (`PrecioOdontologoPublicoOut`, `PreciosPublicosOut`), rate-limit público y únicamente campos públicos de odontólogos activos (sin PII de pacientes).
3. **Acciones de mail (`/api/mail/confirmar`, `/api/mail/cancelar`)**: Soportar negociación por cabecera `Accept: application/json` (o respuesta JSON estructurada cuando la SPA consulta vía `fetch` y redirección/links hacia `FRONTEND_URL/mail/confirmar?token=...`), preservando compatibilidad con los tests de `C-09`.

### D5. Cliente API tipado (`frontend/src/api/public.ts` + `types.ts`)
- **Decisión**: Crear `frontend/src/api/public.ts` usando exclusivamente `apiFetch<T>(..., { auth: false })` y schemas TypeScript estrictos espejando los modelos Pydantic `extra="forbid"`.
- Mapeo explícito de errores HTTP (`400`, `404`, `409`, `422`, `429`) a mensajes en español orientados al paciente, sin volcar stack traces ni detalles internos.

### D6. Estrategia de Testing Frontend (Vitest + React Testing Library)
- **Decisión**: Incorporar `vitest`, `@testing-library/react`, `@testing-library/jest-dom` y `jsdom` como `devDependencies` en `frontend/package.json` y script `"test": "vitest run"`, manteniendo `tsc --noEmit`, `eslint` y `vite build` en verde. Justificación: actualmente no existe test runner configurado en `frontend/package.json` y la regla `U2` exige TDD (RED -> GREEN -> TRIANGULATE con 3 escenarios) antes de implementar UI.

## Risks / Trade-offs

- **Brecha `pago_id` / `GET /precios` / `/mail/*` en backend**: Obliga a incluir 3 tareas backend acotadas dentro de `C-10`. *Mitigación*: mantener los cambios estrictamente retrocompatibles con `C-05`, `C-07` y `C-09`, con tests de contrato backend antes de tocar frontend.
- **Ambigüedad abierta `Q3` (seña en reprogramación)**: `knowledge-base/10_preguntas_abiertas.md` aún marca `Q3` pendiente de confirmación clínica. *Mitigación*: `C-10` consume exactamente el monto/regla devuelto por `GET /api/reservas/{turno_id}/cotizar-cancelacion` y advierte explícitamente en UI que la política aplicable es la informada por el servidor.
- **Fuga accidental de PII en rutas públicas (`P11`, `P12`)**: Cualquier autocompletado por DNI mal diseñado podría filtrar nombre/email/teléfono a un tercero. *Mitigación*: `C-10` nunca precarga PII sin token válido o sesión controlada y en `/mis-turnos` exige `dni + token` siempre.
- **Desfase de docs MCP**: Documentación React Router v7 en Context7 podría tentar a usar imports `"react-router"`. *Mitigación*: regla explícita en D1 verificada por `npm run typecheck`.

## Open Questions

- **`Q1` (anticipación mínima de reserva)**: Se lee el parámetro configurado en backend (`ANTICIPACION_RESERVA_MIN_MINUTOS`); la SPA muestra el límite devuelto o error de negocio al intentar reservar debajo del umbral.
- **`Q3` (política exacta de seña al reprogramar)**: Pendiente de cierre definitivo del cliente; mientras tanto la SPA delega el cálculo al endpoint de cotización/reprogramación del backend y refleja su mensaje sin calcular importes en cliente.
- **`Q4` (multidioma / multi-sede)**: Fuera de alcance en v1 (`P13`); textos únicamente en español (`es-AR`).
