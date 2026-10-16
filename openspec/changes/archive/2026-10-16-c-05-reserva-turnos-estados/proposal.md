# Proposal — c-05-reserva-turnos-estados

## Why

Sin reserva no hay sistema: la disponibilidad de C-04 ofrece slots pero nada los ocupa, y los pagos de C-07 no tienen sobre qué cobrar la seña. Este change convierte slots ofrecibles en turnos con identidad (máquina de estados + historial auditable + constraints anti-choque en DB), desbloqueando el camino crítico C-05 → C-07.

## What Changes

- Modelos `Turno` (`paciente_id, odontologo_id, inicio, fin, estado, canal, idempotency_key` única, `version` lock optimista) y `TurnoHistorial` append-only (`estado_anterior/nuevo, actor_tipo, actor_id, fecha, motivo`) + migración Alembic `003` (cero `create_all`, P3).
- Constraints Postgres de dominio (P6): `UNIQUE (odontologo_id, inicio)` (RN-DOBLE), `EXCLUDE USING gist` anti-solape por profesional sobre rango `tstzrange(inicio, fin)` (RN-SOLAPE), `CHECK (fin > inicio)` y `CHECK (inicio > now())` (RN-PASADO); revoke `UPDATE/DELETE` del rol app sobre `turno_historial` (P9, base preparada en C-02).
- `POST /reservas` público con rate-limit (ruta 03 §3.2, P12): DNI normalizado → reconocimiento de paciente existente (A2, reutiliza seam C-06) o alta implícita exigiendo consentimiento (422 `CONSENTIMIENTO_REQUERIDO` sin persistir nada, P11); valida slot contra motor C-04 + RN-PASADO/DOBLE/SOLAPE/ANTICIPACION; crea `turno(creado)` + pre-reserva con TTL `RESERVA_TTL_MIN` (A5, RN-LIBERACION); `Idempotency-Key` header con `UNIQUE(idempotency_key)` → replay seguro (P4).
- Job de expiración de pre-reservas: `creado` vencido (sin pago aprobado) → `cancelado` (motivo `ttl_expirado`, actor `sistema`) + slot liberado; base que C-07 conectará al webhook MP (`aprobado → confirmado`, `rechazado → cancelado`).
- Máquina de estados `05 §4` cerrada con actor obligatorio por transición (RN-ESTADOS): `creado→confirmado` (sistema/webhook MP), `confirmado→cancelado/reprogramado` (paciente dueño/odontólogo propio/recepcionista), `confirmado→atendido/no_show` (odontólogo propio/recepcionista, `no_show` solo posterior a `fin`), `cancelado→devuelto` (sistema tras devolución ejecutada, C-08); cada transición escribe `turno_historial` en el mismo commit; trigger/check DB rechaza transiciones sin actor.
- Cancelación/reprogramación (B1–B3, F2–F3): endpoint de cotización previa que muestra la regla de seña aplicable 100/60/0 **antes** de confirmar (B2, cálculo desde anticipación); liberación del hueco en el mismo commit (RN-LIBERACION); reprogramación atómica (turno origen → `reprogramado` + nuevo turno `confirmado` heredando el `pago`, sin nuevo cobro; diferencia de monto → se mantiene seña original por defecto, abierta Q3).
- Endpoints staff: agenda del día aislada por profesional (C1, `odontologo_id` forzado en repositorio, P8), `confirmado→atendido/no_show`, reserva por teléfono a nombre del paciente (recepcionista, datos mínimos DNI+mail+consentimiento), `GET /mis-turnos?dni&token` (token mail de 1 uso y vida corta, nunca DNI solo, P12).
- Tests TDD (U2: feliz / error de negocio / borde) por seam: concurrencia (no doble-reserva bajo carrera), transiciones válidas/inválidas, TTL pre-reserva, aislamiento por profesional, consentimiento bloqueante, `extra='forbid'` (P2).

## Capabilities

### New Capabilities

- `reserva-turnos-estados`: reserva de turnos con máquina de estados cerrada + historial append-only con actor obligatorio, constraints anti-choque en DB, `POST /reservas` público con pre-reserva TTL e idempotencia, cancelación/reprogramación con regla de seña visible pre-confirmación, agenda del día staff aislada y `GET /mis-turnos` con token.

### Modified Capabilities

- `disponibilidad-slots`: el endpoint público `GET /disponibilidad` y el motor ahora restan los slots ocupados por turnos activos (`creado` no expirado + `confirmado` + `reprogramado` origen ya liberado excluido); C-04 dejó este seam explícitamente abierto ("booked input is empty in C-04 … is the seam C-05 will wire"). Ningún otro requirement de `disponibilidad-slots` cambia.

## Impact

- Añade: `backend/app/domain/turnos/` (schemas, servicio/máquina de estados, repositorios, job expiración TTL), `backend/app/api/reservas.py` (público) + `backend/app/api/agenda.py` (staff) + `GET /mis-turnos`, modelos `Turno`/`TurnoHistorial`, migración `003`, rate-limiter público (mismo patrón fixed-window C-04).
- Modifica: motor/endpoint `GET /disponibilidad` (resta de ocupados vía seam C-05), registro de routers en `backend/app/main.py`, `.env.example` (documenta `RESERVA_TTL_MIN=15` ya existente en C-01; añade `ANTICIPACION_CANCEL_HS` si se introduce como setting separado), seed dev (10 turnos en todos los estados — se completa en C-13, aquí solo turnos mínimos para tests de aislamiento).
- No toca: auth/JWT (reutiliza `require_role()`, `scoped_repository()`, mail-action tokens C-03), ficha `Paciente` (consume contrato C-06 sin cambiarlo), pagos MP (C-07 consume `creado→confirmado`), mails (C-09), frontend (C-10/C-11), tablas v2 apagadas (P13 intacto: cero escrituras en `lista_espera`, sin sobre-turnos RN-SOBRETURNO).
