# Aplicación e Integración: Skill Propia y MCP Context7 (Parte 2)

> Continuidad de [investigacion.md](investigacion.md) para el proyecto `turnos-odontologia`, preparando el change pendiente **`C-10` (`frontend-reserva-publica`)** mediante Spec-Driven Development (`OPSX`) sin implementarlo ni archivarlo.

---

## 1. Integración en la fundación y verificación de descubrimiento

| Pieza incorporada | Cómo se integró en el repositorio | Verificación de descubrimiento y ejecución |
|---|---|---|
| **Skill propia**: `validador-escenarios-turnos` | Ubicada en [SKILL.md](../../.agents/skills/validador-escenarios-turnos/SKILL.md) (authoring inicial de Santino, completado y normalizado). Indexada en [.atl/skill-registry.md](../../.atl/skill-registry.md) (`16 total`), referenciada en la tabla de skills de [AGENTS.md](../../AGENTS.md) / [CLAUDE.md](../../CLAUDE.md) y documentada en [README.md §8](../../README.md). | El runtime cargó la skill en el listado de skills disponibles; se aplicó paso a paso sobre el borrador de `C-10` en [evidencias/skill-validador-ejecucion.md](evidencias/skill-validador-ejecucion.md). |
| **Servidor MCP**: `@upstash/context7-mcp` | Configurado en [opencode.json](../../opencode.json) (`type: local`, `npx -y @upstash/context7-mcp`, **sin secretos ni keys hardcoded**, `P5`), documentado en [AGENTS.md](../../AGENTS.md) / [CLAUDE.md](../../CLAUDE.md) y [README.md §8](../../README.md). | Sesión real JSON-RPC sobre `stdio` ejecutada (`Context7 Documentation MCP Server v4.7.0`): `tools/list` (`resolve-library-id`, `query-docs`) + llamadas reales `resolve-library-id("react-router")` y `query-docs("/remix-run/react-router", "useSearchParams")`. Salida verbatim en [evidencias/mcp-context7-ejecucion.md](evidencias/mcp-context7-ejecucion.md). |

---

## 2. Evidencia de uso en los changes del TPI (`C-08`, `C-10` y `C-11`)

- **`C-11` (`frontend-agenda-backoffice`, archivado en [2026-11-17-c-11-frontend-agenda-backoffice](../../openspec/changes/archive/2026-11-17-c-11-frontend-agenda-backoffice/proposal.md))**:
  - **Preparación (`propose`)**: [evidencias/skill-c11-propose.md](evidencias/skill-c11-propose.md) auditó RBAC de reserva telefónica (`odontologo` bloqueado), confirmación de `monto_confirmado` (`Q4`) y manejo `503` (`❌ → ✅`).
  - **Implementación y verificación (`apply`)**: [evidencias/mcp-c11-apply.md](evidencias/mcp-c11-apply.md) registró consultas reales a `Context7 v4.7.3` (`NavLink` + `findByRole`) y la corrección del badge de estado en `BandejaPage.tsx` (`StatusBadge` de turno vs `EstadoDevolucion`).
- **`C-10` (`frontend-reserva-publica`, archivado en [2026-11-17-c-10-frontend-reserva-publica](../../openspec/changes/archive/2026-11-17-c-10-frontend-reserva-publica/proposal.md))**:
  - **Preparación (`propose`)**: [evidencias/mcp-context7-ejecucion.md](evidencias/mcp-context7-ejecucion.md) confirmó `useSearchParams` y routing declarativo; [evidencias/skill-validador-ejecucion.md](evidencias/skill-validador-ejecucion.md) auditó `specs/frontend-reserva-publica/spec.md` contra las 9 `RN-*` (`❌ → ✅`).
  - **Implementación y verificación (`apply`)**: [evidencias/mcp-c10-apply.md](evidencias/mcp-c10-apply.md) registró consultas a `Context7 v4.7.2` (`/websites/reactrouter` `MemoryRouter` y `/testing-library/react-testing-library` `cleanup()`) y la auditoría final de `validador-escenarios-turnos`, que detectó y corrigió el llamado a `GET /api/pagos/{id}` (staff-only según `P12`) desde `CheckoutSimuladoPage.tsx`.
- **`C-08` (`devoluciones-comprobantes-conciliacion`, archivado en [2026-11-16-c-08-devoluciones-comprobantes-conciliacion](../../openspec/changes/archive/2026-11-16-c-08-devoluciones-comprobantes-conciliacion/proposal.md))**:
  - **Preparación (`propose`)**: [evidencias/skill-c08-propose.md](evidencias/skill-c08-propose.md) validó escenarios, RBAC y devolución `0 % / 60 % / 100 %` (`❌ → ✅`).
  - **Implementación (`apply` grupos 1–8)**: [evidencias/mcp-c08-apply.md](evidencias/mcp-c08-apply.md) documentó consultas reales a SQLAlchemy `2.0.44` (`CheckConstraint`, `postgresql_where`/`sqlite_where`), Alembic `1.17.1`, FastAPI (`Response` binaria PDF) y Pydantic `2.12` (`ConfigDict(extra='forbid')`).

---

## 3. Revisión crítica (Antes vs. Después) y limitaciones detectadas

1. **Corrección sobre la skill heredada (`validador-escenarios-turnos`)**:
   - *Antes*: faltaba frontmatter YAML (`name`/`description`) exigido para indexado automático, y la sección de criterio decía `"6 de las 8 reglas"` aunque la tabla declaraba **9** reglas (`RN-CONSENTIMIENTO` era la 9.ª).
   - *Después*: se agregó frontmatter YAML estándar y se unificó el criterio a `"6 de las 9 reglas"`, quedando registrada y detectada por el registry.
