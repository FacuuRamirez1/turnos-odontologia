# Proposal — c-01-foundation-setup

## Why

No existe código ni infraestructura: sin scaffolding del monorepo, ningún change posterior (C-02 → C-13) puede construirse ni verificarse. Este change crea la base ejecutable (API mínima, Compose, CI) sobre la que todo el sistema v1 se apoya.

## What Changes

- Scaffolding monorepo: `backend/app/{api,core,domain/{turnos,disponibilidad,pagos,devoluciones,notificaciones,reportes},infra/{db,redis,mp,smtp},workers,tests}` + `frontend/src/{pages/{reserva,agenda,bandeja,reportes},components,api,auth}`.
- Backend FastAPI mínimo con `GET /api/health` (único endpoint de este change) + settings centralizados por env vars + Alembic inicializado (cero `create_all` en runtime).
- Frontend Vite + React + TypeScript estricto (sin `any`, componentes PascalCase) con scaffolding base (auth store esqueleto, cliente API).
- `docker-compose.yml`: servicios `api, web, db (PostgreSQL + pgcrypto), redis, mailhog, worker` con healthchecks y volumen `pgdata`.
- `.env.example` (raíz + cada sub-proyecto) con la lista mínima de `08 §4`: `DATABASE_URL, REDIS_URL, JWT_SECRET, MP_ACCESS_TOKEN, MP_WEBHOOK_SECRET, SMTP_*, MAIL_FROM, RECORDATORIO_VENTANA_HS=24, RESERVA_TTL_MIN=15, FRONTEND_URL, WHATSAPP_ENABLED=false, ARCA_ENABLED=false`.
- CI GitHub Actions con jobs paralelos backend + frontend; secretos solo vía env vars, nunca hardcodeados.
- Valores por defecto resueltos y registrados: anticipación mínima 24 h (consumida en C-04/C-05), `RECORDATORIO_VENTANA_HS=24`, `RESERVA_TTL_MIN=15`, reintentos de mail 3 con backoff vía workers Redis (consumidos en C-09).

## Capabilities

### New Capabilities

- `foundation-setup`: base ejecutable del proyecto — contrato del endpoint de salud, contrato de variables de entorno, topología de servicios Compose y verificación continua. Es la capacidad raíz que los changes C-02 → C-13 extienden sin modificar.

### Modified Capabilities

- Ninguna (no existen specs previas; `openspec list --specs` vacío).

## Impact

- Afecta: raíz del repo (estructura nueva `backend/`, `frontend/`, `docker-compose.yml`, `.env.example`, `.github/workflows/`). Nada existente se modifica (repo sin código previo).
- Dependencias desbloqueadas: C-02 (modelos + migraciones) y toda la cadena C-03 → C-13.
- Riesgo de alcance: inventar dominio (turnos/pagos/mails) en este change — se mitiga dejando solo esqueleto de directorios y el health endpoint.
