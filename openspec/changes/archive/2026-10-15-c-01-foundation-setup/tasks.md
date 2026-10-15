# Tasks — c-01-foundation-setup

## 1. Esqueleto del monorepo

- [x] 1.1 Crear árbol `backend/app/{api,core,domain/{turnos,disponibilidad,pagos,devoluciones,notificaciones,reportes},infra/{db,redis,mp,smtp},workers,tests}` y `frontend/src/{pages/{reserva,agenda,bandeja,reportes},components,api,auth}` con `__init__.py`/índices esqueleto y verificar con listado de directorios que la estructura coincide con `08 §2`
- [x] 1.2 Añadir `backend/requirements.txt` (o `pyproject.toml`) con FastAPI, SQLAlchemy 2.0, Alembic, pydantic v2 + pydantic-settings, pytest/httpx y verificar con instalación en limpio que resuelve sin conflictos
- [x] 1.3 Scaffold Vite + React + TS estricto (`strict`, `noImplicitAny`, lint contra `no-explicit-any`, componentes PascalCase) con auth store esqueleto tipado y verificar con `tsc --noEmit` en verde

## 2. Backend mínimo verificable (TDD)

- [x] 2.1 Escribir test rojo de `GET /api/health` con 3 escenarios (200 sin auth / cuerpo con status / 404 en ruta inexistente) y verificar que falla antes de implementar
- [x] 2.2 Implementar FastAPI mínima + `core/settings.py` (solo env vars, sin secretos hardcodeados) + modelos Pydantic con `extra='forbid'` y verificar con `pytest` en verde
- [x] 2.3 Añadir manejador de errores con envelope consistente + logging de request y verificar con test de error 404 que el envelope es estable

## 3. Base de datos y migraciones (vacías)

- [x] 3.1 Inicializar Alembic (`alembic.ini` + `env.py` cableado a `DATABASE_URL`, sin tablas aún) y verificar con `alembic current` sin errores contra Postgres local
- [x] 3.2 Declarar `infra/db/base.py` + sesión por request (sin `create_all` en runtime) y verificar con grep que no existe ninguna llamada a `create_all` en `backend/`

## 4. Contrato de entorno (P5/P13)

- [x] 4.1 Crear `.env.example` raíz + por sub-proyecto con `DATABASE_URL, REDIS_URL, JWT_SECRET, MP_ACCESS_TOKEN, MP_WEBHOOK_SECRET, SMTP_HOST/PORT/USER/PASS, MAIL_FROM, RECORDATORIO_VENTANA_HS=24, RESERVA_TTL_MIN=15, FRONTEND_URL, WHATSAPP_ENABLED=false, ARCA_ENABLED=false` (titular MP ficticio solo en docs, nunca datos reales) y verificar con script que toda var usada en `settings.py` está documentada
- [x] 4.2 Añadir test que carga `settings` con flags v2 y verificar que `WHATSAPP_ENABLED` y `ARCA_ENABLED` son `false` por defecto

## 5. Docker Compose + worker esqueleto

- [x] 5.1 Escribir `docker-compose.yml` (`api, web, db` con `pgcrypto`, `redis, mailhog, worker`, healthchecks, volumen `pgdata`) y verificar con `docker compose config` válido
- [x] 5.2 Añadir `Dockerfile` api + `worker` esqueleto (loop/cola sin lógica de dominio, fuera del request path según `08 §1`) y verificar con `docker compose up -d` que todos los servicios reportan healthy
- [x] 5.3 Verificar E2E local con `GET /api/health` → 200 una vez `api` está healthy y documentar puertos/sobreescritura por `.env` en README breve

## 6. CI paralela

- [x] 6.1 Crear workflow GitHub Actions con jobs paralelos backend (ruff + mypy + pytest) y frontend (tsc + eslint + build) y verificar con `act -n` o revisión de sintaxis del workflow que ambos jobs están definidos
- [x] 6.2 Verificar en el primer push que ambos jobs corren en paralelo y que un fallo en cualquiera bloquea el merge (verificado: commits `677a316`+`3b68bec` pusheados a `origin/main`, CI run 38770457136 en verde backend+frontend)

## 7. Verificación de cierre del change

- [x] 7.1 Correr `openspec validate --change "c-01-foundation-setup"` y verificar que proposal + specs + design + tasks pasan sin errores
- [x] 7.2 Verificar reglas duras con checklist explícito (U1 sin commits, P5 sin secretos, P11 datos ficticios, P13 v2 apagado, P14 mail solo vía workers) y dejar el resultado anotado para el reviewer

## Workflow follow-up

- Archivar el change con `/opsx:archive c-01-foundation-setup` una vez revisado y marcar `[x]` C-01 en CHANGES.md.
- El implementador (apply) aplicará RED → GREEN → TRIANGULATE con 3 escenarios por test según U2.

