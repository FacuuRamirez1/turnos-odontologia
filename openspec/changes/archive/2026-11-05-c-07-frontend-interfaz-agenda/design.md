# Design

## Context

El backend ya expone los contratos que esta interfaz consume (verificado contra el código, no contra documentación):

| Endpoint | Auth | Contrato relevante |
|---|---|---|
| `POST /api/auth/login` | público (rate-limit 5/60 s) | body `{email, password}` → `{access_token, token_type}`; refresh en cookie `refresh_token` HttpOnly, `path=/api/auth`, `SameSite=Lax` |
| `POST /api/auth/refresh` | cookie | rota el refresh y devuelve `{access_token, token_type}`; reuso → 401 |
| `POST /api/auth/logout` | Bearer | `{ok: true}`; blacklist + borra cookie |
| `GET /api/auth/me` | Bearer | `{sub, rol, email, odontologo_id: string|null}` |
| `GET /api/agenda` | Bearer staff | query `fecha` (YYYY-MM-DD) y `odontologo_id` UUID → `TurnoAgendaOut[]`; odontólogo con UUID ajeno → 403 |
| `POST /api/agenda/{id}/atendido` | Bearer staff | `TurnoAgendaOut`; solo `confirmado→atendido` |
| `POST /api/agenda/{id}/no-show` | Bearer staff | `TurnoAgendaOut`; solo `confirmado→no_show` y con `fin` ya pasado (si no, 422) |
| `GET /api/pacientes/{id}` | Bearer staff o action-token | `PacienteRead` (contacto + consentimiento, sin datos clínicos) |
| `GET /api/pacientes/{id}/turnos` | Bearer staff o action-token | `TurnoAcotado[]` (`turno_id, odontologo_id, inicio, fin, estado`) |

Errores del backend: envelope `{error, detail, path}` para `HTTPException`; `{code, detail}` en gates de negocio (p. ej. `CONSENTIMIENTO_REQUERIDO`); `{detail: [...]}` en validación FastAPI. La UI debe mostrar `detail` sin asumir una sola forma.

Brechas conocidas y verificadas:
- No existe `GET /api/odontologos` (solo `PATCH /api/odontologos/montos`). Recepción/admin no pueden descubrir UUIDs de profesionales.
- `main.py` no registra middleware CORS. El camino soportado es same-origin vía proxy de Vite (`/api` → `http://localhost:8000`), no llamadas cross-origin.
- `frontend/.env.example` sugiere una base absoluta; para el proxy conviene base relativa (`VITE_API_BASE_URL` vacío o same-origin).
- Los placeholders de `pages/*` son solo texto; no hay router, ni estilos, ni estado de sesión real.

## Goals / Non-Goals

**Goals**
- Login/logout/refresh reales, con access token solo en memoria y recuperación de sesión al recargar.
- Agenda del día fiel a `TurnoAgendaOut`, aislada por profesional, con estados de carga/vacío/error.
- Ficha mínima e historial acotado en un panel lateral, con foco en privacidad (sin caché persistente).
- Acciones `atendido`/`no_show` con feedback y refetch.
- TypeScript estricto sin `any`, accesibilidad AA y build sin warnings.

**Non-Goals**
- Pagos MP (C-07), devoluciones (C-08), mails (C-09), reserva pública (C-10), backoffice completo (C-11), reportes (C-12).
- Crear endpoints, migraciones o seeds; no se inventa el directorio de odontólogos.
- Persistir tokens, fichas o historial en almacenamiento del navegador.
- Tests E2E con navegador (no hay runner instalado); el gate es `typecheck + lint + build` más verificación funcional de escenarios.

## Decisions

1. **Access token en memoria + refresh por cookie HttpOnly.**
   - `AuthProvider` guarda `accessToken`, `user` y `status` en React state. No usa `localStorage`/`sessionStorage` (mitiga XSS; alineado con `auth-implementation-patterns`).
   - Al montar, si no hay token, llama `POST /api/auth/refresh` con `credentials: "include"`. Si responde 200, guarda access y pide `/me`; si 401, queda anónimo.
   - El cliente `fetch` siempre envía `credentials: "include"` para que la cookie viaje en same-origin/proxy.
   - Alternativa (localStorage): descartada por XSS. Alternativa (solo cookie): el backend no acepta refresh como auth de agenda; se necesita el access Bearer.

