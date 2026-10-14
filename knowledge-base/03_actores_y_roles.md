# 03 — Actores y roles

**Proyecto**: turnos-odontología · **Fecha**: 2026-10-14 · **Fuente**: `discovery/discovery.md` (§2)
Relacionadas: `05_reglas_de_negocio.md` (máquina de estados con actor), `06_funcionalidades.md`, `08_arquitectura_propuesta.md` (JWT/RBAC).

## 1. Roles (3, cerrados)

### R1. Paciente (no autenticado para reservar; identificado por DNI + mail)
- Reserva turno en flujo canónico 3–4 pasos; si el DNI ya existe, se reconoce y se precargan datos **[v1]**.
- Cancela / reprograma sus turnos viendo las reglas de seña antes de confirmar **[v1]**.
- Confirma o cancela desde el propio mail de recordatorio (token firmado de un solo uso / corta vida) **[v1]**.
- Consulta su ficha mínima: datos de contacto + historial de turnos acotado (pasados/futuros, nada clínico) **[v1]**.
- No ve agendas ajenas ni datos de otros pacientes.

### R2. Odontólogo (autenticado JWT)
- Ve **solo su agenda del día** (aislamiento de agenda por odontólogo) **[v1]**.
- Carga y edita **su** disponibilidad: duración estándar, tope/día, pausas, feriados, bloqueos **[v1]**.
- Gestiona cancelaciones y reprogramaciones de **sus** turnos, con historial (actor + fecha) **[v1]**.
- Configura **su** monto del turno y de la seña **[v1]** (decisión cerrada: montos configurables por odontólogo).
- Si el consultorio no tiene recepcionista, absorbe esas funciones sin que el sistema lo trabe **[v1]**.
- No administra usuarios ni configuración global de pagos.

### R3. Admin / Recepcionista (autenticado JWT, rol delegado opcional)
Permisos **explícitos y cerrados** (lista exhaustiva para v1):
1. Ver las agendas del consultorio (todos los odontólogos, solo lectura salvo puntos 2–3) **[v1]**.
2. Cargar/editar disponibilidad de cualquier odontólogo **[v1]**.
3. Gestionar cancelaciones y reprogramaciones de cualquier turno **[v1]**.
4. Operar la bandeja de devoluciones (aprobar/rechazar según política RN-SEÑA; cada acción guarda actor + fecha + monto) **[v1]**.
5. Consultar reportes mínimos y exportaciones CSV/PDF **[v1]**.
6. Ver fichas mínimas de pacientes (contacto + historial de turnos) **[v1]**.

**Prohibido explícitamente para recepcionista [v1]**: administrar usuarios/roles; modificar configuración de pagos (credenciales MP, webhooks); borrar audit trail; ver/emitir comprobantes ARCA **[v2]**.

## 2. Tabla RBAC (matriz exigible en backend, no solo UI)

| Capacidad | Paciente | Odontólogo | Recepcionista/Admin |
|---|---|---|---|
| Reservar turno (flujo público) | ✅ | — | ✅ (por teléfono, a nombre del paciente) |
| Confirmar/cancelar desde el mail (token) | ✅ (propios) | — | — |
| Cancelar/reprogramar turnos | ✅ (propios) | ✅ (propios) | ✅ (todos) |
| Ver agenda del día | — (solo sus turnos) | ✅ (propia) | ✅ (todas) |
| Cargar disponibilidad | — | ✅ (propia) | ✅ (todas) |
| Configurar monto turno/seña | — | ✅ (propios) | ❌ |
| Operar bandeja de devoluciones | — (solo ver estado de las suyas) | ✅ (las de sus turnos) | ✅ |
| Exportar CSV/PDF, reportes mínimos | — | ✅ | ✅ |
| Administrar usuarios/roles | ❌ | ❌ | ❌ (solo super-admin futuro [v2]) |
| Configuración de pagos/MP | ❌ | ❌ | ❌ |
| Comprobante ARCA / OS | — | — | — ([v2]) |

## 3. Rutas públicas (sin JWT) — lista cerrada [v1]

1. `GET /disponibilidad?...` — slots ofrecibles por odontólogo/fecha (solo huecos libres, sin datos de otros pacientes).
2. `POST /reservas` — crear reserva (datos paciente + DNI + slot + pago MP). Rate-limit: sí.
3. `POST /webhooks/mercadopago` — webhook MP (firma + idempotencia, ver `11_pagos_mercadopago.md`).
4. `GET /mail/confirmar?token=…` / `GET /mail/cancelar?token=…` — acciones desde el mail (token firmado, un uso, expiración corta).
5. `GET /mis-turnos?dni=…&token=…` — consulta acotada de turnos propios (token enviado al mail, no DNI solo).
6. Endpoints de precio/trial públicos (precio y trial públicos desde día uno, decisión confirmada).

Todo lo demás exige JWT con `role` + `odontologo_id` (aislamiento de agenda forzado en queries, ver `08_arquitectura_propuesta.md`).
