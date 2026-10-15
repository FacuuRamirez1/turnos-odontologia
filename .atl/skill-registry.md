# Skill Registry

**Delegator use only.** Any agent that launches sub-agents reads this registry to resolve compact rules, then injects them directly into sub-agent prompts. Sub-agents do NOT read this registry or individual SKILL.md files.

Scope note (project decision): skills live at PROJECT level, not global. Canonical source is `.agents/skills/`; `.opencode/skills/` holds duplicates of the 6 openspec-* workflow skills. `.claude/skills/` is empty.

## Project Skills (project-level)

| Trigger | Skill | Path |
|---------|-------|------|
| Build features or fix bugs test-first, "red-green-refactor", integration tests | tdd | .agents/skills/tdd/SKILL.md |
| Writing, reviewing, or refactoring React/Next.js code; data fetching, bundle optimization, performance | vercel-react-best-practices | .agents/skills/vercel-react-best-practices/SKILL.md |
| BEFORE writing/changing anything in Postgres: tables, columns, schema, migrations, RLS, indexes, triggers, functions, cron/queues, pgvector, EXPLAIN, connection/lock/bloat issues | supabase-postgres-best-practices | .agents/skills/supabase-postgres-best-practices/SKILL.md |
| Building FastAPI backends: REST APIs, async Python, SQLAlchemy, Pydantic, API auth, microservices | python-fastapi-development | .agents/skills/python-fastapi-development/SKILL.md |
| Implementing auth systems, securing APIs, OAuth2/social login, RBAC, sessions, SSO, debugging auth | auth-implementation-patterns | .agents/skills/auth-implementation-patterns/SKILL.md |
| Designing Redis data model, caching objects/sessions, counters, leaderboards, membership sets, key naming review | redis-core | .agents/skills/redis-core/SKILL.md |
| Building new UI or reshaping existing one; aesthetic direction, typography, non-templated visual design | frontend-design | .agents/skills/frontend-design/SKILL.md |
| Integrating Stripe payments, subscriptions, secure checkout, refunds, webhooks (analog for MercadoPago webhook/idempotency — no MP-specific skill exists) | stripe-integration | .agents/skills/stripe-integration/SKILL.md |
| Building EMR/EHR features: encounter workflows, prescriptions, clinical data entry UI, CDSS | healthcare-emr-patterns | .agents/skills/healthcare-emr-patterns/SKILL.md |
| "openspec apply / opsx apply / openspec implement" — implement tasks from an OpenSpec change | openspec-apply-change | .agents/skills/openspec-apply-change/SKILL.md (dup: .opencode/skills/openspec-apply-change/SKILL.md) |
| "openspec archive / opsx archive" — finalize and archive a completed change | openspec-archive-change | .agents/skills/openspec-archive-change/SKILL.md (dup: .opencode/skills/openspec-archive-change/SKILL.md) |
| "openspec explore / opsx explore" — thinking partner before/during a change, no implementation | openspec-explore | .agents/skills/openspec-explore/SKILL.md (dup: .opencode/skills/openspec-explore/SKILL.md) |
| "openspec propose / opsx propose" — new change with proposal + specs + design + tasks in one step | openspec-propose | .agents/skills/openspec-propose/SKILL.md (dup: .opencode/skills/openspec-propose/SKILL.md) |
| "openspec sync / opsx sync" — sync delta specs to main specs without archiving | openspec-sync-specs | .agents/skills/openspec-sync-specs/SKILL.md (dup: .opencode/skills/openspec-sync-specs/SKILL.md) |
| "openspec update change / opsx update" — revise a change's planning artifacts, never edits code | openspec-update-change | .agents/skills/openspec-update-change/SKILL.md (dup: .opencode/skills/openspec-update-change/SKILL.md) |

## Compact Rules

Pre-digested rules per skill. Delegators copy matching blocks into sub-agent prompts as `## Project Standards (auto-resolved)`.

### tdd
- Red before green: write the failing test first, then only enough code to pass it; no speculative features.
- Test behavior through public interfaces (seams), never internals/private methods/side channels.
- Agree seams with user BEFORE writing any test ("What's the public interface, which seams?"); one-liner per seam on what it catches/misses.
- Vertical slices only: one test → one implementation → repeat (tracer bullet); never write all tests first (horizontal slicing).
- Expected values from independent source of truth (literal, worked example, spec) — never recompute the way the code does; no tautological assertions.
- No implementation-coupled tests: no mocking internal collaborators; test must survive refactors.
- Refactoring is NOT part of the red→green loop; it belongs to review stage.
- Name tests in domain language (read GLOSSARY.md if present); respect ADRs in touched area.

