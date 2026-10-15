# Tasks — c-03-auth-jwt-rbac

> TDD obligatorio (U2): cada grupo implementa RED → GREEN → TRIANGULATE con 3 escenarios (feliz / error de negocio / borde). Escribir el test primero, verlo fallar, luego el mínimo código que lo pasa. P2: todo schema Pydantic v2 con `extra='forbid'`. P5: secretos solo por env vars.

## 1. Deps + settings JWT (base)

- [x] 1.1 Agregar `PyJWT` + `bcrypt` a `backend/requirements.txt` y verificar `pip install` resuelve sin conflictos
- [x] 1.2 Extender `Settings` con `JWT_ACCESS_MIN=15`, `JWT_REFRESH_DIAS=7`, `JWT_ACTION_MIN=15` (+ `COOKIE_SECURE` derivado) y verificar `test_settings`-style: defaults presentes, `JWT_SECRET` vacío en producción falla al arrancar (P5)
- [x] 1.3 Actualizar `.env.example` con las 3 TTL vars documentadas y verificar que `test_env_contract` sigue pasando

## 2. Hashing + JWT core (RED primero)

- [x] 2.1 RED: tests de `passwords` — hash verifica (feliz), wrong-password falla (negocio), hash de email inexistente con dummy-verify sin early-return (borde); verificar que fallan sin implementación
- [x] 2.2 GREEN: implementar `app/core/security/passwords.py` (bcrypt cost 12, verify constant-time) y verificar tests 2.1 en verde
- [x] 2.3 RED: tests de `jwt` — access válido decodifica claims `sub/rol/jti/type` (feliz), token manipulado 401 (negocio), `exp` en frontera con 30 s leeway acepta / fuera rechaza (borde); verificar que fallan
- [x] 2.4 GREEN: implementar `app/core/security/jwt.py` (`create_access/refresh/action`, `decode_and_validate(expected_type)`, HS256, `JWT_SECRET` solo env) y verificar tests 2.3 en verde

## 3. Blacklist + rate-limit Redis (RED primero)

- [x] 3.1 RED: tests de blacklist — `jti` listado es rechazado (feliz-negado), TTL expira y deja de listar (borde), Redis caído usa fallback en memoria con warning (negocio); verificar que fallan
- [x] 3.2 GREEN: implementar `app/infra/redis/blacklist.py` (keys `auth:blacklist:<jti>`, fallback dict misma interfaz) y verificar tests 3.1 en verde
- [x] 3.3 RED: tests de rate-limit — 5 intentos OK + 6to 429 (feliz/límite), par IP+email distinto no afectado (borde), ventana 60 s resetea contador (negocio); verificar que fallan
- [x] 3.4 GREEN: implementar `app/infra/redis/rate_limit.py` (fixed window 60 s por hash IP+email) y verificar tests 3.3 en verde

## 4. Guard require_role + matriz RBAC (RED primero, P8)

- [x] 4.1 RED: tests del guard — rol permitido autoriza y devuelve identidad `sub/rol/odontologo_id` (feliz), rol no permitido 403 (negocio), token odontólogo sin vínculo no autoriza scope (borde); verificar que fallan
- [x] 4.2 GREEN: implementar `app/core/security/dependencies.py` (`require_role(*roles)`, identidad validada, `odontologo_id` desde claims) y verificar tests 4.1 en verde
- [x] 4.3 RED: tests matriz `03 §2` — recepcionista: 6 permisos sí autorizan (feliz ×6), 4 prohibiciones (usuarios/roles, config MP, borrar audit, ARCA) responden 403 (negocio ×4), UI no confiada: endpoint negado aunque el test simule llamada directa (borde); verificar que fallan
- [x] 4.4 GREEN: cablear matriz sobre endpoints de prueba/seed y verificar tests 4.3 en verde; documentar la matriz en `design.md`-referencia dentro del docstring del guard

## 5. Endpoints login/refresh/logout/me (RED primero)

