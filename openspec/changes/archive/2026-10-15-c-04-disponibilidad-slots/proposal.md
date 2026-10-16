# Proposal — c-04-disponibilidad-slots

## Why

Sin disponibilidad por odontólogo no hay nada que ofrecer ni reservar: C-05 (reserva), C-07 (pagos) y C-10 (frontend pública) dependen de un motor de slots confiable. Este change lo construye ahora, desbloqueando el camino crítico C-04 → C-05.

## What Changes

- Modelos `Disponibilidad` (`odontologo_id, dia_semana, hora_inicio, hora_fin, duracion_min, tope_dia, vigente_desde/hasta`) y `Bloqueo` (`odontologo_id, desde, hasta, motivo: pausa|feriado|bloqueo|vacaciones, created_by`) + migración Alembic `002` (cero `create_all`, P3).
- Constraints Postgres de dominio (P6): no-solapamiento de disponibilidades por profesional/día, `CHECK` de rangos horarios y duración positiva, `CHECK` de motivo cerrado en bloqueo.
- CRUD staff de disponibilidad/bloqueos con RBAC backend: odontólogo solo la propia (`scoped_repository` + `require_role("odontologo")`), recepcionista/admin todas (`require_role("recepcionista","admin")`); config `monto_turno/monto_senia` por odontólogo (D1, épica D).
- Motor puro de slots ofrecibles: múltiplos exactos desde `hora_inicio` (RN-DURACION), tope/día (RN-TOPE), resta de bloqueos (RN-PAUSAS), anticipación mínima configurable (RN-ANTICIPACION, default `ANTICIPACION_MIN_HS=24`, env-overridable).
- Endpoint público `GET /disponibilidad?odontologo_id&fecha` — solo huecos libres, sin datos de otros pacientes, con rate-limit (ruta 03 §3.1 ya registrada en `PUBLIC_ROUTES`, P12).
- Tests TDD (U2: feliz / error de negocio / borde) por seam: generación de slots, pausas/feriados, tope, anticipación, aislamiento por profesional, rate-limit público, `extra='forbid'` (P2).

## Capabilities

### New Capabilities

- `disponibilidad-slots`: disponibilidad por odontólogo (CRUD + constraints), motor de slots ofrecibles (RN-DURACION/TOPE/PAUSAS/ANTICIPACION) y endpoint público `GET /disponibilidad` con rate-limit; incluye config de montos por odontólogo (D1).

### Modified Capabilities

- Ninguna. Reutiliza seams de `auth-jwt-rbac` (`require_role()`, `scoped_repository()`, `PUBLIC_ROUTES`) y modelos de `core-models-usuarios-pacientes` (`Odontologo`, `BaseRepository`, `UnitOfWork`) sin cambiar sus requirements.

## Impact

- Añade: `backend/app/domain/disponibilidad/` (schemas, servicio/motor, repositorios), `backend/app/api/disponibilidad.py` (CRUD staff + `GET /disponibilidad` público), modelos `Disponibilidad`/`Bloqueo`, migración `002`, setting `ANTICIPACION_MIN_HS`, rate-limiter público reutilizando `LoginRateLimiter`/patrón fixed-window.
- Modifica: registro de routers en `backend/app/main.py`, `.env.example` (nueva var `ANTICIPACION_MIN_HS=24`), seed dev (disponibilidad L–V + feriado/bloqueo ejemplo ya reservados en C-02).
- No toca: auth/JWT, `core-models` existentes, pagos (C-07), mails (C-09), frontend.
- Colisión con C-06 (propuesta concurrente): ninguna detectada — C-06 trabaja sobre `Paciente`/ficha-consentimiento; C-04 sobre `Disponibilidad`/`Bloqueo`/`Odontologo.montos`. Único punto de contacto potencial: `Odontologo` (C-04 solo añade lectura/escritura de `monto_turno/monto_senia`, sin cambiar su spec). Si C-06 tocara `Odontologo`, coordinar en apply; por ahora se continúa solo con este change.