2. **Corrección sobre el borrador inicial de `C-10` (Antes vs. Después)**:
   - *Antes (`Borrador 1` → ❌ Reglas vulneradas)*: permitía consultar `/mis-turnos` solo con `DNI` (violando `P12`), omitía el bloqueo cuando `consentimiento_datos=false` (`RN-CONSENTIMIENTO`/`P11`), no explicitaba la marca `"(simulado)"` / `checkout_token` (`P10`/`P15`) y daba por cerrada la regla de seña en reprogramación ignorando `Q3`.
   - *Después (`Borrador 2` → ✅ Aprobado)*: exigió `dni + token` en `/mis-turnos`, bloqueo en Paso 1 sin consentimiento, flujo completo `POST /api/pagos/{pago_id}/simular` + `GET /api/pagos/{pago_id}` con marca `"(simulado)"` e idempotencia (`P4`), y explicitó la ambigüedad abierta `Q3` en `design.md`.
3. **Limitaciones reales detectadas durante la ejecución**:
   - **Desfase de versión en Context7 MCP**: `query-docs` sobre `/remix-run/react-router` devolvió ejemplos de **React Router v7** (`import { useSearchParams } from "react-router"`), mientras [frontend/package.json](../../frontend/package.json) fija `"react-router-dom": "6.28.0"`. El equipo lo detectó al cruzar la doc con el proyecto y fijó en `design.md` (`D1`) la regla obligatoria de importar desde `"react-router-dom"`.
   - **Brechas de contrato descubiertas al leer el backend real**: Context7 solo cubre librerías públicas, no el repo interno. Al contrastar los specs con [reservas.py](../../backend/app/api/reservas.py), [__init__.py](../../backend/app/api/__init__.py) y [mail.py](../../backend/app/api/mail.py), detectamos que `ReservaOut` aún no devolvía `pago_id`, `GET /api/precios` faltaba registrarse y `/api/mail/*` devolvía `HTMLResponse`; por eso `tasks.md` incorporó la Sección 1 de costuras backend antes del código UI.
   - **Sandbox sin red en Windows**: en entorno restringido sin red, `npx @upstash/context7-mcp` expira al intentar resolver/descargar; la ejecución real requiere conectividad habilitada (`BypassSandbox: true` o red abierta en el entorno local).

---

## 4. Archivos creados / modificados y motivo de cada cambio

| Archivo | Acción | Motivo |
|---|---|---|
| [.agents/skills/validador-escenarios-turnos/SKILL.md](../../.agents/skills/validador-escenarios-turnos/SKILL.md) | Modificado | Agregar frontmatter YAML y corregir inconsistencia `"8"` → `"9"` reglas en criterios de revisión. |
| [.atl/skill-registry.md](../../.atl/skill-registry.md) | Modificado | Indexar `validador-escenarios-turnos` (`16 total`) y registrar `AGENTS.md`/`CLAUDE.md` existentes. |
| [AGENTS.md](../../AGENTS.md) y [CLAUDE.md](../../CLAUDE.md) | Modificado | Incorporar skill propia y sección `Integración MCP (Context7)` en las instrucciones base del proyecto. |
| [opencode.json](../../opencode.json) | Creado | Declarar configuración reproducible del MCP local `@upstash/context7-mcp` sin secretos (`P5`). |
| [README.md](../../README.md) | Modificado | Actualizar estado Alembic/roadmap y agregar §8 documentando MCP Context7 y skill propia. |
| [evidencias/mcp-context7-ejecucion.md](evidencias/mcp-context7-ejecucion.md) | Creado | Guardar salida JSON-RPC verbatim de `tools/list`, `resolve-library-id` y `query-docs` + hallazgo v6 vs v7. |
| [evidencias/skill-validador-ejecucion.md](evidencias/skill-validador-ejecucion.md) | Creado | Documentar validación real Antes/Después de `C-10` con `validador-escenarios-turnos`. |
| [docs/skills-mcp/aplicacion.md](aplicacion.md) | Creado | Informe final Parte 2 del TP integrando verificación, evidencia, crítica y trazabilidad. |
| [openspec/changes/archive/2026-11-17-c-10-frontend-reserva-publica/](../../openspec/changes/archive/2026-11-17-c-10-frontend-reserva-publica/proposal.md) | Archivado | Implementación completa (`backend` + `frontend`), `483` tests pytest y `41` tests Vitest, archivado y marcado `[x]` en [CHANGES.md](../../CHANGES.md). |
| [evidencias/mcp-c10-apply.md](evidencias/mcp-c10-apply.md) | Creado | Evidencia `Context7` + auditoría `validador-escenarios-turnos` en el apply de `C-10` (incluye corrección `P12`). |
| [evidencias/mcp-c08-apply.md](evidencias/mcp-c08-apply.md) | Actualizado | Consultas SQLAlchemy/Alembic (grupo 1) + FastAPI/Pydantic (grupos 2–8) aplicadas en `C-08`. |
| [openspec/changes/archive/2026-11-17-c-11-frontend-agenda-backoffice/](../../openspec/changes/archive/2026-11-17-c-11-frontend-agenda-backoffice/proposal.md) | Archivado | Backoffice staff (`/agenda`, `/bandeja`, disponibilidad/bloqueos, `Q10`, trazabilidad, PDF) + `51` tests Vitest y `[x]` en [CHANGES.md](../../CHANGES.md). |
| [evidencias/skill-c11-propose.md](evidencias/skill-c11-propose.md) y [evidencias/mcp-c11-apply.md](evidencias/mcp-c11-apply.md) | Creados | Validación de escenarios en `propose` + consultas Context7 `NavLink`/RTL y corrección `EstadoDevolucion` en `apply` de `C-11`. |
