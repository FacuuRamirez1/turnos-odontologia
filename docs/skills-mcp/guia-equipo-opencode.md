# Guía rápida para el equipo: cómo completar el TPI con OpenCode

> Esta guía reemplaza a la versión del TP de Skills + MCP. Ahora el objetivo es el **Trabajo Práctico Integrador (TPI) de Metodología I**: llevar el proyecto fundado a un **sistema funcionando** mediante changes completos (propuestos, aplicados, verificados y archivados), integrando la **skill propia** y el **MCP** con evidencia de uso real en esos changes.
>
> Meta del equipo: **completar todos los changes del roadmap** (`C-08`, `C-10`, `C-11`, `C-12`, `C-13`). El mínimo exigido por la cátedra es mucho menor, pero cada change que se cuente debe estar completo y probado.

---

## 1. Estado actual del repositorio (`main`)

| Concepto | Estado |
|---|---|
| **Changes archivados** (`openspec/changes/archive/`) | `C-01`, `C-02`, `C-03`, `C-04`, `C-05`, `C-06`, `C-07F` (frontend interfaz agenda), `C-07` (pagos simulados, webhook, guard `P15`) y `C-09` (mails y recordatorios). |
| **Preparado, sin implementar** | `C-10` (`frontend-reserva-publica`) en [openspec/changes/c-10-frontend-reserva-publica/](../../openspec/changes/c-10-frontend-reserva-publica/proposal.md) (`proposal.md`, `specs/`, `design.md`, `tasks.md`). |
| **Pendientes** | `C-08`, `C-10`, `C-11`, `C-12`, `C-13` (ver [CHANGES.md](../../CHANGES.md)). |
| **Skill propia** | `validador-escenarios-turnos` en [SKILL.md](../../.agents/skills/validador-escenarios-turnos/SKILL.md), indexada en [.atl/skill-registry.md](../../.atl/skill-registry.md) y referenciada en [AGENTS.md](../../AGENTS.md) / [CLAUDE.md](../../CLAUDE.md). |
| **MCP** | Context7 (`@upstash/context7-mcp`) en [opencode.json](../../opencode.json), sin secretos. |
| **Evidencia previa (TP anterior)** | [investigacion.md](investigacion.md), [aplicacion.md](aplicacion.md) y [evidencias/](evidencias/mcp-context7-ejecucion.md). Es evidencia de **preparación** de `C-10`; en el TPI hay que sumar evidencia de **uso durante la implementación y verificación**. |

> Las restricciones del TP anterior (no implementar ni archivar `C-10`, no tocar `backend/` ni `frontend/`) **ya no rigen**. Pasamos a implementar.

---

## 2. Qué exige el TPI (resumen operativo)

1. **Mínimo grupal**: 2 changes válidos por integrante (3 integrantes = 6). Cuentan los del Parcial 2. Nosotros ya superamos ese mínimo, pero **solo si cada change archivado tiene su alcance completo, tests ejecutados y funcionamiento real**. Archivar no reemplaza probar.
2. **Un change cuenta** cuando está: propuesto → aplicado → **verificado** (tests ejecutados antes de archivar + comprobación real) → archivado (OpenSpec y `CHANGES.md` actualizado).
3. **Los pendientes se distinguen claramente** de los terminados: no se presentan como funcionalidades completas, ni en el README ni en el video.
4. **Skill propia y MCP son obligatorios** y deben tener **evidencia concreta de aplicación a un change**: solicitud, herramienta o procedimiento, resultado y aporte. Tenerlos instalados o listarlos no alcanza. Un change preparado con ellos solo cuenta para el mínimo si además está implementado, verificado y archivado.
5. **Todos los integrantes** participan y explican parte del trabajo en el video (cámara encendida en la presentación personal).
6. **Datos ficticios** de pacientes (`P11`) y **cero secretos** en repo, entrega y video (`P5`).
7. El equipo debe poder explicar, con palabras propias, qué problema resuelve cada change, qué generó o modificó y cómo se comprobó.

---

## 3. Reglas del proyecto que siguen vigentes

- **U1**: nunca commitear ni pushear sin pedido explícito del equipo.
- **U2**: nunca producción sin test en rojo primero (RED → GREEN → TRIANGULATE con 3 escenarios: feliz, error de negocio y borde).
- **U3**: nada de skills globales (`-g`); todo va a `.agents/skills/`.
- **P1–P15** de [AGENTS.md](../../AGENTS.md). Especialmente: `P1` (sin `any`), `P2` (`extra='forbid'`), `P3` (migraciones Alembic), `P4`/`P10` (pagos solo por webhook e idempotencia), `P11` (consentimiento y DNI ficticios), `P12` (rutas públicas), `P14` (leer `CHANGES.md` antes de `/opsx:propose`) y `P15` (marca "(simulado)").
- **P7**: commits convencionales, **sin co-autoría de IA** y con **commits propios de cada integrante**. Repartan los changes entre los integrantes para que todos tengan autoría real en el historial.

---

## 4. Plan de trabajo: completar todos los changes

Ciclo por cada change (siempre en este orden y sin saltear el archivado formal):