2. **Base de API relativa por defecto y proxy de Vite.**
   - `API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "")`.
   - En desarrollo se usa `/api` same-origin con el proxy existente; así la cookie `path=/api/auth` y el Bearer funcionan sin CORS.
   - Si se define una base absoluta, se documenta que requiere CORS en el backend; no se agrega CORS en este change (sería alcance backend).
   - Alternativa (base absoluta hardcodeada): descartada por CORS y por secretos/entornos.

3. **Selector de profesional consciente del rol.**
   - `odontologo`: `odontologo_id` se toma de `/me`; el campo se muestra como dato fijo y no editable. El backend igualmente rechaza un UUID ajeno con 403.
   - `recepcionista`/`admin`: input de UUID obligatorio, persistido solo en el query string (`?odontologo_id=...`) para poder compartir/bookmarkear la vista. No se persiste en storage.
   - **No se agrega `GET /api/odontologos`**: respetar el contrato existente y P14. La brecha queda como follow-up explícito en CHANGES.md.
   - Alternativa (hardcodear UUIDs del seed): descartada, frágil y filtra datos de entorno.

4. **Contratos tipados espejo + guardas de runtime mínimas.**
   - `api/types.ts` replica nombres y nulabilidad exactos (`snake_case` incluido) para evitar traducciones implícitas.
   - `EstadoTurno` es una unión cerrada; una guarda `isEstadoTurno` normaliza valores inesperados a `desconocido` sin romper el render.
   - `ApiError` conserva `status`, `code?` y `detail`; el cliente intenta parsear JSON y cae a un mensaje genérico si el body no es JSON.
   - Alternativa (`any` o `as unknown as` masivo): prohibida por P1 y por el lint `no-explicit-any`.

5. **Carga en paralelo y cancelación.**
   - La ficha abre `GET /pacientes/{id}` y `GET /pacientes/{id}/turnos` con `Promise.all` (skill Vercel: eliminar waterfalls).
   - Agenda y ficha usan `AbortController`; al cambiar fecha/profesional o selección se aborta la petición anterior para evitar carreras y `setState` tardío.
   - Tras `atendido`/`no_show` se refrescan agenda y ficha/historial en paralelo, no secuencialmente.

6. **Estado local, no store global.**
   - Solo la sesión es global (`AuthContext`). Agenda, selección y ficha viven en la página; no hay Redux/Zustand ni estado derivado en efectos innecesarios.
   - `useSearchParams` de React Router gobierna fecha y profesional (URL como fuente de verdad compartible).
   - Alternativa (store global): descartada por tamaño del change.

7. **Identidad visual “bitácora clínica”.**
   - Concepto: agenda como libreta de consultorio, no como dashboard SaaS. Riel horario vertical, filas tipo renglón con hora monoespaciada, acento verde pino y señal ámbar; bordes finos, sin grilla de tarjetas idénticas ni sombras difusas.
   - Paleta nombrada (6): `--porcelain #F3F6F4`, `--ink #14201C`, `--pine #1C4B3E`, `--mint #2F7D6B`, `--amber #B4681B`, `--danger #9E3434`; superficies blancas cálidas y hairlines.
   - Tipografía: pila sans del sistema para UI + monoespaciada para horas/UUIDs; escala 12/14/16/20/28/40, líneas < 80 ch.
   - Movimiento: una sola transición de entrada del panel de ficha; respeta `prefers-reduced-motion`.
   - Accesibilidad: contraste AA, foco visible, labels asociados, `aria-live="polite"` para errores, estados con texto además de color, targets ≥ 44 px.
   - Prohibiciones de `frontend-design` respetadas: nada de cream+serif+terracotta, SaaS-card-kit, eyebrows en mayúsculas ni flechas decorativas.

8. **Sin caché de datos de paciente.**
   - La ficha se pide al seleccionar y se descarta al cerrar o cambiar de turno. No se escribe en storage; el historial no se persiste. Esto reduce exposición de datos (P11) y mantiene el backend como única fuente.

## Skills y MCP aplicados (explícito)

### Skills propias del proyecto

