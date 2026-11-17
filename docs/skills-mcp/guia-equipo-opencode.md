# Guía rápida para el equipo: cómo completar el TPI con OpenCode

> Esta guía reemplaza a la versión del TP de Skills + MCP. Ahora el objetivo es el **Trabajo Práctico Integrador (TPI) de Metodología I**: llevar el proyecto fundado a un **sistema funcionando** mediante changes completos (propuestos, aplicados, verificados y archivados), integrando la **skill propia** y el **MCP** con evidencia de uso real en esos changes.
>
> Meta del equipo: **completar todos los changes del roadmap** (`C-10`, `C-11`, `C-12`, `C-13`). `C-08` quedó completo y archivado el **16/11/2026**. El mínimo exigido por la cátedra es mucho menor, pero cada change que se cuente debe estar completo y probado.

---

## 1. Estado actual del repositorio (`main`)

| Concepto | Estado |
|---|---|
| **Changes archivados** (`openspec/changes/archive/`) | `C-01`, `C-02`, `C-03`, `C-04`, `C-05`, `C-06`, `C-07F` (frontend interfaz agenda), `C-07` (pagos simulados, webhook, guard `P15`), `C-09` (mails y recordatorios) y **`C-08`** (`devoluciones-comprobantes-conciliacion`, archivado el **16/11/2026**). |
| **Preparado, sin implementar** | `C-10` (`frontend-reserva-publica`) en [openspec/changes/c-10-frontend-reserva-publica/](../../openspec/changes/c-10-frontend-reserva-publica/proposal.md) (`proposal.md`, `specs/`, `design.md`, `tasks.md`). |
| **Pendientes** | `C-10`, `C-11`, `C-12`, `C-13` (ver [CHANGES.md](../../CHANGES.md)). `C-11` ya está desbloqueado por `C-08`. |
| **Migraciones** | Head actual = **`006_devolucion_comprobante`** (`C-08`). `C-09` → `004`, `C-07` → `005`. La `006` debe aplicarse **antes** del seed. |
| **Novedades de `C-08` (16/11)** | Backend: bandeja de devoluciones (alta al cancelar, cálculo 100/60, aprobación/rechazo/ejecución idempotente), recibos internos con PDF, conciliación de reembolsos + alertas, trazabilidad turno↔pago↔devolución↔comprobante y aviso de devolución por mail con PDF adjunto. **No tocó `frontend/`**: la UI de bandeja es `C-11`. |
| **Pruebas de `C-08`** | 17 archivos de test nuevos (~125 funciones), 12 archivos modificados, E2E `test_f2_devolucion_e2e.py` y test adversarial de la migración 006. |
| **Skill propia** | `validador-escenarios-turnos` en [SKILL.md](../../.agents/skills/validador-escenarios-turnos/SKILL.md), indexada en [.atl/skill-registry.md](../../.atl/skill-registry.md) y referenciada en [AGENTS.md](../../AGENTS.md) / [CLAUDE.md](../../CLAUDE.md). |
| **MCP** | Context7 (`@upstash/context7-mcp`) en [opencode.json](../../opencode.json), sin secretos. |
| **Evidencia acumulada** | [investigacion.md](investigacion.md), [aplicacion.md](aplicacion.md) y [evidencias/](evidencias/): TP anterior (`mcp-context7-ejecucion.md`, `skill-validador-ejecucion.md`), `skill-c08-propose.md` (veredicto ❌ → ✅) y `mcp-c08-apply.md`. En el TPI hay que sumar evidencia de **uso durante la implementación y verificación** de cada change nuevo. |

> Las restricciones del TP anterior (no implementar ni archivar `C-10`, no tocar `backend/` ni `frontend/`) **ya no rigen**. Pasamos a implementar.
>
> **Mínimo del TPI**: somos **4 integrantes**, así que el mínimo es **8 changes válidos** (2 × 4). Hoy hay **10 changes archivados**; para el mínimo solo cuentan los que estén completos, probados y verificados.

---

## 2. Qué exige el TPI (resumen operativo)

1. **Mínimo grupal**: 2 changes válidos por integrante (**4 integrantes = 8**). Cuentan los del Parcial 2. Nosotros ya superamos ese mínimo, pero **solo si cada change archivado tiene su alcance completo, tests ejecutados y funcionamiento real**. Archivar no reemplaza probar.
2. **Un change cuenta** cuando está: propuesto → aplicado → **verificado** (tests ejecutados antes de archivar + comprobación real) → archivado (OpenSpec y `CHANGES.md` actualizado). `C-08` es el modelo más reciente: 35 subtareas, 17 archivos de test nuevos y un E2E completo antes de archivar.
3. **Los pendientes se distinguen claramente** de los terminados: no se presentan como funcionalidades completas, ni en el README ni en el video.
4. **Skill propia y MCP son obligatorios** y deben tener **evidencia concreta de aplicación a un change**: solicitud, herramienta o procedimiento, resultado y aporte. Tenerlos instalados o listarlos no alcanza. Un change preparado con ellos solo cuenta para el mínimo si además está implementado, verificado y archivado.
5. **Todos los integrantes** participan y explican parte del trabajo en el video (cámara encendida en la presentación personal).
6. **Datos ficticios** de pacientes (`P11`) y **cero secretos** en repo, entrega y video (`P5`).
7. El equipo debe poder explicar, con palabras propias, qué problema resuelve cada change, qué generó o modificó y cómo se comprobó.