- [x] 5.1 RED: tests `POST /api/auth/login` — credenciales seed OK 200 + cookie `refresh_token` HttpOnly/Secure/SameSite=Lax (feliz), credencial mala 401 sin distinguir causa (negocio), campo extra → 422 `extra='forbid'` (borde, P2); verificar que fallan
- [x] 5.2 GREEN: implementar `POST /api/auth/login` (email case-insensitive vía `lower()`, rate-limit 5/60 s, schemas request/response P2) y verificar tests 5.1 en verde
- [x] 5.3 RED: tests `POST /api/auth/refresh` + `POST /api/auth/logout` — rotación emite par nuevo e invalida anterior (feliz), reuso de refresh rotado 401 (negocio), logout invalida access en uso posterior 401 (borde); verificar que fallan
- [x] 5.4 GREEN: implementar refresh con rotación atómica (check-and-set `jti`) + logout con blacklist de ambos `jti`, y verificar tests 5.3 en verde
- [x] 5.5 RED: tests `GET /api/auth/me` — token válido 200 con `sub/rol/email/odontologo_id?` (feliz), token expirado 401 envelope estándar (negocio), token blacklisteado 401 (borde); verificar que fallan
- [x] 5.6 GREEN: implementar `GET /api/auth/me` y registrar router `app/api/auth.py` en `main.py` bajo `/api`, y verificar tests 5.5 + `test_health` existente en verde

## 6. Tokens de acción por mail JWT separados (RED primero, base C-09)

- [x] 6.1 RED: tests action tokens — emisión + validación un uso OK (feliz), segundo uso rechazado por hash consumido (negocio), access token presentado como mail-token rechazado por `type` (borde); verificar que fallan
- [x] 6.2 GREEN: implementar `app/core/security/action_tokens.py` (`type='action'`, TTL `JWT_ACTION_MIN`, consumed-hash en Redis `auth:action_consumed:<sha256>`, nunca raw) y verificar tests 6.1 en verde
- [x] 6.3 RED: test expiración action token — expirado rechaza con error explícito (borde temporal); verificar que falla y luego pasa sin código nuevo o con ajuste mínimo (TRIANGULATE)

## 7. Aislamiento odontologo_id E2E + rutas públicas cerradas (P8, P12)

- [x] 7.1 RED: tests aislamiento E2E — odontólogo A no recibe filas de B aunque el endpoint no filtre (feliz-aislado, usa `BaseRepository` C-02), repositorio scopeado sin `odontologo_id` levanta `ValueError` (borde fail-closed); verificar que fallan
- [x] 7.2 GREEN: cablear `odontologo_id` de la identidad a repositorios en endpoints staff y verificar tests 7.1 en verde (RN-AISLAMIENTO)
- [x] 7.3 RED: tests P12 — exactamente las 6 rutas públicas de `03 §3` responden sin JWT y cada una tiene rate-limit (feliz ×6), cualquier otra ruta sin token 401 (negocio), ráfaga sobre pública → 429 (borde); verificar que fallan
- [x] 7.4 GREEN: cerrar rutas (todo lo no listado exige JWT válido no-blacklisteado) y verificar tests 7.3 en verde

## 8. Integración, calidad y verificación final

- [x] 8.1 Pasar suite completa `pytest` en verde con cobertura ≥ 80 % en módulos nuevos y verificar `ruff` + `mypy` limpios
- [x] 8.2 Verificar `GET /api/health` y docs OpenAPI (`/docs` lista los 4 endpoints auth con request/response models) sin regresiones
- [x] 8.3 Verificar cero `create_all` en runtime y cero secretos hardcodeados (`grep` por `create_all` y por literales de secreto) — P3/P5
- [x] 8.4 Ejecutar `openspec validate --change c-03-auth-jwt-rbac` y verificar que pasa sin errores

## Workflow follow-up

- Proponer el change para revisión (`/opsx:propose` ya ejecutado — estos son sus artefactos).
- Al aprobar, implementar con `/opsx:apply c-03-auth-jwt-rbac` y archivar con `/opsx:archive c-03-auth-jwt-rbac`, luego tick `[x]` C-03 en CHANGES.md (GATE 3 → desbloquea C-04 y C-06).
