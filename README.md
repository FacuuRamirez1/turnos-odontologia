# Turnos Consultorio Odontología

SaaS de gestión odontológica single-sede (v1): agenda multi-profesional con
protección anti-solapamiento a nivel de base de datos, reserva online en 3–4
pasos, seña con pagos simulados en el MVP (checkout simulado + webhook server-to-server firmado; MercadoPago real = v2/producción), recordatorios
por mail vía workers Redis, ficha mínima de paciente con consentimiento
bloqueante, agenda de staff aislada por profesional y reportes/caja mínimos.

Stack: Python + FastAPI (Pydantic v2) · SQLAlchemy + Alembic · PostgreSQL ·
Redis · Docker / Docker Compose · React + TypeScript estricto + Vite.
Pagos [MVP]: proveedor simulado detrás del mismo puerto/adaptador (`PAGO_MODO=simulado`, D14); MercadoPago real = v2/producción. Mail [v1]: SMTP vía workers Redis, solo desde
`MAIL_FROM` alineado. WhatsApp y ARCA apagados en v1 (`WHATSAPP_ENABLED=false`,
`ARCA_ENABLED=false`).

## Video explicativo / demostración

Video de demostración del sistema (enlace pendiente).

## 1. Clonar y prerrequisitos

```bash
git clone https://github.com/FacuuRamirez1/turnos-odontologia.git
cd turnos-odontologia
```

### Prerrequisitos

| Herramienta | Versión mínima real | Fuente en el repo |
|---|---|---|
| Python | 3.11 | `backend/Dockerfile` (`python:3.11-slim`), CI `setup-python 3.11`, `ruff target py311`, `mypy python_version 3.11` |
| Node.js | 20 | `frontend/Dockerfile` (`node:20-slim`), CI `setup-node 20` |
| npm | incluida con Node 20 (`npm ci` / `npm install` en CI y Dockerfile) | `.github/workflows/ci.yml`, `frontend/Dockerfile` |
| Docker + Docker Compose | cualquiera con soporte `docker compose` v2 (Compose lee `${VAR:-default}`) | `docker-compose.yml` |
| PostgreSQL | 16 (imagen `postgres:16` + extensión `pgcrypto`) | `docker-compose.yml`, `backend/app/infra/db/init-pgcrypto.sql` |
| Redis | 7 (imagen `redis:7-alpine`) | `docker-compose.yml` |
| MailHog (solo dev local) | `mailhog/mailhog:v1.0.1` | `docker-compose.yml` |

Versiones pinneadas relevantes:

| Paquete | Versión | Fuente |
|---|---|---|
| fastapi | 0.119.0 | `backend/requirements.txt` |
| SQLAlchemy | 2.0.44 | `backend/requirements.txt` |
| alembic | 1.17.1 | `backend/requirements.txt` |
| pydantic | 2.12.4 | `backend/requirements.txt` |
| react / react-dom | 18.3.1 | `frontend/package.json` |
| typescript | 5.6.3 | `frontend/package.json` |
| vite | 6.0.3 | `frontend/package.json` |
| react-router-dom | 6.28.0 | `frontend/package.json` |

## 2. Configurar entorno y levantamiento

```bash
cp .env.example .env
docker compose up -d --build
curl http://localhost:8000/api/health
# {"status":"ok","service":"turnos-odontologia"}
```

Rollback dev (base vacía, borra el volumen `pgdata`):

```bash
docker compose down -v
```

### Variables de entorno (`.env.example` → `.env`)

Copiar el contrato canónico de la raíz (`.env.example`; hay espejos por
sub-proyecto en `backend/.env.example` y `frontend/.env.example`). Solo se
documentan nombres y propósito — jamás valores reales (P5):