| Skill | Cómo se aplica en este change | Evidencia verificable |
|---|---|---|
| `frontend-design` | Dos pasadas: plan de tokens + wireframe ASCII antes de codificar; identidad “bitácora clínica”; revisión contra defaults prohibidos. | `design.md` (Decisión 7), `styles/global.css` con tokens nombrados, revisión de copy y foco. |
| `vercel-react-best-practices` | Sin waterfalls: `Promise.all` en ficha y refetch; imports directos (sin barrels nuevos); estado derivado en render; `setState` funcional; render condicional con ternario; listas largas con `content-visibility`. | `pages/agenda/AgendaPage.tsx`, `components/FichaPacientePanel.tsx`, `api/*`. |
| `auth-implementation-patterns` | Access en memoria, refresh HttpOnly, logout con blacklist, RBAC y aislamiento siguen en backend; la UI no autoriza nada por sí sola. | `auth/AuthProvider.tsx`, `api/client.ts`, `api/auth.ts`. |
| `tdd` | Precondición no cumplida: no hay runner de frontend (Vitest/Jest) ni script `test`; el módulo Strict TDD solo aplica con runner disponible. Se sustituye por escenarios verificables en la spec + gate de build. | `frontend/package.json` (sin `test`), sección “Verification” de tasks. |
| `openspec-propose` / `openspec-apply-change` / `openspec-archive-change` | Artefactos SDD, implementación task-by-task y archivo con sync de specs. | `openspec/changes/c-07-frontend-interfaz-agenda/*`, `openspec validate`. |

### Herramientas MCP

| MCP | Uso concreto | Resultado |
|---|---|---|
| `context7` | Consulta de documentación de React Router v6 (`BrowserRouter`, `Routes`, `useNavigate`, rutas declarativas) antes de escribir el router. | Patrón de router declarativo aplicado en `App.tsx`; no se usó sintaxis de v7 ni data routers. |
| `engram` | Recuperación de contexto de C-05/C-06 al inicio y guardado de decisiones de este change con `topic_key: opsx/c-07-frontend-interfaz-agenda/{propose|apply|archive}`. | Contexto de sesiones previas y trazabilidad de decisiones. |

No se usan otros servidores MCP (no hay base de datos, scraping ni generación de imágenes en este change).

## Risks / Trade-offs

- **[Alto] Recepción/admin no pueden descubrir `odontologo_id`.** Mitigación: input UUID con validación, query string compartible y brecha documentada; follow-up `GET /api/odontologos` en un change posterior. No se hardcodean IDs.
- **[Medio] CORS si se usa base absoluta.** Mitigación: default relativo + proxy; `.env.example` documenta la alternativa same-origin. Si se despliega cross-origin, el backend debe agregar CORS (fuera de alcance).
- **[Medio] Cookie de refresh con `path=/api/auth`.** Solo se envía a rutas de auth; no sirve para autenticar agenda (correcto). El bootstrap debe llamar exactamente `/api/auth/refresh`.
- **[Medio] Deriva del enum de estados.** Mitigación: unión cerrada + guarda runtime + badge `desconocido`; un estado nuevo del backend no rompe la UI.
- **[Medio] `no_show` antes de `fin` → 422.** Mitigación: botón deshabilitado con explicación cuando el turno aún no terminó y mensaje del backend si igual se intenta.
- **[Bajo] Privacidad en el DOM.** Mitigación: no storage, no logs de datos de paciente, cierre de panel descarta el estado; el backend mantiene RBAC.
- **[Bajo] Sin tests automatizados de UI.** Mitigación: escenarios de spec + verificación manual guiada; agregar runner queda como follow-up.

## Migration Plan

- Sin migraciones de DB ni cambios de backend.
- Deploy: build estático de Vite (`npm run build`) servido same-origin con proxy/reverse-proxy hacia `/api`.
- Rollback: revertir los archivos de `frontend/src` y el router; no hay estado persistido que limpiar.

## Open Questions

- ¿Se agrega `GET /api/odontologos` (id + nombre) en un change posterior para eliminar el input manual de UUID? Propuesta: sí, change pequeño de contrato staff.
- ¿La agenda debe incluir nombre del paciente en la respuesta (`TurnoAgendaOut` hoy solo trae `paciente_id`)? Propuesta: evaluar junto con el directorio para evitar N+1 de fichas.
