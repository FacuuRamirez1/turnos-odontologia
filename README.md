# Turnos Odontología — base ejecutable (C-01)

Scaffolding del monorepo + infraestructura base. Dominio real desde C-02.

## Puertos (sobreescribibles por `.env`)

| Servicio | Var | Default | URL |
|---|---|---|---|
| api (FastAPI) | `API_PORT` | 8000 | http://localhost:8000/api/health |
| web (Vite dev) | `WEB_PORT` | 5173 | http://localhost:5173 |
| db (PostgreSQL) | `PG_PORT` | 5432 | — |
| redis | `REDIS_PORT` | 6379 | — |
| mailhog SMTP | `MAILHOG_SMTP_PORT` | 1025 | — |
| mailhog UI | `MAILHOG_HTTP_PORT` | 8025 | http://localhost:8025 |

Copiar `.env.example` → `.env` y ajustar. `docker-compose.yml` lee `${VAR:-default}`.

## Arranque

```bash
cp .env.example .env
docker compose up -d --build
curl http://localhost:8000/api/health  # {"status":"ok","service":"turnos-odontologia"}
```

Rollback dev (base vacía): `docker compose down -v`.

## Verificación C-01

```bash
# backend (12+ tests)
cd backend && python -m pytest app/tests/ -v
# alembic (requiere db healthy)
cd backend && python -m alembic current
# frontend
cd frontend && npm install && npm run typecheck
# compose
docker compose config
```

## Notas

- Seña default $65.000 ARS y umbral devolución $40.000: informativos (C-02/C-08),
  sin lógica de pagos en C-01.
- `WHATSAPP_ENABLED=false`, `ARCA_ENABLED=false` (P13, v2 apagado).
- Mails solo vía workers Redis desde `MAIL_FROM` (P14, real en C-09).