| Variable | Propósito |
|---|---|
| `DATABASE_URL` | Conexión SQLAlchemy/psycopg a PostgreSQL |
| `REDIS_URL` | Conexión a Redis (colas de mail, reintentos, idempotencia) |
| `JWT_SECRET` | Firma de JWT access/refresh/acción (cambiar en producción) |
| `JWT_ACCESS_MIN` | TTL del access token, en minutos |
| `JWT_REFRESH_DIAS` | TTL del refresh token, en días |
| `JWT_ACTION_MIN` | TTL de tokens de acción por mail, en minutos |
| `PAGO_MODO` | `simulado` (default MVP/dev) o `mercadopago` (diseñado, no construido en el MVP). **Nunca `simulado` en producción** (P15) |
| `MP_WEBHOOK_SECRET` | Firma HMAC del webhook server-to-server de pagos y devoluciones; obligatorio también en modo simulado |
| `MP_ACCESS_TOKEN` / `MP_PUBLIC_KEY` | Opcionales: solo requeridas si `PAGO_MODO=mercadopago` (ficticias en dev) |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` | Salida SMTP (en dev apuntan a MailHog) |
| `MAIL_FROM` | Único remitente alineado autorizado (P14) |
| `RECORDATORIO_VENTANA_HS` | Ventana de recordatorios por mail |
| `MAIL_ACTION_TTL_MIN` / `MAIL_RATE_LIMIT` | TTL y rate-limit de links públicos `/api/mail/confirmar` y `/api/mail/cancelar` |
| `RESERVA_TTL_MIN` / `RESERVA_RATE_LIMIT` | TTL de la pre-reserva de slot y rate-limit por IP |
| `ANTICIPACION_MIN_HS` | Anticipación mínima configurable de slots |
| `TIMEZONE` | Zona del consultorio (`America/Argentina/Cordoba`) |
| `API_PUBLIC_URL` / `FRONTEND_URL` | URLs públicas de backend y frontend para links de mail |
| `WORKER_SCHEDULER_TICK_S` / `WORKER_HEARTBEAT_FILE` | Tick del scheduler del worker de mails y ruta opcional de heartbeat en disco |
| `WHATSAPP_ENABLED` / `ARCA_ENABLED` | Flags v2, siempre `false` en v1 (P13) |
| `VITE_API_BASE_URL` | (solo `frontend/.env.example`) base URL pública de la API |
| `API_PORT` / `WEB_PORT` / `PG_PORT` / `REDIS_PORT` / `MAILHOG_SMTP_PORT` / `MAILHOG_HTTP_PORT` | Overrides de puertos del Compose (defaults abajo) |

### Servicios (`docker-compose.yml`)

| Servicio | Función | Puerto host (default sobreescribible) |
|---|---|---|
| `api` | FastAPI (`uvicorn app.main:app`), healthcheck contra `GET /api/health` | `8000` (`API_PORT`) |
| `web` | Frontend Vite dev (`npm run dev -- --host 0.0.0.0 --port 5173`), proxy `/api` → `http://localhost:8000` | `5173` (`WEB_PORT`) |
| `db` | PostgreSQL 16 + pgcrypto, volumen `pgdata` | `5432` (`PG_PORT`) |
| `redis` | Colas de mail, reintentos, idempotencia | `6379` (`REDIS_PORT`) |
| `mailhog` | SMTP fake + UI web para dev | SMTP `1025` (`MAILHOG_SMTP_PORT`), UI `8025` (`MAILHOG_HTTP_PORT`) |
| `worker` | Worker de mails (`python -m app.workers.main`, cola `mail:pendientes`) | sin puerto publicado |

URLs útiles en dev: API `http://localhost:8000`, health
`http://localhost:8000/api/health`, web `http://localhost:5173`, MailHog UI
`http://localhost:8025`.

## 3. Migraciones, seed y tests

Todos los comandos existen en el repo y se verificaron contra
`backend/alembic.ini`, `backend/pytest.ini`, `backend/app/infra/db/seed_dev.py`,
`.github/workflows/ci.yml` y `backend/app/api/health.py`.

