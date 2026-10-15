# Proposal — c-03-auth-jwt-rbac

## Why

Sin autenticación no hay agenda aislada ni staff operativo: C-02 dejó `Usuario.password_hash` y roles cerrados persistidos pero sin ningún mecanismo de login, y todo lo que sigue en el roadmap (C-04 → C-13) depende de identidad verificada con RBAC exigible en backend (GATE 2, desbloquea TODO lo demás).

## What Changes

- `POST /api/auth/login` — credenciales (email + password) → JWT access corto + refresh rotativo; rate-limit 5 intentos/60 s por par IP+email.
- `POST /api/auth/refresh` — rotación: el refresh presentado se invalida (blacklist) y se emite un par nuevo; refresh transportado en cookie HttpOnly (`Secure`, `SameSite=Lax`).
- `POST /api/auth/logout` — invalida access (blacklist por `jti`) y refresh vigentes.
- `GET /api/auth/me` — identidad del portador (sub, rol, odontologo_id?).
- Claims JWT: `sub` (user id), `rol` (`odontologo | recepcionista | admin`), `odontologo_id?` (solo rol odontólogo vinculado); `password_hash` con algoritmo moderno + salt (bcrypt/argon2).
- Guard `require_role(*roles)` + matriz RBAC de `03 §2` enforced en cada endpoint staff (backend, nunca solo UI — P8), con tests por rol incluyendo las 4 prohibiciones de recepcionista.
- Tokens de acción por mail como JWT separados (tipo distinto, corta vida, un solo uso con hash consumido en DB) — base que C-09 usa para confirmar/cancelar desde el mail (F4.3).
- Env vars nuevas: `JWT_ACCESS_MIN`, `JWT_REFRESH_DIAS` (secret ya existe como `JWT_SECRET` desde C-01; P5 — nada hardcodeado).

## Capabilities

### New Capabilities

- `auth-jwt-rbac`: autenticación JWT (login/refresh/logout/me), autorización RBAC exigible en backend con aislamiento `odontologo_id`, rate-limit de login, blacklist de tokens y tokens de acción por mail como JWT separados.

### Modified Capabilities

- Ninguna (C-02 persiste identidad; este change agrega el comportamiento de autenticación/autorización sin cambiar sus requirements).

## Impact

- **Backend**: nuevo router `app/api/auth.py`, módulo `app/core/security/` (jwt, passwords, dependencies/`require_role`, action_tokens), blacklist + rate-limit en `app/infra/redis/` (Redis con fallback en memoria para tests), settings extendidos, error envelope existente reutilizado.
- **APIs**: 4 endpoints nuevos bajo `/api/auth/*`; ningún endpoint existente cambia (solo `GET /api/health` existe).
- **Dependencias**: requiere C-02 archivado (modelo `Usuario`, `BaseRepository`, migración 001); desbloquea C-04 y C-06 (GATE 3).
- **Frontend**: sin cambios en este change (el auth store de C-01 consume estos endpoints en C-10/C-11).
- **Seguridad**: cierra P8 (RBAC backend) y prepara P10 (webhook server-to-server en C-07 reutiliza el guard) y P12 (solo las 6 rutas públicas de `03 §3`, todas con rate-limit).
