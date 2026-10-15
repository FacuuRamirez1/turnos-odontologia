# Spec Delta — auth-jwt-rbac

## Purpose

Verifica quién es cada miembro del staff y qué puede hacer: login con JWT rotativo, autorización por rol exigible en backend con aislamiento por odontólogo, y tokens de acción por mail como base para C-09.

## ADDED Requirements

### Requirement: Login emite access corto y refresh rotativo

The system SHALL authenticate staff by email (case-insensitive) plus password and, on success, return a short-lived signed access token and a rotating refresh token.

#### Scenario: Login correcto

- **WHEN** valid credentials for an active user are posted to `POST /api/auth/login`
- **THEN** the system responds 200 with an access token and a refresh token, both signed JWTs

#### Scenario: Credenciales inválidas no distinguen causa

- **WHEN** an unknown email or a wrong password is posted to `POST /api/auth/login`
- **THEN** the system responds 401 without revealing whether the email exists

#### Scenario: Usuario inactivo no puede loguearse

- **WHEN** credentials for a user with `activo = false` (or soft-deleted) are posted
- **THEN** the system responds 401 and issues no tokens

#### Scenario: Schemas rechazan campos no declarados

- **WHEN** a login request includes an undeclared field
- **THEN** the system responds 422 and issues no tokens (P2 `extra='forbid'`)

### Requirement: Rate-limit en login por IP y email

The system SHALL rate-limit `POST /api/auth/login` to 5 attempts per 60 seconds per IP+email pair, enforced server-side in Redis.

#### Scenario: Sexto intento dentro de la ventana es bloqueado

- **WHEN** 5 failed logins occur within 60 seconds for the same IP+email pair
- **THEN** the 6th attempt responds 429 even with correct credentials

#### Scenario: Par IP+email distinto no es afectado

- **WHEN** one IP+email pair is blocked
- **THEN** a different email from the same IP can still attempt login

### Requirement: Refresh rota con blacklist del token anterior

The system SHALL accept a valid refresh token once: it invalidates the presented token (blacklist by `jti`) and issues a new access + refresh pair.

#### Scenario: Rotación feliz emite par nuevo

- **WHEN** a valid unused refresh token is posted to `POST /api/auth/refresh`
- **THEN** the system responds 200 with a new access token and a new refresh token

#### Scenario: Reuso de refresh rotado es rechazado

- **WHEN** an already-rotated (blacklisted) refresh token is posted again
- **THEN** the system responds 401 and issues no tokens

#### Scenario: Refresh expirado o manipulado es rechazado

- **WHEN** an expired or signature-tampered refresh token is posted
- **THEN** the system responds 401 and issues no tokens

### Requirement: Logout invalida tokens vigentes

The system SHALL invalidate the caller's access token (blacklist by `jti` until its expiry) and refresh token on `POST /api/auth/logout`.

#### Scenario: Access usado tras logout es rechazado

- **WHEN** a logged-out access token is used on an authenticated endpoint
- **THEN** the system responds 401

#### Scenario: Logout exige autenticación

- **WHEN** `POST /api/auth/logout` is called without a valid access token
- **THEN** the system responds 401

### Requirement: Me devuelve identidad del portador

The system SHALL expose `GET /api/auth/me` returning the bearer's `sub` (user id), `rol`, email and `odontologo_id` when linked.

#### Scenario: Token válido devuelve identidad

- **WHEN** `GET /api/auth/me` is called with a valid non-blacklisted access token
- **THEN** the system responds 200 with the caller's identity fields

#### Scenario: Token expirado es rechazado

- **WHEN** an expired access token is used on `GET /api/auth/me`
- **THEN** the system responds 401 with the standard error envelope

### Requirement: Claims con rol cerrado y vínculo odontólogo

Access tokens SHALL carry `sub`, `rol` (`odontologo | recepcionista | admin`) and `odontologo_id` only for the odontologo role; a token with `rol='odontologo'` and no linked profile SHALL authorize nothing.

#### Scenario: Odontólogo sin vínculo no autoriza

- **WHEN** a request bears an odontologo-role token with no linked `odontologo_id`
- **THEN** the system denies it as if unauthenticated for odontologo-scoped actions

#### Scenario: Recepcionista no porta odontologo_id