### vercel-react-best-practices
- Eliminate waterfalls first (CRITICAL): `Promise.all()` for independent ops; start promises early/await late in API routes; chain per-item nested fetches (`ids.map(id => get(id).then(...))`).
- Check cheap sync conditions BEFORE awaiting flags/remote values; defer `await` into the branch that uses it.
- RSC: parallelize via component composition (sibling async components, not parent-await-then-child); use Suspense boundaries to stream non-critical sections.
- Import directly, avoid barrel files (`lucide-react`, `@mui/*`); `next/dynamic` + `ssr:false` for heavy components; defer analytics/logging past hydration; preload on hover/focus intent.
- Server: `React.cache()` for per-request dedup of DB/auth (not `fetch` — auto-memoized); LRU cache for cross-request; never mutable module-level request state; minimize RSC→client serialized props (pass only used fields).
- Authenticate INSIDE every Server Action (like a public API route); validate input with zod before auth checks.
- Re-renders: derive state during render (no setState-in-effect for props); functional `setState(curr => ...)`; split hooks with independent deps; `useDeferredValue`/`startTransition` for expensive input-driven renders; never define components inside components.
- Conditional render with ternary (`count > 0 ? ... : null`), never `&&` on numeric/falsy values; `content-visibility: auto` for long lists.

### supabase-postgres-best-practices
- Load BEFORE any Postgres work — even one-column changes or single queries; rules live in `references/<prefix>-*.md`, read the matching file.
- Query (CRITICAL): add missing indexes for WHERE/JOIN/ORDER BY; prefer partial indexes for filtered queries; composite indexes ordered by selectivity; covering indexes for index-only scans.
- Connections (CRITICAL): pool (Supavisor/pgbouncer), respect conn limits, short transactions, prepared statements; diagnose exhaustion via pg_stat_activity.
- Security (CRITICAL): RLS on every user-facing table + tests verifying row visibility per tenant/role; never trust client data; least-privilege roles.
- Schema (HIGH): right-sized types (timestamptz, uuid, numeric vs float), NOT NULL + CHECK constraints, FKs with explicit actions.
- Locking: short transactions, `SELECT ... FOR UPDATE SKIP LOCKED` for queues, advisory locks for leader-election, deadlock-safe lock ordering.
- Data access: keyset pagination (not OFFSET) for large lists; batch inserts; upsert with ON CONFLICT; fix N+1 with joins/lateral/batching.
- Diagnose with EXPLAIN ANALYZE + pg_stat_statements; VACUUM/ANALYZE on schedule; pg_restore with correct flags for dumps.

### python-fastapi-development
- Stack: FastAPI + Python 3.11+ + SQLAlchemy 2.0 + Pydantic v2 + PostgreSQL + Alembic + pytest; manage env with uv/poetry + env vars.
- Structure: routers per domain (turnos, disponibilidad, pagos, mails), Pydantic request/response models on every endpoint, SQLAlchemy models + Alembic migrations, session-per-request dependency.
- Async everywhere on I/O paths (DB, Redis, HTTP); never block event loop with sync I/O in async handlers.
- Auth via JWT (short-lived access 15–30 min) + OAuth2 password/bearer scheme; hash with bcrypt/argon2; auth as FastAPI dependencies, enforced server-side.
- Errors: custom exception hierarchy + handlers returning consistent error envelope; request logging + error tracking wired.
- Quality gates: pytest passing (>80% coverage) incl. integration tests with test DB, mypy clean, ruff/black clean, OpenAPI docs complete, versioned API.
- Deploy: Dockerfile + docker-compose (FastAPI+React+PG+Redis parity); never treat scaffolding output as final without env-specific validation.

### auth-implementation-patterns
- Distinguish AuthN (who) from AuthZ (what); enforce both server-side on every request — never client-side-only checks.
- Passwords: always bcrypt/argon2 hash; enforce strength; secure reset tokens with expiry; rate-limit all auth endpoints (brute-force protection).
- Tokens: short-lived access (15–30 min) + rotating refresh; JWT secrets rotated; never store JWT in localStorage (XSS) — httpOnly + Secure + SameSite cookies.
- RBAC: roles (paciente/odontólogo/admin) + resource-ownership checks on every mutation; verify session inside the handler/action, not just middleware/layout.
- OAuth2/OIDC for social/SSO; validate all auth input (email format, password policy); CSRF protection for session-based flows.
- Log security events (logins, failures); MFA where possible; details + worked examples in `references/details.md`.
- Project mapping: this skill backs the C-03 auth-jwt-rbac change family.

