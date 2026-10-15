"""Routers por dominio (C-01 health; C-03 auth) + registro de rutas públicas P12.

`PUBLIC_ROUTES`: lista cerrada de `03 §3` — lo único alcanzable sin JWT
(C-04+ monta cada router con su guard; lo no listado exige token válido
no-blacklisteado por construcción: sin router montado no hay ruta abierta).
Excepción infra (no es ruta de dominio): `GET /api/health`, `/docs`, `/openapi.json`.
Rate-limit: cada ruta pública lo lleva (`03 §3`); login ya lo aplica (5/60 s).
"""

PUBLIC_ROUTES: tuple[str, ...] = (
    "GET /disponibilidad",  # 03 §3.1 slots ofrecibles, sin datos ajenos
    "POST /reservas",  # 03 §3.2 crear reserva (rate-limit sí)
    "POST /webhooks/mercadopago",  # 03 §3.3 firma + idempotencia (C-07)
    "GET /mail/*",  # 03 §3.4 confirmar/cancelar (token 1 uso, vida corta; C-09)
    "GET /mis-turnos",  # 03 §3.5 consulta acotada, nunca DNI solo (C-09)
    "GET /precios",  # 03 §3.6 precio y trial públicos (path canónico en C-04+)
)
