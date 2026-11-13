# Guía rápida para el equipo: cómo seguir y qué pedirle a OpenCode

> Esta guía explica en qué estado quedó `main`, qué **no** hay que tocar antes de entregar el TP de **Metodología I**, cómo sumar commits propios por integrante y qué prompts copiar y pegar en **OpenCode** para terminar la entrega y continuar el desarrollo.

---

## 1. Estado actual del repositorio (`main`)

| Hito | Commit en `main` | Qué quedó hecho |
|---|---|---|
| **`C-07` (`pagos-mp-checkout-webhook`)** | `285e4de` | Pagos simulados (`PAGO_MODO=simulado`, `D14`), webhook server-to-server idempotente, conciliación, guard `P15` y tests. Ya **implementado y archivado**. |
| **TP Parte 1 — Investigación** | `4da88b8` | Ficha de investigación y decisión en [investigacion.md](investigacion.md). |
| **TP Parte 2 — Integración y `C-10`** | `ad50ebb` | Skill propia integrada ([SKILL.md](../../.agents/skills/validador-escenarios-turnos/SKILL.md) + [.atl/skill-registry.md](../../.atl/skill-registry.md)), MCP Context7 configurado ([opencode.json](../../opencode.json)), [AGENTS.md](../../AGENTS.md) / [CLAUDE.md](../../CLAUDE.md) / [README.md](../../README.md) actualizados, evidencias reales en [evidencias/](evidencias/mcp-context7-ejecucion.md), informe en [aplicacion.md](aplicacion.md) y change **`C-10`** (`frontend-reserva-publica`) **preparado** en [openspec/changes/c-10-frontend-reserva-publica/](../../openspec/changes/c-10-frontend-reserva-publica/proposal.md). |

---

## 2. Reglas clave ANTES de entregar el TP de Metodología I

1. **NO implementar ni archivar `C-10` todavía**:
   - La consigna del TP exige entregar un único change **preparado** (`proposal.md`, `specs/`, `design.md`, `tasks.md`), **sin** implementarlo ni archivarlo.
   - En [CHANGES.md](../../CHANGES.md) el `C-10` **debe seguir figurando como `[ ] pendiente`** hasta después de la entrega del TP.
2. **Tampoco modificar código productivo (`backend/` o `frontend/`)** en la rama de entrega del TP.
3. **Commits propios de cada integrante (`P7`)**:
   - Todos los integrantes deben tener commits propios en el historial con su nombre y email reales (y **sin** líneas de co-autoría de IA).
   - Ideas válidas para sumar el aporte propio antes de cerrar el TP:
     - Crear o completar **`ENTREGA.md`** con los datos del equipo, rol de cada integrante y el link al video.
     - Revisar/enriquecer notas de defensa o aclaraciones puntuales en `docs/skills-mcp/investigacion.md` o `docs/skills-mcp/aplicacion.md`.
     - Ejecutar una validación extra desde OpenCode (por ejemplo, una consulta de Context7 MCP sobre `react-router-dom` v6 o una re-auditoría de un escenario con `validador-escenarios-turnos`) y documentar esa observación.
4. **No subir el enunciado (`documento-practica (4).pdf`)** si está local sin trackear: dejarlo fuera de `git add`.

---

## 3. Comandos rápidos al entrar al repositorio

```bash
# 1. Traer lo último de main
git pull origin main

# 2. Verificar que tu identidad Git sea la tuya (regla P7)
git config user.name
git config user.email

# 3. Verificar que C-10 y todo OpenSpec validan sin errores
openspec status --change c-10-frontend-reserva-publica
openspec validate --all
```

> **Nota sobre MCP Context7 en OpenCode**: [opencode.json](../../opencode.json) ya declara el servidor local `context7` (`npx -y @upstash/context7-mcp`, sin secretos). Si abrís OpenCode en la raíz del proyecto, necesita acceso a Node (`npx`) y salida a internet para descargar/consultar Context7 en tiempo real.

---

## 4. Qué instrucciones darle a OpenCode (copiar y pegar)

### Prompt A — Onboarding y armado de `ENTREGA.md` + guion del video (antes de entregar el TP)