### redis-core
- Choose type by ACCESS pattern: String (counters/INCR), Hash (objects with independent field updates), List (queues/recent-N), Set (membership), Sorted Set (rankings), JSON (nested docs), Stream (event log/consumer groups), Vector Set (similarity).
- Never serialize a flat object into a String for field-level updates (fetch+parse+mutate+rewrite anti-pattern) — use Hash.
- Keys: lowercase colon-separated `{entity}:{id}:{attribute}` (e.g. `turno:123:estado`); short but readable; no URLs/long strings as keys (hash digest instead); tenant prefix for multi-tenancy (`tenant:42:...`); one convention per service.
- Project uses: mail reminder queues/retries, MercadoPago webhook idempotency keys, session/short-TTL state.
- Full rationale + Python examples in `references/choose-data-structure.md`; naming cleanup cases in `references/key-naming.md`.

### frontend-design
- Design as studio lead: one opinionated, brief-specific identity — never templated defaults; ground every choice in the subject (dental booking: patients + backoffice agenda).
- Two passes: (1) compact token plan (palette 4–6 named hex, type roles, layout concept + ASCII wireframe, uniqueness principles), (2) review plan against brief for generic-default tells → revise → then code.
- Banned defaults unless brief demands: cream #F4F1EA + serif + terracotta #D97757; near-black + acid accent; broadsheet hairlines; SaaS-card-kit (identical rounded cards + soft shadow + gradient wash); ALL-CAPS eyebrow per heading; `A · B · C` meta strings; `WORD — fragment` labels; `→` on links.
- Typography: 1–2 distinct families, Elements-of-Typographic-Style scale; <80ch lines; never single-word accent coloring as the only hierarchy.
- Motion: one orchestrated moment max; motion must answer user action; respect reduced-motion; responsive + keyboard focus + visible accessibility floor.
- Copy: active voice, sentence case, CTA names the outcome ("Reservar turno"); error/empty states explain what happened + how to fix, never vague apologies.

### stripe-integration
- Prefer Checkout Sessions (hosted/embedded/custom `ui_mode`) over hand-rolled Payment Intents; Setup Intents for saving methods; you compute amount/tax/discount yourself only in bespoke flows.
- Webhooks are source of truth: handle `payment_intent.succeeded/failed`, `subscription.updated/deleted`, `charge.refunded`, `invoice.payment_succeeded`; always verify signatures; idempotent handlers (dedupe by event id).
- Model: Product → Price → Subscription → Invoice per cycle; customer records own methods/metadata/billing details.
- SCA/3DS: test cards `4242…` success / `4000000000000002` decline / `4000002500003155` 3DS / `4000000000009995` insufficient; use `sk_test_*` in tests.
- Project mapping: NO MercadoPago skill exists — reuse this skill's webhook/idempotency/checkout-state-machine patterns for seña/devoluciones (C-07/C-08); amounts/currency/MP SDK differ.
- Worked patterns in `references/details.md`; never expose secret keys client-side; confirm payment status server-side before mutating turno state.

### healthcare-emr-patterns
- Safety gate: every decision answered against "Could this harm a patient?" — drug interactions MUST alert, abnormal labs MUST flag, critical vitals MUST escalate, no silent passes.
- Critical interactions BLOCK prescribing by default; override requires documented reason in audit trail; major interactions require acknowledgment; all alerts logged.
- Encounter flow is single-page vertical (header sticky: demographics/allergies/meds → complaint → HPI → exam → vitals → diagnosis ICD-10/SNOMED → meds → orders → plan → sign/lock/print); no tab-fragmented clinical workflow.
- Signed/locked encounters are immutable — addendum-only linked records; audit captures who/when + addenda.
- Alerts are non-dismissable modals/panels, never auto-dismissing toasts; red-flag templates trigger visible blocking alerts.
- Accessibility: WCAG AA 4.5:1, 44×44px targets, full keyboard nav, never color-only indicators (pair with text/icon), labeled fields for screen readers.
- Anti-patterns: clinical data in localStorage, `any` types for clinical structs, editable signed encounters, toasts for critical alerts.
- Project mapping: dental-adjacent (agenda/turnos, not full EMR); reuse safety/audit/addendum/accessibility patterns for patient data + turno state history.

### openspec-apply-change
- Implements tasks from a named change; announce "Using change: <name>" + how to override; infer/auto-select single active change else prompt via `openspec list --json`.
- Store selection sticky: if a store is named, `openspec store list --json` then `--store <id>` on all spec/change commands.
- Project check: `openspec list --json` must show root before any write; `root: null` + auto-selected → answer normally without OpenSpec; explicit request → ask (init/store/continue-without) and never create root as side effect.
- Work through tasks sequentially with validation; never edit code outside change scope.