### Migraciones (Alembic)

```bash
cd backend
python -m alembic current    # revisión aplicada (requiere DB levantada y sana)
python -m alembic upgrade head
```

Revisiones reales en `backend/alembic/versions/`:
`001_core_v2off.py` (core + tablas v2 apagadas), `002_disponibilidad_bloqueo.py`,
`003_turno_historial.py`, `004_recordatorio_mail.py`, `005_pago_evento_pago.py`
y `006_devolucion_comprobante.py` (head actual tras `C-08`). Aplicar `upgrade head`
**antes** de ejecutar `seed_dev`. Cero `create_all` en runtime (P3).

### Seed dev (datos ficticios, idempotente)

```bash
cd backend
python -m app.infra.db.seed_dev
```

Punto de entrada `main()` en `backend/app/infra/db/seed_dev.py` (asume la
migración base `006` aplicada). Inserta por natural-key con `ON CONFLICT DO NOTHING`:
2 odontólogos (L–V 9–17, 30 min, montos distintos), 1 recepcionista + 1 admin,
5 pacientes con DNI ficticios y consentimiento, feriado + bloqueo de ejemplo,
1 pago aprobado con recibo y 1 devolución 60 % ejecutada con recibo (todos
simulados, D14). Sin escrituras v2 (P13), sin datos reales (P11). Re-corridas
no duplican.

### Tests

```bash
cd backend && python -m pytest app/tests/ -v   # o: pytest -q (como en CI; testpaths=app/tests)
cd frontend && npm install && npm run typecheck && npm run test
```

Suite backend en `backend/app/tests/` (config `backend/pytest.ini`,
convención `test_*.py`): salud, contrato de env, migraciones 001–006, seed,
auth JWT + RBAC + rate-limit, disponibilidad/motor de slots, reservas/estados/
expiración TTL, pagos simulados/webhook, devoluciones/comprobantes/conciliación
(`test_f2_devolucion_e2e.py`), ficha + consentimiento, aislamiento por profesional,
precios públicos y acciones de mail JSON/HTML. Suite frontend en Vitest + React
Testing Library (`npm run test`): cliente público, wizard `/reservar`,
`/checkout-simulado`, `/mail/*`, `/mis-turnos`, `/precios` e integración de
rutas públicas.

### Linters y tipos

```bash
cd backend && ruff check app   # config [tool.ruff] en backend/pyproject.toml
cd backend && mypy app        # config [tool.mypy] strict en backend/pyproject.toml
cd frontend && npm run lint    # eslint src --max-warnings 0
cd frontend && npm run build   # tsc --noEmit && vite build
```

Scripts frontend reales (`frontend/package.json`): `dev` (vite), `build`
(`tsc --noEmit && vite build`), `preview`, `typecheck` (`tsc --noEmit`), `lint`,
`test` (`vitest run`).
`tsconfig.json` estricto (`strict`, `noImplicitAny`, `strictNullChecks`,
`noUnusedLocals/Parameters`); prohibido `any` (P1).

### Health check y flujos implementados

```bash
curl http://localhost:8000/api/health
# {"status":"ok","service":"turnos-odontologia"}
```