> **Qué es un change relevante (TPI)**: un avance coherente y verificable del roadmap, con propósito claro y resultado útil. No cuentan divisiones artificiales de tareas menores (crear cada carpeta, cambiar textos o generar archivos vacíos para llegar al número).
>
> **El TPI integra los dos trabajos anteriores**: la skill propia y el MCP son **obligatorios**, aunque la entrega independiente del TP de Skills + MCP haya sido opcional. Pueden aplicarse en la preparación, la implementación o la verificación de un change, y sirven como evidencia aunque el change todavía no esté archivado (pero para el mínimo el change debe estar completo).

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
| 1 | `C-10` `frontend-reserva-publica` | Ya está preparado. Empezar por la **Sección 1 de `tasks.md`** (costuras backend: `pago_id` en `ReservaOut`, `GET /api/precios`, respuestas de `/api/mail/*`) y recién después la UI. |
| 2 | `C-11` `frontend-agenda-backoffice` | Frontend. Ya está **desbloqueado**: la bandeja de `C-08` está archivada. Puede proponerse en paralelo con `C-10`, como permite `CHANGES.md`. |
| 3 | `C-12` `reportes-exportaciones` | Backend y exportaciones. Reutiliza comprobantes y trazabilidad de `C-08`. |
| 4 | `C-13` `hardening-cumplimiento-cierre` | Cierre: hardening, cumplimiento y revisión final de reglas duras. |

**Antes de pasar al siguiente change**, verificar que el anterior tenga: tasks completas, tests automatizados en verde, funcionamiento real comprobado (backend con Swagger o frontend con backend levantado), `openspec validate --all` sin errores, archivado y `CHANGES.md` en `[x]`.

**Si el tiempo no alcanza**: es válido entregar un alcance parcial, siempre que lo declarado esté completo. En ese caso los changes sin terminar quedan `[ ] pendiente` y se listan aparte en el README y en el video. No se archiva nada incompleto.

### 4.1 Qué hacer ahora (estado al 16/11)

`C-08` quedó archivado en [openspec/changes/archive/2026-11-16-c-08-devoluciones-comprobantes-conciliacion/](../../openspec/changes/archive/2026-11-16-c-08-devoluciones-comprobantes-conciliacion/proposal.md). Tareas concretas para seguir:

1. **Implementar `C-10`**: es el próximo change y ya tiene proposal/design/specs/tasks. En la vista `/mis-turnos` se puede mostrar la devolución del paciente (el backend ya la devuelve), pero **no hay vista de bandeja**: eso es `C-11`.
2. **Completar la evidencia de `C-08`**: [mcp-c08-apply.md](evidencias/mcp-c08-apply.md) solo cubre el **grupo 1** (SQLAlchemy/Alembic). Faltan las consultas de los grupos 2–8 (FastAPI/Pydantic, PDF, worker, tests) con solicitud, resultado y aporte. Es evidencia obligatoria del TPI y hoy está incompleta.
3. **Actualizar `README.md`**: todavía dice head `005`, no menciona la `006`, ni los endpoints/flujo de devoluciones, ni `PAGO_MODO`, `MP_WEBHOOK_SECRET` o `WORKER_*`. Dejarlo reproducible antes del video.
4. **Proponer `C-11`**: puede ir en paralelo con `C-10`; la bandeja backend de devoluciones ya existe.
5. **Si falta para el mínimo**: pueden agregar un change intermedio acotado sobre lo ya implementado (como se hizo con `C-07F`), siempre con alcance completo, pruebas y archivado. Actualizar `CHANGES.md` explicando qué adelanta, reemplaza o reduce, sin duplicar trabajo.
6. **Cada integrante**: confirmar commits propios (`P7`) y que su parte del video cubra un change completo con tests ejecutados.

---

## 5. Skill y MCP: dónde usarlos y cómo dejar evidencia

La evidencia del TP anterior alcanza para la preparación de `C-10`, pero el TPI pide mostrar **aporte concreto en los changes**. Usar las herramientas así:

| Momento | Herramienta | Uso concreto |
|---|---|---|
| `/opsx:propose` de cada change pendiente | Skill `validador-escenarios-turnos` | Auditar los escenarios (feliz, error de negocio, borde) contra las 9 reglas `RN-*` y las reglas `P*` antes de implementar. Guardar el reporte con veredicto. |
| `/opsx:apply` de changes de frontend (`C-10`, `C-11`) | MCP Context7 | Consultar `react`, `react-router-dom@6.28.0`, `vite` o `typescript` desde el agente y contrastar con `frontend/package.json` (el TP anterior ya detectó el desfase v6 contra v7). |
| `/opsx:apply` de changes de backend (`C-12`, `C-13`) | MCP Context7 | Consultar `fastapi`, `pydantic` v2, `sqlalchemy` o `alembic` para validar APIs reales antes de escribir código. |
| Antes de `/opsx:archive` | Skill | Contrastar los tests implementados con los escenarios y reglas. Si el veredicto es `❌ Reglas vulneradas`, corregir antes de archivar. |

**Estado de la evidencia (16/11)**: `C-08` dejó [skill-c08-propose.md](evidencias/skill-c08-propose.md) con el ciclo completo de la skill (detectó varios defectos en los escenarios, veredicto `❌` → correcciones → `✅`) y [mcp-c08-apply.md](evidencias/mcp-c08-apply.md) con dos consultas reales a Context7 (SQLAlchemy y Alembic). **Quedó incompleto**: el archivo declara que los grupos 2–8 se agregarían después y no se agregaron; completarlo es una tarea corta y obligatoria para el TPI.

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

### 6.1 Backend: migraciones, datos demo y pruebas (lo nuevo de `C-08`)

```powershell
cd backend
python -m alembic upgrade head        # head actual: 006_devolucion_comprobante
python -m app.infra.db.seed_dev       # idempotente: pago aprobado, devolución 60 % ejecutada y 2 recibos
python -m pytest app/tests/test_f2_devolucion_e2e.py -v
python -m app.workers.main            # worker de mails (Redis + SMTP/MailHog)
```

- `PAGO_MODO=simulado` es obligatorio en dev: con `PAGO_MODO=mercadopago` la ejecución de devoluciones responde `503` (v2 no construido, `P15`).
- `MP_WEBHOOK_SECRET` debe ser el mismo para el adaptador y el webhook, o la firma HMAC falla.
- Aplicar la migración **006 antes** de correr el seed.
- Mails en MailHog: `http://localhost:8025`. Con Compose: `docker compose up -d db redis mailhog worker api`.
- La **conciliación no corre sola** todavía (no está enganchada al worker); se verifica con `python -m pytest app/tests/test_pagos_conciliacion.py -v` y las alertas se leen en `GET /api/devoluciones/alertas`.
- **Q4 abierta**: toda devolución exige aprobación manual (ni la del 60 % se auto-aprueba). Una cotización 0 % no genera devolución ni recibo.
- En Windows, setear `WORKER_HEARTBEAT_FILE` a una ruta existente si se quiere heartbeat.

### 6.2 Endpoints que agregó `C-08` (para probar en Swagger)

Todos exigen JWT de staff (`odontologo`, `recepcionista` o `admin`); el odontólogo solo ve lo de sus propios turnos (403 si es ajeno).

| Método | Ruta | Qué hace |
|---|---|---|
| `GET` | `/api/devoluciones?estado=` | Bandeja de devoluciones con filtro por estado. |
| `GET` | `/api/devoluciones/alertas` | Alertas de conciliación de pagos/reembolsos. |
| `GET` | `/api/devoluciones/{id}` | Detalle de una devolución. |
| `POST` | `/api/devoluciones/{id}/aprobar` | `pendiente → aprobada` con `monto_confirmado`. |
| `POST` | `/api/devoluciones/{id}/rechazar` | `pendiente → rechazada` con motivo obligatorio. |
| `POST` | `/api/devoluciones/{id}/ejecutar` | `aprobada → ejecutada` vía proveedor + webhook; encola el aviso con recibo. |
| `GET` | `/api/comprobantes/{id}` | Detalle del recibo interno. |
| `GET` | `/api/comprobantes/{id}/pdf` | PDF del recibo (regenerado, `application/pdf`). |
| `GET` | `/api/turnos/{turno_id}/trazabilidad` | Turno ↔ pago ↔ devolución ↔ comprobantes + historial. |

Cambios de contrato a tener en cuenta:

- `POST /api/reservas/{id}/cancelar` ahora devuelve la **devolución persistida** o `null` (antes devolvía un objeto `pendiente` no persistido). Es un cambio **BREAKING** aprobado en `C-08`.
- `POST /api/webhooks/mercadopago` incorpora la rama `kind=devolucion` con idempotencia por `mp_refund_id`.
- `POST /api/pagos/{pago_id}/simular` ahora emite también el recibo de pago al aprobar.
- El paciente no tiene endpoint propio de devoluciones: la ve por `/mis-turnos` (a completar en `C-10`) o por el mail `aviso_devolucion` con PDF adjunto.

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
- **Subir el `.txt`** al espacio **Entrega TPI** de la comisión (C1, C3 o C4). Fechas y horarios se consultan en la tarea del campus.
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
- [ ] `.txt` completo con video, repositorio, cantidad de integrantes y nombres, con acceso verificado y subido al espacio **Entrega TPI** de la comisión.