```text
/opsx:propose  →  validar escenarios con la skill  →  /opsx:apply (TDD)  →  verificar  →  /opsx:archive  →  marcar [x] en CHANGES.md
```

**Orden sugerido** (confirmar dependencias reales en [CHANGES.md](../../CHANGES.md) antes de cada `/opsx:propose`, `P14`):

| Orden | Change | Observación |
|---|---|---|
| 1 | `C-08` `devoluciones-comprobantes-conciliacion` | Backend. Hay que proponerlo desde cero. Según el roadmap, `C-11` requiere su bandeja. |
| 2 | `C-10` `frontend-reserva-publica` | Ya está preparado. Empezar por la **Sección 1 de `tasks.md`** (costuras backend: `pago_id` en `ReservaOut`, `GET /api/precios`, respuestas de `/api/mail/*`) y recién después la UI. |
| 3 | `C-11` `frontend-agenda-backoffice` | Frontend. Depende de la bandeja de `C-08`. |
| 4 | `C-12` `reportes-exportaciones` | Backend y exportaciones. |
| 5 | `C-13` `hardening-cumplimiento-cierre` | Cierre: hardening, cumplimiento y revisión final de reglas duras. |

**Antes de pasar al siguiente change**, verificar que el anterior tenga: tasks completas, tests automatizados en verde, funcionamiento real comprobado (backend con Swagger o frontend con backend levantado), `openspec validate --all` sin errores, archivado y `CHANGES.md` en `[x]`.

**Si el tiempo no alcanza**: es válido entregar un alcance parcial, siempre que lo declarado esté completo. En ese caso los changes sin terminar quedan `[ ] pendiente` y se listan aparte en el README y en el video. No se archiva nada incompleto.

---

## 5. Skill y MCP: dónde usarlos y cómo dejar evidencia

La evidencia del TP anterior alcanza para la preparación de `C-10`, pero el TPI pide mostrar **aporte concreto en los changes**. Usar las herramientas así:

| Momento | Herramienta | Uso concreto |
|---|---|---|
| `/opsx:propose` de cada change pendiente | Skill `validador-escenarios-turnos` | Auditar los escenarios (feliz, error de negocio, borde) contra las 9 reglas `RN-*` y las reglas `P*` antes de implementar. Guardar el reporte con veredicto. |
| `/opsx:apply` de changes de frontend (`C-10`, `C-11`) | MCP Context7 | Consultar `react`, `react-router-dom@6.28.0`, `vite` o `typescript` desde el agente y contrastar con `frontend/package.json` (el TP anterior ya detectó el desfase v6 contra v7). |
| `/opsx:apply` de changes de backend (`C-08`, `C-12`, `C-13`) | MCP Context7 | Consultar `fastapi`, `pydantic` v2, `sqlalchemy` o `alembic` para validar APIs reales antes de escribir código. |
| Antes de `/opsx:archive` | Skill | Contrastar los tests implementados con los escenarios y reglas. Si el veredicto es `❌ Reglas vulneradas`, corregir antes de archivar. |

**Cómo registrar cada uso** en [evidencias/](evidencias/mcp-context7-ejecucion.md) (un archivo por uso, con nombre claro, por ejemplo `skill-c08-propose.md` o `mcp-c10-apply.md`), incluyendo siempre:

1. Qué se pidió (prompt textual) y en qué change y fase.
2. Qué herramienta se ejecutó (nombre de la skill o tool del MCP, por ejemplo `resolve-library-id` y `query-docs`) y cómo se confirmó la conexión.
3. El resultado obtenido (extracto real, sin secretos).
4. El aporte: qué se corrigió o decidió gracias a esto (diff, commit, línea del spec).
5. Cómo se revisó el resultado antes de aceptarlo.

Además, actualizar [aplicacion.md](aplicacion.md) con los changes donde se aplicaron las herramientas. Mantener en el repo la skill, sus referencias y las instrucciones reproducibles del MCP, sin credenciales.

> **Para la skill**: el equipo debe poder explicar en el video qué necesidad resuelve, con qué skill creadora se hizo (`skill-creator`), cómo se adaptó y dónde está integrada. Conviene dejar esa explicación escrita en [investigacion.md](investigacion.md) o [aplicacion.md](aplicacion.md).

---

## 6. Comandos rápidos al entrar al repositorio

```bash
# 1. Traer lo último de main
git pull origin main

# 2. Verificar que tu identidad Git sea la tuya (regla P7)
git config user.name
git config user.email

# 3. Ubicarse en el estado de OpenSpec
openspec list --json
openspec status --change "<nombre-del-change>"
openspec validate --all
```

> **MCP Context7 en OpenCode**: [opencode.json](../../opencode.json) declara el servidor local `context7` (`npx -y @upstash/context7-mcp`, sin secretos). Abrir OpenCode en la raíz del proyecto; necesita Node (`npx`) y salida a internet.

---

## 7. Prompts para OpenCode (copiar y pegar)

### Prompt A — Proponer el siguiente change (con skill)