- **Salud**: `GET /api/health` (Swagger interactivo en `http://localhost:8000/docs`).
- **Reportes y exportaciones (`C-12`)**: staff-only (JWT; odontólogo ve solo lo propio, P8) bajo `/api/reportes`: `GET /asistencia`, `/caja`, `/mail` (JSON) y `/turnos.csv|pdf`, `/caja.csv|pdf`, `/auditoria.csv` (descarga). Parámetros `desde`, `hasta` (YYYY-MM-DD, máx. 366 días) y `odontologo_id` opcional (solo recepción/admin). La caja y sus exportaciones llevan la marca "(simulado)" con `PAGO_MODO=simulado`. No son rutas públicas (P12).
- **Reserva pública (`C-10`)**: en `http://localhost:5173` están habilitadas `/reservar` (`/reserva`), `/checkout-simulado`, `/mail/confirmar`, `/mail/cancelar`, `/mis-turnos` (exige `dni + token`, P12) y `/precios` (D11), además de `GET /api/precios`.
- **Backoffice staff (`C-11`, JWT obligatorio)**: en `http://localhost:5173/agenda` y `/bandeja` están habilitados agenda aislada por rol (`P8`), disponibilidad/bloqueos, reserva telefónica `Q10` (solo `recepcionista`/`admin`), cancelar/reprogramar staff, trazabilidad auditable y bandeja de devoluciones con recibos PDF simulados (`"(simulado)"`).
- **Devoluciones, comprobantes y trazabilidad (`C-08`, staff-only JWT)**: `GET /api/devoluciones`, `GET /api/devoluciones/alertas`, `GET /api/devoluciones/{id}`, `POST /api/devoluciones/{id}/aprobar|rechazar|ejecutar`, `GET /api/comprobantes/{id}`, `GET /api/comprobantes/{id}/pdf` y `GET /api/turnos/{turno_id}/trazabilidad`.

## 4. Estructura del repositorio

Árbol real de la raíz (una línea por carpeta/archivo clave):

```text
turnos-odontologia/
├── backend/                 # FastAPI + SQLAlchemy + Alembic (app, migraciones, tests)
│   ├── app/api/             # Routers: health, auth, disponibilidad, public_disponibilidad, reservas, agenda, pacientes, odontologos, pagos, precios, devoluciones, comprobantes, turnos, mis_turnos, mail
│   ├── app/core/            # settings (env), security JWT/passwords, errors/envelope
│   ├── app/domain/          # Lógica de dominio: turnos, disponibilidad, pagos, devoluciones, comprobantes, notificaciones, reportes, pacientes
│   ├── app/infra/db/        # Modelos, BaseRepository/UoW, session, seed_dev.py, seed_data/, init-pgcrypto.sql
│   ├── app/infra/           # Adaptadores db/redis/mp/pago_simulado/smtp
│   ├── app/workers/         # Worker de mails Redis (python -m app.workers.main)
│   ├── app/tests/           # Suite pytest (test_*.py, conftest, helpers)
│   └── alembic/             # env.py + versions/001 a 006
├── frontend/                # SPA React 18 + TS estricto + Vite 6 (Vitest + RTL)
│   └── src/                 # api/{client,public}, auth/, components/, pages/{reserva,mail,mis-turnos,precios,agenda,bandeja,reportes}, App.tsx
├── openspec/                # Cambios OPSX: changes/archive/, changes/, specs/
├── docs/skills-mcp/         # Fichas, guía de equipo y evidencias del TP/TPI de Metodología I
├── knowledge-base/          # Fuente de verdad del dominio (11 docs: 01 visión … 11 pagos, MP real + modo simulado D14)
├── discovery/               # discovery.md/pdf fuente de la KB
├── CHANGES.md               # Índice canónico de los 13 changes, dependencias y roadmap
├── AGENTS.md / CLAUDE.md    # Instrucciones de agentes (stack, skills, MCP Context7, reglas duras U1–U3/P1–P15)
├── opencode.json            # Configuración MCP reproducible del proyecto (context7, sin secretos)
├── docker-compose.yml       # Topología local: api, web, db, redis, mailhog, worker
├── .env.example             # Contrato canónico de entorno (copiar a .env; jamás commitear .env real)
├── .github/workflows/ci.yml # CI: backend (ruff + mypy + pytest) y frontend (tsc + eslint + build) en paralelo
├── .agents/skills/          # Skills de proyecto (auth, fastapi, postgres, redis, tdd, frontend…)
└── .engram/                 # Memoria persistente del proyecto (observaciones y resúmenes de sesión)
```

No existe `tests/` en la raíz: los tests viven en `backend/app/tests/`.

