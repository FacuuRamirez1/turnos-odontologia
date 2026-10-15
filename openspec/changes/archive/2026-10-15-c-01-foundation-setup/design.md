# Design — c-01-foundation-setup

## Context

Repo sin código previo (solo `knowledge-base/`, `CHANGES.md`, `discovery/`). Stack obligatorio: FastAPI + SQLAlchemy + Alembic + PostgreSQL + Redis + Docker Compose; frontend React + TS estricto + Vite (ver `02 §2`, `08 §2/§4–§5`). Ver motivación en `proposal.md — Why`. Este change solo deja la base ejecutable; el dominio (C-02 → C-13) llega después.

## Goals / Non-Goals

**Goals:**

- Monorepo ejecutable con `docker compose up` → `GET /api/health` 200.
- Contrato de env vars cerrado y valores resueltos ya pineados (`RECORDATORIO_VENTANA_HS=24`, `RESERVA_TTL_MIN=15`, flags v2 en `false`).
- CI paralela backend/frontend desde el día uno.

**Non-Goals:**

- Ningún modelo de dominio, migración de datos, auth, ni lógica de turnos/pagos/mails (C-02 → C-09).
- Ningún seed con datos (seeds en C-02/C-13 con DNI ficticios, P11).
- Ninguna integración real con MercadoPago o SMTP (solo vars + servicios locales como MailHog).

## Decisions

- **Monolito modular por dominios desde el scaffolding** (directorios `domain/{turnos,disponibilidad,pagos,devoluciones,notificaciones,reportes}` vacíos con `__init__.py`): evita reestructuraciones en C-04 → C-09. Alternativa (empezar plano y refactorizar en C-04): descartada, el costo de mover imports a mitad del camino crítico es mayor.
- **FastAPI + Pydantic v2 `extra='forbid'` + settings centralizados** (`backend/app/core/settings.py` vía `pydantic-settings`): cumple P2/P5 desde el primer endpoint. Alternativa (settings dispersos por módulo): descartada, dispersa secretos.
- **Alembic inicializado sin tablas en este change** (solo `env.py` + `alembic.ini` cableado a `DATABASE_URL`): cumple P3 (cero `create_all`); la migración 001 llega en C-02. Alternativa (crear tablas aquí): descartada, el schema pertenece a C-02 con governance CRÍTICO.
- **PostgreSQL + `pgcrypto` en el servicio `db`, Redis y MailHog separados, `worker` como servicio propio**: refleja `08 §5` (workers fuera del request path, mail local en dev). Alternativa (worker dentro de `api`): descartada, ocultaría fallos de colas que C-09 necesita visibles.
- **Vite + React + TS `strict` + `noImplicitAny` + lint `no-explicit-any`** (P1) y auth store solo como esqueleto tipado: el flujo real de reserva llega en C-10/C-11. Alternativa (relajar TS al inicio): descartada, P1 es contrato.
- **CI con dos jobs paralelos (backend: ruff + mypy + pytest; frontend: tsc + eslint + build)**: falla rápido y en paralelo. Alternativa (un solo job secuencial): descartada, más lenta y mezcla señales.
- **Credenciales MP de prueba ficticias solo vía env vars** (titular ficticio, ej. "Clínica Odontológica Ficticia S.R.L.", P5/P11): se declaran las vars pero no se consumen hasta C-07; la conciliación se diseña en C-07, aquí solo se deja el cableado de configuración.
- **Defaults ya resueltos pineados en `.env.example`**: anticipación mínima 24 h (documentada para C-04/C-05), ventana 24 h, TTL 15 min, reintentos mail 3 con backoff (C-09). Decisiones informativas de otros changes (seña $65.000 ARS, umbral devolución $40.000, mantener seña original en reprogramación) NO se implementan aquí; quedan registradas en sus changes (C-02/C-05/C-08).

## Risks / Trade-offs

- [Riesgo] Estructura sobredimensionada para un solo endpoint → Mitigación: directorios esqueleto con `__init__.py` y README de una línea cada uno; tasks prohíben añadir lógica de dominio.
- [Riesgo] Divergencia dev/CI (versiones de Python/Node) → Mitigación: versiones pineadas en `Dockerfile`, `compose` y workflow; CI usa las mismas imágenes.
- [Riesgo] Puertos locales ocupados (5432/6379/8025) → Mitigación: documentados y sobreescribibles por `.env`; healthchecks con `start_period` generoso.
- [Trade-off] Un solo spec (`foundation-setup`) para todo el scaffolding: aceptado porque la capacidad es cohesiva (base ejecutable) y evita fragmentar la raíz del sistema.

## Migration Plan

- Despliegue: solo dev local (`docker compose up --build`); sin migración de datos (base vacía); rollback = `docker compose down -v` (volumen `pgdata` sin datos de valor aún).
- Verificación post-apply: `GET /api/health` → 200; `alembic current` sin error; CI en verde.

## Open Questions

- Reserva telefónica por recepcionista (criterio propuesto: datos completos + consentimiento con fecha en el momento): supuesto a validar en C-05, NO bloquea este change.
- Ninguna otra pregunta abierta afecta a este change (las Alta de `10_preguntas_abiertas.md` ya están resueltas para C-01 vía las decisiones listadas arriba).