```text
Leé AGENTS.md y CHANGES.md y revisá el estado real con openspec list y openspec status.
Quiero proponer el change <C-NN nombre> respetando dependencias y las reglas duras U1–U3 y P1–P15.
1. Ejecutá /opsx:propose para generar proposal, specs, design y tasks.
2. Aplicá la skill validador-escenarios-turnos sobre los escenarios (feliz, error de negocio, borde)
   y mostrame el reporte completo con veredicto. Si es ❌, corregí los specs y volvé a validar.
3. Guardá el reporte en docs/skills-mcp/evidencias/ con la solicitud, el resultado y el aporte.
No implementes código ni hagas git commit sin mi confirmación (U1).
```

### Prompt B — Implementar un change (con MCP y TDD)

```text
Aplicá /opsx:apply sobre <nombre-del-change> siguiendo el orden de tasks.md, con TDD estricto
(RED → GREEN → TRIANGULATE, 3 escenarios por comportamiento).
Antes de usar una API de una librería, consultá el MCP context7 (resolve-library-id + query-docs)
y contrastá la versión con frontend/package.json o backend/requirements.txt.
Registrá en docs/skills-mcp/evidencias/ cada consulta relevante: qué pedimos, qué devolvió y qué cambió en el código.
No commitees ni pushees sin mi confirmación (U1).
```

### Prompt C — Verificar y archivar

```text
Para <nombre-del-change>: ejecutá toda la suite de tests relacionada, mostrame los resultados,
y comprobá el funcionamiento real (backend levantado con Swagger y, si hay frontend, el flujo completo).
Aplicá la skill validador-escenarios-turnos para contrastar los tests contra los escenarios y las reglas RN-*.
Si todo está en verde, pedime confirmación y recién entonces ejecutá /opsx:archive y marcá [x] en CHANGES.md.
Si algo falla o falta, decímelo con el detalle y no archives.
```

### Prompt D — Demostración en vivo de skill y MCP (para el video)

```text
Sin modificar código ni commitear, demostrá en vivo:
1. Una consulta al MCP context7 (resolve-library-id + query-docs) sobre una librería que usa el change actual,
   contrastada con la versión real declarada en el proyecto.
2. La skill validador-escenarios-turnos aplicada a un spec real, explicando cómo cubre las reglas RN-*,
   los 3 escenarios obligatorios, y qué corrigió o confirmó.
```

---

## 8. Entrega y video

- **Video de hasta 10 minutos** por equipo. Todos hablan y muestran la pantalla real; las diapositivas solo acompañan. Distribución sugerida:
  - `0:00–0:30`: presentación del equipo y alcance alcanzado.
  - `0:30–3:00`: recorrido por los changes completos (propósito, resultado y verificación); mostrar roadmap y archivado.
  - `3:00–6:00`: skill propia y MCP (creación o conexión, integración y aplicación concreta con evidencia).
  - `6:00–10:00`: resultado de los tests y demostración del sistema funcionando hasta el alcance declarado.
- **Preparar entorno y datos ficticios antes de grabar**, con backend y frontend levantados.
- **Archivo `.txt`** con el nombre `TPI-C?-Apellido1-Apellido2-Apellido3.txt` (reemplazar la comisión: C1, C3 o C4, y conservar solo los apellidos que correspondan). Formato:

```text
ENTREGA — TPI METODOLOGÍA I
Comisión: <1, 3 o 4>
Video explicativo: <link>
Repositorio del proyecto: <link>
Cantidad de integrantes: <n>
Integrantes:
1. Nombre Apellido
2. Nombre Apellido
3. Nombre Apellido
```

- **No dejar campos de ejemplo** y comprobar que el docente pueda acceder al video y al repositorio.
- El repo debe contener todo el avance: fundación, roadmap actualizado, artefactos SDD y changes archivados, código, tests, la skill propia y la documentación del MCP.
- El **`README.md`** debe permitir reproducir lo presentado: requisitos, instalación, configuración de ejemplo sin secretos, datos ficticios, arranque de backend y frontend, acceso a Swagger, ejecución de tests, y una indicación clara de qué está completo y qué queda pendiente.

---

## 9. Checklist final antes de entregar

- [ ] Total de changes archivados válidos ≥ 2 por integrante, y cada uno con alcance completo, tests ejecutados y funcionamiento comprobado.
- [ ] `CHANGES.md` actualizado: lo terminado en `[x]`, lo pendiente claramente separado (nada incompleto presentado como completo).
- [ ] `openspec validate --all` en verde y changes archivados en `openspec/changes/archive/`.
- [ ] Skill propia y MCP con evidencia de aplicación en changes (solicitud, herramienta, resultado y aporte) dentro de `docs/skills-mcp/evidencias/`.
- [ ] Cada integrante tiene commits propios con autoría real (`P7`, sin co-autoría de IA).
- [ ] El sistema arranca y permite ejecutar todo lo declarado; el README permite reproducirlo.
- [ ] Sin secretos (`.env`, claves, tokens) en el repo, la entrega ni el video; solo datos ficticios.
- [ ] Todos los integrantes hablan en el video y la duración total no supera los 10 minutos.
- [ ] `.txt` completo con video, repositorio, cantidad de integrantes y nombres, con acceso verificado.