```text
Leé AGENTS.md, CHANGES.md, docs/skills-mcp/investigacion.md, docs/skills-mcp/aplicacion.md,
docs/skills-mcp/evidencias/mcp-context7-ejecucion.md, docs/skills-mcp/evidencias/skill-validador-ejecucion.md
y la carpeta openspec/changes/c-10-frontend-reserva-publica/.

NO implementes código en backend/ ni frontend/, NO archives C-10 ni cambies su estado [ ] pendiente en CHANGES.md,
y NO hagas git commit ni git push sin mi confirmación explícita (U1).

Con esa base:
1. Resumime en 5 puntos qué quedó armado para el TP de Metodología I.
2. Ayudame a redactar ENTREGA.md en la raíz del repo con la estructura pedida por la cátedra
   (integrantes, rol de cada uno, links a investigacion.md, aplicacion.md, evidencias y C-10, y espacio para el link del video).
3. Armá un guion de demostración de máximo 5 minutos repartido entre los integrantes del grupo.
```

---

### Prompt B — Demostrar en vivo la skill propia y el MCP Context7 en OpenCode (para grabar el video o verificar)

```text
Usando el proyecto actual y respetando AGENTS.md (sin modificar código de producción ni commitear):
1. Consultá el MCP context7 (resolve-library-id + query-docs) sobre react-router-dom / useSearchParams
   y contrastalo con la versión real declarada en frontend/package.json (6.28.0) y el diseño D1 de
   openspec/changes/c-10-frontend-reserva-publica/design.md.
2. Aplicá la skill validador-escenarios-turnos sobre openspec/changes/c-10-frontend-reserva-publica/specs/frontend-reserva-publica/spec.md
   y explicá cómo cubre las 9 reglas RN-*, los 3 escenarios obligatorios (feliz, error de negocio, borde),
   P12 (/mis-turnos con token), P11 (consentimiento) y P15 (marca "(simulado)").
```

---

### Prompt C — Cómo seguir el desarrollo del sistema DESPUÉS de entregar el TP

> ⚠️ **Usar este prompt recién después de haber entregado/cerrado el TP de Metodología I.**

```text
Ya entregamos el TP de Metodología I. Leé AGENTS.md, CHANGES.md y openspec/changes/c-10-frontend-reserva-publica/.
Queremos retomar el desarrollo del proyecto respetando las reglas duras U1–U3 y P1–P15:
- Aplicá /opsx:apply sobre c-10-frontend-reserva-publica siguiendo el orden de tasks.md
  (empezando por la Sección 1 de costuras backend + vitest, con TDD RED → GREEN → TRIANGULATE en 3 escenarios).
- Antes de avanzar a un siguiente change (por ejemplo C-08 devoluciones-comprobantes-conciliacion o C-11),
  verificá todos los checks de la sección 5, pedime confirmación para /opsx:archive y preguntame antes de commitear (U1).
```

---

## 5. Checklist final antes de subir el TP a la cátedra

- [ ] Cada integrante tiene al menos un commit propio en `main` con su autoría real (`P7`, sin co-autoría de IA).
- [ ] Existe `ENTREGA.md` completo (integrantes, repo, rama/tag o commit, y link accesible al video).
- [ ] Video de demostración ≤ 5 minutos donde participan los integrantes explicando:
  - Por qué eligieron la skill `validador-escenarios-turnos` y el MCP `@upstash/context7-mcp`.
  - Cómo se integraron en la fundación ([AGENTS.md](../../AGENTS.md), [.atl/skill-registry.md](../../.atl/skill-registry.md), [opencode.json](../../opencode.json)).
  - Evidencia real de ejecución de MCP + skill y qué errores/desfases concretos ayudaron a corregir en **`C-10`** (`P12`, `RN-CONSENTIMIENTO`, `Q3`, `react-router-dom@6.28.0` vs v7, costuras backend).
- [ ] `openspec validate --all` devuelve todo en verde y `C-10` sigue como `[ ] pendiente` en [CHANGES.md](../../CHANGES.md).
- [ ] Archivo comprimido nombrado exactamente **`TP-Skills-MCP-Apellido1-Apellido2-Apellido3.zip`** (sin `node_modules`, `.venv` ni `.env`).