- **WHEN** a recepcionista logs in
- **THEN** the access token carries no `odontologo_id` claim yet authorizes recepcionista actions

### Requirement: Passwords con hash moderno y salt

The system SHALL store only salted modern hashes (bcrypt/argon2, never plaintext) and verify logins in constant time; every seeded dev user SHALL authenticate with its documented dev password.

#### Scenario: Seed staff hace login

- **WHEN** a seeded dev user logs in with its documented dev password
- **THEN** the system responds 200 with a token pair

#### Scenario: Timing no distingue usuario inexistente

- **WHEN** login is attempted with an unknown email
- **THEN** the system still performs a hash verification (no early return) before responding 401

### Requirement: RBAC exigible en backend según matriz 03 §2

Every staff endpoint SHALL enforce the role matrix server-side via a role guard (`require_role`): odontólogo operates only own agenda, recepcionista holds exactly the 6 allowed permissions and is denied the 4 prohibitions, regardless of what the UI shows.

#### Scenario: Odontólogo accede a agenda propia

- **WHEN** an odontologo token accesses own-agenda actions
- **THEN** the system authorizes them

#### Scenario: Rol incorrecto es denegado en backend

- **WHEN** a token with an unauthorized role calls a guarded endpoint
- **THEN** the system responds 403 even if the frontend would have hidden the action

#### Scenario: Prohibiciones de recepcionista negadas en backend

- **WHEN** a recepcionista token attempts user/role administration, MP payment config, audit-trail deletion or ARCA vouchers
- **THEN** the system responds 403 for each of the 4 prohibitions

### Requirement: Aislamiento odontologo_id forzado en repositorio

Odontologo-scoped reads SHALL always filter by the caller's `odontologo_id`, enforced in the repository layer so it cannot be omitted by endpoint code (RN-AISLAMIENTO, P8).

#### Scenario: Odontólogo no ve agenda ajena

- **WHEN** an odontologo queries a scoped collection
- **THEN** zero rows from other professionals are returned even if endpoint code passes no filter

#### Scenario: Scope faltante falla cerrado

- **WHEN** a scoped repository is constructed without an `odontologo_id`
- **THEN** construction raises instead of returning unfiltered data

### Requirement: Refresh en cookie HttpOnly segura

The system SHALL transport the refresh token in an `HttpOnly`, `Secure`, `SameSite=Lax` cookie, never in response bodies stored by clients or in `localStorage`.

#### Scenario: Login setea cookie segura

- **WHEN** login succeeds
- **THEN** the response sets the refresh cookie with `HttpOnly`, `Secure` and `SameSite=Lax` flags

### Requirement: Tokens de acción por mail como JWT separados

The system SHALL issue mail-action tokens as a distinct JWT type (short-lived, single-use with consumed-hash recorded server-side) for confirm/cancel and `mis-turnos`, never accepting session access tokens in their place (base for C-09, P12).

#### Scenario: Token de acción de un uso no se reusa

- **WHEN** a consumed mail-action token is presented a second time
- **THEN** the system rejects it

#### Scenario: Access token no sirve como token de mail

- **WHEN** a session access token is presented to a mail-action route
- **THEN** the system rejects it (token types are not interchangeable)

#### Scenario: Token de mail expirado es rechazado

- **WHEN** an expired mail-action token is presented
- **THEN** the system rejects it with an explicit expiry error

### Requirement: Secretos solo por variables de entorno

The system SHALL read `JWT_SECRET` (and any signing secret) exclusively from environment variables with no hardcoded fallback that can sign valid tokens; behavior is identical across dev, test and prod except for secret values and TTLs.

#### Scenario: Sin secreto válido no se firman tokens

- **WHEN** the JWT secret is missing or empty in production mode
- **THEN** startup fails instead of signing with a default (P5)

### Requirement: Rutas públicas cerradas con rate-limit

Only the 6 public routes listed in `03 §3` SHALL be reachable without a JWT, each with rate-limiting; every other route SHALL require a valid non-blacklisted token (P12).

#### Scenario: Ruta staff sin token es rechazada

- **WHEN** any non-public route is called without a token
- **THEN** the system responds 401

#### Scenario: Ráfaga pública es limitada

- **WHEN** a public route receives a burst above its configured threshold
- **THEN** the system responds 429