### openspec-archive-change
- Finalize + archive a completed change; same store-selection and project-check rules as apply-change.
- Verify implementation complete and specs synced before archiving; run `openspec archive` (with `--store <id>` when sticky); report archived name.
- Never archive with open tasks or unsynced deltas unless user explicitly confirms.

### openspec-explore
- Thinking partner only — NEVER write code or implement; may read/search/investigate + run read-only commands freely.
- May create/update OpenSpec change artifacts (proposal/design/specs) only within confirmed scope: name artifacts + planned action, ask direct yes/no, wait for separate-message confirmation.
- Explicit "capture as new change" request counts as confirmation for that scaffold only; new scope needs new confirmation.
- If asked to implement, decline explore-mode implementation and point to `/openspec-propose` → apply workflow.

### openspec-propose
- Planning ONLY: create change + proposal.md + `specs/<capability>/spec.md` (delta, not main) + design.md + tasks.md in one step; do NOT edit project code; stop after artifacts.
- Preserve full `<capability-path>` (e.g. `identity/user-auth`); follow existing spec organization for new capabilities.
- Same store-selection + project-check rules; implementation starts only on a NEW explicit request via apply workflow.

### openspec-sync-specs
- Agent-driven merge: read delta specs, edit main specs intelligently (e.g. add a scenario without copying whole requirement); never blind-copy.
- Preserve full `<capability-path>` when resolving main spec; same store-selection + project-check rules.
- Syncs without archiving; verify with status/validate after merge.

### openspec-update-change
- Revise EXISTING planning artifacts, keep them coherent; NEVER edits code; never creates missing artifacts (status names the next one).
- Same store-selection + project-check + input/change-selection rules as other openspec skills.
- Do not confuse with `openspec update` CLI (refreshes generated files) — if user means the CLI, run that instead.

## Project Conventions

| File | Path | Notes |
|------|------|-------|
| CHANGES.md | CHANGES.md | Canonical change index + dependency tree (C-01…C-13); read before any `/opsx:propose`; corte P2=b |
| KB README | knowledge-base/README.md | KB entry point; 12 files |
| KB visión | knowledge-base/01_vision_y_objetivos.md | Problem, goals, scope |
| KB general | knowledge-base/02_descripcion_general.md | System overview |
| KB actores | knowledge-base/03_actores_y_roles.md | paciente/odontólogo/admin roles |
| KB datos | knowledge-base/04_modelo_de_datos.md | Domain model (turnos, disponibilidad, pagos) |
| KB reglas | knowledge-base/05_reglas_de_negocio.md | No-overlap, anticipación, seña, auto-release |
| KB funciones | knowledge-base/06_funcionalidades.md | Required vs optional scope |
| KB flujos | knowledge-base/07_flujos_principales.md | 3–4-step booking, cancel/reschedule |
| KB arquitectura | knowledge-base/08_arquitectura_propuesta.md | FastAPI + React + PostgreSQL + Redis + Docker |
| KB decisiones | knowledge-base/09_decisiones_y_supuestos.md | D1/D2 cuts, stack calls |
| KB abiertas | knowledge-base/10_preguntas_abiertas.md | Open questions |
| KB pagos | knowledge-base/11_pagos_mercadopago.md | MercadoPago seña/devoluciones spec |
| OpenSpec root | openspec/ | specs + changes + archive live here |

> NOTE — conventions pending re-index: `CLAUDE.md` / `AGENTS.md` do NOT exist yet (generated later by agent-instruction). Re-run this registry after that step to index hard rules + referenced paths. No `agents.md`, `.cursorrules`, `GEMINI.md`, or `copilot-instructions.md` found at project root.

Read the convention files listed above for project-specific patterns and rules. All referenced paths have been extracted — no need to read index files to discover more.

## Deduplication & Gaps

- Canonical skill source: `.agents/skills/` (15 dirs). `.opencode/skills/` duplicates the 6 openspec-* skills — delegators must use the `.agents/skills/` path.
- `.claude/skills/` is empty; no global directories were scanned (project decision).
- Gap (known): no MercadoPago-specific skill; `stripe-integration` is the webhook/idempotency analog for C-07/C-08.
- Gap (known): no docker-compose skill installed at registry time; `CHANGES.md`/KB assume Docker parity — revisit if a docker skill is added.
- `state.skills.installed` lists the 9 coding skills; all 9 verified present in `.agents/skills/` + 6 openspec-* workflow skills = 15 total.