## 5. CI/CD

Workflow real `.github/workflows/ci.yml` (nombre `ci`, corre en `push` y
`pull_request`, jobs paralelos; un fallo bloquea el merge):

- `backend` (Python 3.11, `working-directory: backend`): `pip install -r
  requirements.txt` → `ruff check app` → `mypy app` → `pytest -q`.
- `frontend` (Node 20, caché npm): `npm ci` → `npm run typecheck` → `npm run
  lint` → `npm run build`.

Secretos solo vía env vars (P5).

## 6. Troubleshooting

| Síntoma | Causa probable | Solución |
|---|---|---|
| `port is already allocated` en `docker compose up` | Puertos 8000/5173/5432/6379/1025/8025 ocupados | Sobreescribir vía `.env`: `API_PORT`, `WEB_PORT`, `PG_PORT`, `REDIS_PORT`, `MAILHOG_SMTP_PORT`, `MAILHOG_HTTP_PORT`; verificar con `docker compose config` |
| La API no arranca / `DATABASE_URL` inválida | Falta `.env` o variables sin completar | `cp .env.example .env` y completar según la tabla de §2 (nunca pegar secretos reales en el repo) |
| `docker: command not found` o daemon apagado | Docker apagado | Iniciar Docker Desktop / daemon y reintentar `docker compose up -d --build` |
| `alembic upgrade head` falla / tablas vacías | DB sin migrar o `db` no healthy | Esperar `service_healthy` de `db`, luego `python -m alembic current` y `python -m alembic upgrade head`; verificar volumen `pgdata` |
| Seed duplica o falla | Migración base sin aplicar | Aplicar `upgrade head` primero; el seed es idempotente (`ON CONFLICT DO NOTHING`), re-correr `python -m app.infra.db.seed_dev` es seguro |
| Frontend no habla con la API | `VITE_API_BASE_URL` incorrecta | Revisar `frontend/.env.example` (`VITE_API_BASE_URL=http://localhost:8000`); el proxy Vite redirige `/api` a `localhost:8000` |
| Mails no llegan en dev | Se espera MailHog, no SMTP real | Abrir `http://localhost:8025`; en Compose la API usa `SMTP_HOST=mailhog:1025` |

## 7. Estado actual y roadmap

- **Cerrados (verificado en `openspec/changes/archive/` y `CHANGES.md [x]`, 12 changes)**:
  `C-01` `foundation-setup`, `C-02` `core-models-usuarios-pacientes`, `C-03`
  `auth-jwt-rbac`, `C-04` `disponibilidad-slots`, `C-05` `reserva-turnos-estados`,
  `C-06` `ficha-paciente-consentimiento`, `C-07F` `frontend-interfaz-agenda`,
  `C-07` `pagos-mp-checkout-webhook` (modo simulado D14), `C-09`
  `mails-recordatorios`, `C-08` `devoluciones-comprobantes-conciliacion`,
  `C-10` `frontend-reserva-publica` y `C-11` `frontend-agenda-backoffice`.
- **Total del roadmap**: 13 changes en 7 fases (`CHANGES.md`) + `C-07F` intermedio.
- **Camino crítico (9)**: `C-01 → C-02 → C-03 → C-04 → C-05 → C-07 → C-08 → C-11 → C-13`.
- **Pendientes**: `C-12` `reportes-exportaciones` y `C-13` `hardening-cumplimiento-cierre`.
- **Nota**: head actual de migraciones = `006_devolucion_comprobante` (`C-08`). El
  `2026-11-05-c-07-frontend-interfaz-agenda` archivado en openspec corresponde a
  `C-07F` (frontend); `C-07` quedó en `2026-11-13-c-07-pagos-mp-checkout-webhook`,
  `C-08` en `2026-11-16-c-08-devoluciones-comprobantes-conciliacion`, `C-10` en
  `2026-11-17-c-10-frontend-reserva-publica` y `C-11` en
  `2026-11-17-c-11-frontend-agenda-backoffice`.
