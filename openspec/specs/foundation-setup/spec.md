# foundation-setup

## Purpose

Establishes the executable project foundation every later change builds on: a verifiable health contract, a closed environment-variable contract, and a reproducible local/CI topology.

## Requirements

### Requirement: Health endpoint contract

The system SHALL expose `GET /api/health` returning HTTP 200 with a JSON body containing service status, and it SHALL require no authentication.

#### Scenario: Health check succeeds

- **WHEN** a client calls `GET /api/health` without credentials
- **THEN** the system responds HTTP 200 with a JSON body indicating healthy status

#### Scenario: Health check shape is stable

- **WHEN** a client parses the `GET /api/health` response
- **THEN** the body contains a status field deserializable without authentication or extra headers

### Requirement: Environment variable contract

The system SHALL declare every required setting in versioned `.env.example` files, and it SHALL read secrets only from environment variables, never from hardcoded values.

#### Scenario: Required vars are documented

- **WHEN** a developer copies `.env.example` to `.env`
- **THEN** all of `DATABASE_URL, REDIS_URL, JWT_SECRET, MP_ACCESS_TOKEN, MP_WEBHOOK_SECRET, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, MAIL_FROM, RECORDATORIO_VENTANA_HS, RESERVA_TTL_MIN, FRONTEND_URL, WHATSAPP_ENABLED, ARCA_ENABLED` have a documented entry

#### Scenario: Resolved defaults are pinned

- **WHEN** a developer reads the default `.env.example`
- **THEN** `RECORDATORIO_VENTANA_HS=24`, `RESERVA_TTL_MIN=15`, `WHATSAPP_ENABLED=false` and `ARCA_ENABLED=false` are present

#### Scenario: No hardcoded secrets

- **WHEN** the codebase is searched for secret values (JWT secret, MP tokens, SMTP passwords)
- **THEN** no secret literal exists outside test fixtures and every access resolves via environment

### Requirement: Local service topology

The system SHALL provide a `docker-compose.yml` with services `api, web, db (PostgreSQL + pgcrypto), redis, mailhog, worker`, each with a healthcheck, and a persistent `pgdata` volume.

#### Scenario: Full stack boots

- **WHEN** a developer runs `docker compose up -d` then `GET /api/health`
- **THEN** the endpoint answers HTTP 200 once the `api` service reports healthy

#### Scenario: Unhealthy dependency is visible

- **WHEN** the `db` or `redis` service fails its healthcheck
- **THEN** `docker compose ps` reports that service as unhealthy instead of silently serving traffic

### Requirement: Continuous verification

The system SHALL run a CI pipeline with parallel backend and frontend jobs that typecheck, lint and test every push and pull request.

#### Scenario: CI gates a change

- **WHEN** a pull request is opened
- **THEN** backend and frontend jobs both execute and the merge is blocked unless both pass

### Requirement: Strict typing baselines

The system SHALL enforce Pydantic v2 `extra='forbid'` on every backend model and strict TypeScript (no `any`, PascalCase components) on every frontend file from day one.

#### Scenario: Undeclared field is rejected

- **WHEN** a request payload contains a field not declared in its Pydantic model
- **THEN** the API rejects it with HTTP 422

#### Scenario: Frontend forbids any

- **WHEN** frontend CI runs the typecheck
- **THEN** any usage of TypeScript `any` fails the build
