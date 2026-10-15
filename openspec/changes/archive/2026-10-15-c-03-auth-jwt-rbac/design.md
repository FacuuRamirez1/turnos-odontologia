# Design — c-03-auth-jwt-rbac

## Context

See proposal.md (Why) for motivation. Current state observed in repo:

- C-02 archived: `Usuario` persists `email` (lower-unique index), `password_hash` (CHECK ≥ 60 chars), closed `rol`, nullable `odontologo_id` without FK (canonical link is `Odontologo.user_id → usuario.id`); `BaseRepository` forces `odontologo_id` fail-closed; migration `001` only.
- C-01: `Settings` from env vars (P5) with `JWT_SECRET` present but **no** TTL vars yet; `ErrorEnvelope` pattern; router-per-domain (`app/api/health.py`); `main.py` wires routers under `/api`.
- `backend/requirements.txt` has **no** JWT or password-hashing library yet — this change adds them (see Decisions).
- Stale `__pycache__` under `core/security/`, `api/` and `infra/redis/` references auth modules with no committed `.py` source and `git status` clean: prior uncommitted attempt, fully reverted — this design starts from zero and does not reuse it.

## Goals / Non-Goals

**Goals:**

- Login/refresh/logout/me working against the C-02 `Usuario` table with zero schema change (no Alembic migration in this change).
- RBAC enforced server-side so C-04+ can decorate endpoints with the same guard.
- Mail-action token base that C-09 consumes without redesign.

**Non-Goals:**

- Password reset / change flows (no requirement; defer to a later change if needed).
- Frontend login UI (C-10/C-11 consume these endpoints).
- Turno state machine actor stamping (P9 full enforcement lands in C-05/C-07; here we only establish identity + role claims those later changes record).

## Decisions

1. **JWT library: `PyJWT` (over `python-jose`)** — minimal, maintained, HS256 only; avoids jose's abandoned-status and crypto surface. All tokens HS256 with `JWT_SECRET`.
2. **Password hashing: `bcrypt` direct (over passlib)** — passlib is in maintenance mode; `bcrypt` package + `secrets.compare_digest`-style constant-time verify. Cost factor 12. Dummy-hash verify on unknown email to equalize timing.
3. **Token model: `jti` + `type` claims on every token** — `type ∈ {access, refresh, action}`; a single `decode_and_validate(expected_type=...)` choke point rejects cross-type reuse (access-as-mail-token can never happen). `jti = uuid4` enables blacklist without storing token contents.
4. **Blacklist + rate-limit in Redis with in-memory fallback** — `redis` client already a dependency; keys `auth:blacklist:<jti>` (TTL = token remainder) and `auth:ratelimit:<ip>:<email-hash>` (fixed window 60 s, counter + expiry). Fallback dict with same interface when Redis is unreachable (tests/dev without Redis); fallback is fail-open for availability but logs a warning — production Compose always provides Redis.
5. **Refresh transport: HttpOnly cookie + rotation on every use** — cookie `refresh_token`, `Secure` (relaxed only for local non-TLS dev via setting), `SameSite=Lax`, `Path=/api/auth`. Rotation invalidates the presented `jti` before issuing the new pair (atomic check-and-set under Redis to survive concurrent reuse races: loser gets 401).
6. **Mail-action tokens: separate `aud`/type, 15-min TTL, single-use via consumed-hash table kept in memory/Redis** — persisted consumed-hash set (`auth:action_consumed:<sha256>`) so C-09 can later move it to a `RecordatorioMail.token_accion` column without changing the validation contract. Never stored raw.
7. **Settings extension (P5): `JWT_ACCESS_MIN` (default 15), `JWT_REFRESH_DIAS` (default 7), `JWT_ACTION_MIN` (default 15)** — new vars with safe defaults; missing/empty `JWT_SECRET` in production fails startup (no silent default signing).
8. **RBAC guard shape: `require_role(*roles)` FastAPI dependency returning the validated identity** — endpoint declares `Depends(require_role("odontologo", "recepcionista"))`; identity object carries `sub/rol/odontologo_id`; repositories keep receiving `odontologo_id` from the identity (P8 — UI never trusted). The 6-public-routes list (P12) is enforced by simply not guarding those routers; a test asserts the closed list.
9. **No migration (P3)** — C-03 needs no schema change: `Usuario` already has everything; consumed action hashes live in Redis until C-09 models them. Zero `create_all` stays.

Alternatives considered: session-cookie auth (rejected — stateless JWT already decided in `08 §3`); refresh reuse-detection with family rotation (rejected as over-engineering — single-use blacklist gives equivalent security with simpler reasoning); storing blacklist in Postgres (rejected — TTL expiry is a natural Redis fit, and C-02 audit tables stay untouched).

## Risks / Trade-offs

- [Risk] Fixed-window rate-limit allows 10 requests at window edges → Mitigation: 5/60 s threshold is low enough that edge-burst doubles stay harmless; sliding window deferred unless tests show abuse.
- [Risk] In-memory fallback hides Redis outages → Mitigation: every fallback use logs a warning; health endpoint reports Redis reachability; Compose dev always runs Redis.
- [Risk] Clock skew rejects valid tokens at expiry boundary → Mitigation: 30 s `leeway` on `exp` validation, documented in tests.
- [Risk] `Secure` cookie breaks local HTTP dev → Mitigation: `COOKIE_SECURE` follows `FRONTEND_URL` scheme (http → false locally, true otherwise), explicit in `.env.example`.
- [Trade-off] No refresh-family reuse detection means a stolen refresh is usable once before rotation invalidates it → accepted: short access TTL (15 min) bounds the window; full device-session management is out of v1 scope.

## Migration Plan

No data migration. Deploy: add `PyJWT` + `bcrypt` to `requirements.txt`, extend `.env.example` with the three TTL vars, wire `app/api/auth.py` router in `main.py`. Rollback: remove router + deps; no persisted state to revert (blacklist keys expire on their own).

## Open Questions

None blocking. TTL defaults (15 min access / 7 d refresh / 15 min action) follow `08 §3` conventions and are env-overridable; C-09 may tune action TTL when mail flows are implemented.