- **Guion de demostración TPI**: [guion-video-tpi.md](docs/skills-mcp/guion-video-tpi.md).
- **Pagos (D14, 2026-11-05)**: en el MVP la seña usa un proveedor simulado
  (`PAGO_MODO=simulado`) detrás del mismo puerto/adaptador; la bandeja y el flujo
  de devoluciones/recibos (`C-08`) y reserva/checkout público (`C-10`) operan con
  marca explícita `"(simulado)"`. Ver `knowledge-base/11_pagos_mercadopago.md` §0.

Gobernanza: leer `CHANGES.md` y la KB relevante antes de cada
`/opsx:propose`; reglas duras en `AGENTS.md` (U1–U3, P1–P15). Sin commit ni push
sin pedido explícito (U1).

## 8. Integración MCP y Skill propia (Metodología I)

### Servidor MCP (`Context7` — `@upstash/context7-mcp`)

- **Propósito**: consultar documentación oficial y ejemplos por versión de las librerías del stack (`react`, `react-router-dom`, `vite`, `fastapi`, etc.) en modo **solo lectura** durante la exploración y planificación SDD. No accede a PostgreSQL, Redis, archivos `.env` ni datos de pacientes.
- **Requisitos**: Node.js `>= 20` (`npm` / `npx` en PATH) y acceso HTTP de salida a Context7.
- **Variables de entorno**: ninguna obligatoria para uso estándar; opcionalmente `CONTEXT7_API_KEY` para mayor cuota, referenciada vía entorno (`{env:CONTEXT7_API_KEY}`), jamás escrita en archivos versionados (`P5`).
- **Configuración reproducible del proyecto** ([opencode.json](opencode.json)):
  ```json
  {
    "$schema": "https://opencode.ai/config.json",
    "mcp": {
      "context7": {
        "type": "local",
        "command": ["npx", "-y", "@upstash/context7-mcp"],
        "enabled": true
      }
    }
  }
  ```
  Para clientes con bloque `mcpServers` (Antigravity / Claude Desktop): usar `"command": "npx"`, `"args": ["-y", "@upstash/context7-mcp"]` (en configuraciones globales externas, ej. `~/.config/opencode/opencode.json` o la configuración MCP del IDE, replicar el mismo bloque).
- **Comprobación de conexión y herramienta real**:
  1. Verificar en el cliente MCP (ej. `/mcps` en OpenCode) que `context7` figure conectado con las tools `resolve-library-id` y `query-docs`.
  2. Probar una invocación real sobre `stdio`: enviar `initialize` + `tools/call` (`resolve-library-id` con `libraryName: "react-router"` y luego `query-docs` sobre `/remix-run/react-router`). Evidencia registrada en [mcp-context7-ejecucion.md](docs/skills-mcp/evidencias/mcp-context7-ejecucion.md).
- **Troubleshooting en Windows**: si un entorno restringido o PowerShell bloquea `npx` sin wrapper o hay demora en la primera ejecución, ejecutar primero `npx -y @upstash/context7-mcp --help` en terminal con red para poblar la caché npm, o invocar mediante `cmd /c npx -y @upstash/context7-mcp`. Si el entorno de sandbox bloquea salida HTTP, habilitar red al cliente MCP antes de consultar.

### Skill propia (`validador-escenarios-turnos`) y documentación del TP

- Skill de proyecto ubicada en [SKILL.md](.agents/skills/validador-escenarios-turnos/SKILL.md) e indexada en [.atl/skill-registry.md](.atl/skill-registry.md) + `AGENTS.md` / `CLAUDE.md`.
- Documentación completa del TP: [investigacion.md](docs/skills-mcp/investigacion.md) (Parte 1) y [aplicacion.md](docs/skills-mcp/aplicacion.md) (Parte 2).
