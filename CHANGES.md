# CHANGES — Secuencia de Implementación

> Índice canónico de todos los changes del proyecto **turnos-odontología** (sistema web de turnos odontológicos, Argentina, single-sede v1).
> Cada change es atómico: un agente puede implementarlo en una sesión (~4-6 horas).
> **Leer este archivo antes de ejecutar cualquier `/opsx:propose`.**
> Corte de alcance: **P2=b (v1 completo junto)** — reserva + agenda + seña real MP + mail se construyen juntos (D1); el recorte cae sobre reportes/UX, nunca sobre pagos/auditoría (D2).

---

## Cómo usar este documento

1. Identificar el change a implementar (verificar que sus dependencias están en `openspec/changes/archive/`).
2. Leer los docs de la knowledge-base indicados en "Leer antes".
3. Ejecutar `/opsx:propose <nombre-del-change>`.
4. Al terminar el change, archivarlo con `/opsx:archive <nombre-del-change>`.
5. Marcar el checkbox `[x]` en este archivo.

---

## Árbol de dependencias

```
C-01 foundation-setup
  └── C-02 core-models-usuarios-pacientes
        └── C-03 auth-jwt-rbac                    ← desbloquea TODO lo demás
              │
              ├── C-04 disponibilidad-slots
              │     └── C-05 reserva-turnos-estados
              │           │
              │           ├── C-07 pagos-mp-checkout-webhook
              │           │     ├── C-08 devoluciones-comprobantes-conciliacion
              │           │     │     └── C-11 frontend-agenda-backoffice ──╮
              │           │     ├── C-09 mails-recordatorios ───────────────╮
              │           │     ├── C-10 frontend-reserva-publica   ← paralelos ║
              │           │     │                                            ║
              │           │     └── C-12 reportes-exportaciones ──────────────╜
              │           │                                           │
              │           └───────────────────────────────────────────┘
              │                         └── C-13 hardening-cumplimiento-cierre (+ C-09, + C-11)
              │
              └── C-06 ficha-paciente-consentimiento  ← paralelo con C-04/C-05
```

### Paralelismo por fase

> Cada "gate" es un punto de sincronización. Los changes dentro de un grupo pueden ejecutarse en paralelo.

```
GATE 0: ninguna
  → C-01 (solo)

GATE 1: C-01 ✓
  → C-02 (solo)

GATE 2: C-02 ✓
  → C-03 (solo)

GATE 3: C-03 ✓                     ← PRIMER FORK (2 paralelos)
  → C-04 disponibilidad-slots       [Agente A]
  → C-06 ficha-paciente            [Agente B]

GATE 4: C-04 ✓
  → C-05 reserva-turnos-estados     [Agente A]

GATE 5: C-05 ✓
  → C-07 pagos-mp-checkout-webhook [Agente A]

GATE 6: C-07 ✓                     ← SEGUNDO FORK (4 paralelos)
  → C-08 devoluciones-comprobantes [Agente A]
  → C-09 mails-recordatorios       [Agente B]
  → C-10 frontend-reserva-publica  [Agente C]
  → C-12 reportes-exportaciones    [Agente A — si C-08 ✓]

GATE 7: C-08 ✓
  → C-11 frontend-agenda-backoffice [Agente C]

GATE 8: C-09 + C-11 + C-12 ✓
  → C-13 hardening-cierre          [Agente A]
```

### Camino crítico (9 changes — mínimo irreducible)

```
C-01 → C-02 → C-03 → C-04 → C-05 → C-07 → C-08 → C-11 → C-13
```

### Plan óptimo con 3 agentes

```
Paso │ Agente A (Backend Core)      │ Agente B (Backend Aux)       │ Agente C (Frontend)
─────┼──────────────────────────────┼──────────────────────────────┼─────────────────────────
  1  │ C-01 foundation-setup        │ —                            │ —
  2  │ C-02 core-models             │ —                            │ —
  3  │ C-03 auth-jwt-rbac           │ —                            │ —
  4  │ C-04 disponibilidad-slots    │ C-06 ficha-paciente          │ —
  5  │ C-05 reserva-turnos-estados  │ —                            │ —
  6  │ C-07 pagos-mp-checkout       │ —                            │ —
  7  │ C-08 devoluciones-comprob.   │ C-09 mails-recordatorios     │ C-10 frontend-reserva
  8  │ C-12 reportes-exportaciones  │ —                            │ C-11 frontend-backoffice
  9  │ C-13 hardening-cierre        │ —                            │ —
```

---

## FASE 0 — Cimientos

### [C-01] `foundation-setup`
- **Estado**: `[x]` completado
- **Scope**: Scaffolding completo del monorepo + infraestructura base
  - Estructura `backend/app/{api,core,domain/{turnos,disponibilidad,pagos,devoluciones,notificaciones,reportes},infra/{db,redis,mp,smtp},workers,tests}` + `frontend/src/{pages/{reserva,agenda,bandeja,reportes},components,api,auth}`
  - `backend/`: FastAPI app mínima con `GET /api/health`, Alembic inicializado, `shared/` con settings, logger, db, exceptions
  - `frontend/`: Vite + React + TypeScript scaffolding, auth store base, `.env.example` en cada sub-proyecto
  - `docker-compose.yml`: servicios `api, web, db (PostgreSQL + pgcrypto), redis, mailhog, worker` con healthchecks y volúmenes pgdata
  - `.env.example` con lista mínima de `08 §4` (`DATABASE_URL, REDIS_URL, JWT_SECRET, MP_ACCESS_TOKEN, MP_WEBHOOK_SECRET, SMTP_*, MAIL_FROM, RECORDATORIO_VENTANA_HS, RESERVA_TTL_MIN, FRONTEND_URL, WHATSAPP_ENABLED=false, ARCA_ENABLED=false`)
  - CI GitHub Actions: jobs paralelos backend + frontend; secretos solo via env vars
- **Dependencias**: ninguna
- **Governance**: BAJO
- **Leer antes**:
  - `knowledge-base/01_vision_y_objetivos.md` §3 (alcance v1)
  - `knowledge-base/02_descripcion_general.md` §2 (stack obligatorio)
  - `knowledge-base/08_arquitectura_propuesta.md` §2 (estructura) + §4–§5 (env vars, Compose)

---

### [C-02] `core-models-usuarios-pacientes`
- **Estado**: `[x]` completado
- **Scope**: Modelos base + migraciones iniciales + seed mínimo + tablas v2 apagadas
  - Modelos: `Usuario` (`email` único, `password_hash`, `rol`, `odontologo_id` nullable, `activo`), `Odontologo` (`user_id`, `monto_turno`, `monto_senia`, `activo`), `Paciente` (`dni` UNIQUE, `consentimiento_datos` bool + fecha)
  - `AuditMixin` (`is_active, created_at, updated_at, deleted_at`), `BaseRepository[T]` con filtro forzado `odontologo_id`, `UnitOfWork`
  - Rol DB de app sin UPDATE/DELETE sobre tablas append-only (prepara RN-AUDIT; se aplica en C-05/C-07)
  - Tablas **[v2] modeladas apagadas**: `lista_espera`, `notificacion_whatsapp` (creadas, sin escrituras en v1)
  - Migración 001: tablas core + v2 apagadas
  - Seed dev según `04 §5`: 2 odontólogos (L–V 9–17, 30 min, tope 14/día, montos distintos), 1 recepcionista + 1 admin, 5 pacientes DNI ficticios, feriado + bloqueo ejemplo
- **Dependencias**: C-01
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §1–§2 (principios, entidades) + §5 (seed)
  - `knowledge-base/03_actores_y_roles.md` §1 (3 roles cerrados)
  - `knowledge-base/08_arquitectura_propuesta.md` §1 (patrones: repositorios, audit trail)
  - `knowledge-base/09_decisiones_y_supuestos.md` D4, D8, D13 (enfoque B, single-sede, pago/comprobante separados)

---

## FASE 1 — Autenticación

### [C-03] `auth-jwt-rbac`
- **Estado**: `[x]` completado
- **Scope**: Sistema completo de autenticación JWT con RBAC exigible en backend
  - `POST /api/auth/login` — JWT access corto + refresh rotativo, rate limiting 5/60s por IP+email
  - `POST /api/auth/refresh` — rotación con blacklist del anterior; `POST /api/auth/logout` — blacklist; `GET /api/auth/me`
  - Claims: `sub, rol, odontologo_id?`; `password_hash` con algoritmo moderno + salt
  - Decorador/guard `require_role()` + matriz RBAC de `03 §2` enforced en cada endpoint + tests por rol
  - Refresh en cookie HttpOnly (secure, samesite=lax); tokens de acción por mail como JWT separados (base, se usan en C-09)
  - Tests: login correcto, token expirado, rate limit, refresh rotation, aislamiento `odontologo_id`
- **Dependencias**: C-02
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/03_actores_y_roles.md` §1–§2 (roles, matriz RBAC)
  - `knowledge-base/08_arquitectura_propuesta.md` §3 (seguridad JWT)
  - `knowledge-base/05_reglas_de_negocio.md` §2 RN-AISLAMIENTO
  - `knowledge-base/07_flujos_principales.md` F4.3 (tokens de acción por mail)

---

## FASE 2 — Dominio de turnos

> C-04 y C-06 pueden proponerse en paralelo. C-04 debe archivarse antes de C-05.

### [C-04] `disponibilidad-slots`
- **Estado**: `[x]` completado
- **Scope**: Disponibilidad por odontólogo + motor de slots ofrecibles (épica C2)
  - Modelos: `Disponibilidad` (`odontologo_id, dia_semana, hora_inicio, hora_fin, duracion_min, tope_dia, vigente_desde/hasta`), `Bloqueo` (`desde, hasta, motivo: pausa|feriado|bloqueo|vacaciones, created_by`)
  - Migración 002: tablas disponibilidad + bloqueo
  - CRUD disponibilidad/bloqueos: odontólogo solo la propia, recepcionista todas (RBAC `03 §2`); config de `monto_turno/monto_senia` por odontólogo (D1, épica D1)
  - Motor de slots: múltiplos exactos desde `hora_inicio` (RN-DURACION), tope/día (RN-TOPE), resta de bloqueos (RN-PAUSAS), anticipación mínima configurable (RN-ANTICIPACION)
  - Endpoint público `GET /disponibilidad?odontologo_id&fecha` — solo huecos libres, sin datos de otros pacientes, con rate-limit (ruta pública `03 §3`)
  - Tests: generación de slots, pausas/feriados, tope, anticipación, aislamiento por profesional
- **Dependencias**: C-03
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §2 (disponibilidad, bloqueo)
  - `knowledge-base/05_reglas_de_negocio.md` §1 (RN-DURACION/TOPE/PAUSAS/ANTICIPACION/LIBERACION)
  - `knowledge-base/06_funcionalidades.md` §Épica C + §Épica D D1
  - `knowledge-base/03_actores_y_roles.md` §2–§3 (quién carga disponibilidad, rutas públicas)

---

### [C-05] `reserva-turnos-estados`
- **Estado**: `[ ]` pendiente
- **Scope**: Reserva con máquina de estados + constraints anti-choque + cancelación/reprogramación (épicas A1–A3, A5, B, C1, C3)
  - Modelos: `Turno` (`paciente_id, odontologo_id, inicio, fin, estado, canal, idempotency_key` única, `version` lock optimista), `TurnoHistorial` append-only (`estado_anterior/nuevo, actor_tipo, actor_id, fecha, motivo`)
  - Constraints DB: `UNIQUE (odontologo_id, inicio)` (RN-DOBLE), `EXCLUDE USING gist` anti-solape por profesional (RN-SOLAPE), `CHECK (inicio > now())` (RN-PASADO); revoke UPDATE/DELETE rol app sobre historial
  - `POST /reservas` público (rate-limit): DNI → reconocimiento paciente existente (A2), crea `turno(creado)` + pre-reserva slot con TTL `RESERVA_TTL_MIN` (A5, RN-LIBERACION); expiración → `cancelado` + slot libre
  - Máquina de estados `05 §4` con actor obligatorio por transición (trigger/check RN-ESTADOS): `creado→confirmado`, `confirmado→cancelado/reprogramado/atendido/no_show`, `cancelado→devuelto`
  - Cancelación/reprogramación: muestra regla de seña 100/60/0 **antes** de confirmar (B2); liberación en el mismo commit; reprogramación crea nuevo `confirmado` heredando `pago` (diferencia de monto → abierta Q3, mantener seña original por defecto)
  - Endpoints staff: agenda del día aislada por profesional (C1), `confirmado→atendido/no_show`, `GET /mis-turnos?dni&token`, reserva por teléfono a nombre del paciente (recepcionista)
  - Tests: concurrencia (no doble-reserva), transiciones válidas/inválidas, TTL pre-reserva, aislamiento
- **Dependencias**: C-04
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/05_reglas_de_negocio.md` §2 (constraints) + §4 (máquina de estados)
  - `knowledge-base/07_flujos_principales.md` F1 (reserva E2E) + F2–F3 (cancelación, reprogramación)
  - `knowledge-base/04_modelo_de_datos.md` §2 (turno, turno_historial) + §4 (constraints)
  - `knowledge-base/06_funcionalidades.md` §Épicas A, B, C
  - `knowledge-base/10_preguntas_abiertas.md` §1.3 (diferencia de monto) + §3.7 (defaults anticipación/TTL)

---

### [C-06] `ficha-paciente-consentimiento`
- **Estado**: `[x]` completado
- **Scope**: Ficha mínima de paciente + consentimiento + historial acotado (épica F1)
  - Endpoints: CRUD ficha mínima (contacto, DNI, consentimiento), `GET /pacientes?dni=` reconocimiento con precarga (A2), historial de turnos acotado pasados/futuros sin nada clínico
  - RN-CONSENTIMIENTO enforced: sin consentimiento registrado no se persiste ficha (error explícito en `POST /reservas` y en alta manual)
  - RBAC: odontólogo/recepcionista ven fichas (contacto + historial); paciente solo la propia vía token mail; exportación solo roles autorizados (se usa en C-12)
  - Tests: bloqueo sin consentimiento, reconocimiento por DNI, visibilidad acotada por rol
- **Dependencias**: C-03
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/03_actores_y_roles.md` §1 R1/R3 + §2 (matriz ficha)
  - `knowledge-base/05_reglas_de_negocio.md` §6 RN-CONSENTIMIENTO
  - `knowledge-base/06_funcionalidades.md` §Épica F F1 + §Épica A A2
  - `knowledge-base/04_modelo_de_datos.md` §2 (paciente)

---

## FASE 3 — Pagos (MercadoPago)

### [C-07] `pagos-mp-checkout-webhook`
- **Estado**: `[ ]` pendiente
- **Scope**: Seña real vía MercadoPago: checkout + webhook idempotente + conciliación (épica D base, F1/F5)
  - Modelos: `Pago` (separado del turno, D13) con `mp_payment_id` único, `mp_preference_id`, estados `pendiente|aprobado|rechazado|...`, `idempotency_key` única; `EventoPago` append-only sin UPDATE/DELETE
  - Migración 003: tablas pago + evento_pago
  - Checkout: reserva crea `turno(creado)` + `pago(pendiente)` + preferencia MP por monto de seña del odontólogo; **nunca** confirmar por callback frontend, solo webhook server-to-server
  - `POST /webhooks/mercadopago`: valida firma (`MP_WEBHOOK_SECRET`) → persiste `webhook_recibido` con payload crudo → procesa por `mp_payment_id` con idempotencia (replay seguro): `aprobado` → turno `confirmado`; `rechazado` → turno `cancelado` + aviso
  - Outbox/escritura atómica turno+pago+evento antes de llamar a MP (nunca cobrar sin rastro local)
  - Job diario conciliación: local vs. API MP por `mp_payment_id`; discrepancias → evento `conciliado` + alerta en bandeja
  - Abiertas Q1/Q2 (monto default, credenciales/titular MP) → defaults configurables por env/DB, documentados
  - Tests: webhook válido/inválido (firma), replay idempotente, expiración pre-reserva, conciliación con discrepancia
- **Dependencias**: C-05
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/11_pagos_mercadopago.md` §1–§3 (checkout, webhooks, idempotencia) + §6–§7 (conciliación, audit)
  - `knowledge-base/07_flujos_principales.md` F1.3–F1.5 + F5
  - `knowledge-base/05_reglas_de_negocio.md` §3 RN-SENIA-PAGO
  - `knowledge-base/04_modelo_de_datos.md` §1.1 (pago separado) + §2 (pago, evento_pago)
  - `knowledge-base/10_preguntas_abiertas.md` §1.1–1.2 (monto default, credenciales MP)

---

### [C-08] `devoluciones-comprobantes-conciliacion`
- **Estado**: `[ ]` pendiente
- **Scope**: Bandeja de devoluciones + recibos internos + trazabilidad navegable (épicas D2–D4, F2)
  - Modelos: `Devolucion` (`pago_id, turno_id, monto, porcentaje 100|60|0, motivo, estado pendiente|aprobada|rechazada|ejecutada, aprobada_por/at, mp_refund_id`); `Comprobante` separado (D13, `tipo=recibo_interno`, campos ARCA `cae` columnados apagados)
  - Migración 004: tablas devolucion + comprobante
  - Cálculo 100/60/0 (RN-SENIA-*) registrado en `devolucion.porcentaje`; ejecución contra API MP con `idempotency_key`, guarda `mp_refund_id`; reintentos consultan antes de re-ejecutar
  - Bandeja: aprobar/rechazar/ejecutar con actor+fecha+monto (RBAC: odontólogo las de sus turnos, recepcionista todas); `cancelado→devuelto` tras ejecución; recibo interno PDF por pago aprobado y por devolución ejecutada
  - Trazabilidad turno↔pago↔devolución↔comprobante navegable (base para C-11/C-12)
  - Abierta Q4 (60 % auto vs. manual) → default: manual en bandeja, umbral configurable pendiente
  - Tests: cálculo 100/60/0, idempotencia devolución, permisos bandeja, PDF recibo
- **Dependencias**: C-07
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/11_pagos_mercadopago.md` §4–§5 (bandeja, comprobantes)
  - `knowledge-base/07_flujos_principales.md` F2 (cancelación con devolución)
  - `knowledge-base/05_reglas_de_negocio.md` §3 RN-SENIA-100/60/0, RN-BANDEJA, RN-COMPROBANTE
  - `knowledge-base/04_modelo_de_datos.md` §2 (devolucion, comprobante)
  - `knowledge-base/10_preguntas_abiertas.md` §1.4 (umbral auto/manual)

---

## FASE 4 — Notificaciones (mail-only v1)

### [C-09] `mails-recordatorios`
- **Estado**: `[ ]` pendiente
- **Scope**: Mail transaccional + recordatorios con confirmar/cancelar desde el mail (épica E completa)
  - Modelo `RecordatorioMail` (`turno_id, tipo, destinatario, plantilla_version, estado encolado|enviado|reintentando|fallido|confirmado_desde_mail|cancelado_desde_mail, intentos, token_accion` hash único con expiración) + migración 005
  - Workers Redis separados del request path: colas, reintentos backoff 3 intentos, scheduler de ventana configurable `RECORDATORIO_VENTANA_HS`
  - Mails: confirmación inmediata al reservar (A3, tras `aprobado`), recordatorio en ventana (E1), aviso de devolución con comprobante (F2); plantillas versionadas
  - `GET /mail/confirmar?token=` / `/mail/cancelar?token=` — tokens firmados un solo uso, vida corta; cancelar deriva a F2 mostrando regla de seña (E2)
  - Config entregabilidad: `MAIL_FROM` alineado, docs SPF/DKIM/DMARC del dominio, métricas de entrega visibles (E3); fallo de alineación → `fallido` sin reintento infinito
  - Puerto/adaptador de notificaciones: WhatsApp **[v2]** conector apagado reutilizando `turno_id` + `plantilla_version` sin migraciones
  - Tests: scheduler ventana, backoff, token un uso/expirado, métricas
- **Dependencias**: C-05, C-07
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/07_flujos_principales.md` F4 (recordatorio por mail)
  - `knowledge-base/06_funcionalidades.md` §Épica E + §Épica A A3
  - `knowledge-base/08_arquitectura_propuesta.md` §1 (workers/outbox) + §6 (SPF/DKIM/DMARC)
  - `knowledge-base/04_modelo_de_datos.md` §2 (recordatorio_mail)
  - `knowledge-base/10_preguntas_abiertas.md` §3.7 (defaults ventana/reintentos)

---

## FASE 5 — Frontend

> C-10 y C-11 pueden proponerse en paralelo una vez que C-08 está archivado (C-11 requiere la bandeja de C-08).

### [C-10] `frontend-reserva-publica`
- **Estado**: `[ ]` pendiente
- **Scope**: SPA pública de reserva 3–4 pasos + páginas de acción por mail + precios públicos (épica A cara visible, D11)
  - Flujo canónico: datos (DNI con reconocimiento/precarga) → profesional → fecha/hora (slots de `GET /disponibilidad`) → confirmación viendo monto turno + seña (A4) → checkout MP → confirmación inmediata
  - Páginas `/mail/confirmar`, `/mail/cancelar`, `/mis-turnos` (token, nunca DNI solo) con estados de error amigables
  - Endpoints públicos de precio/trial (D11, `03 §3.6`); cancelación/reprogramación propia con reglas de seña visibles pre-confirmación (B1–B2)
  - Manejo de slot expirado/pago fallido sin bloquear al usuario (A5); sin datos de otros pacientes en ningún render
  - Tests E2E: reserva feliz, DNI reconocido, pago rechazado libera slot, cancelar desde mail
- **Dependencias**: C-05, C-07
- **Governance**: BAJO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §Épicas A, B
  - `knowledge-base/07_flujos_principales.md` F1 + F4.3
  - `knowledge-base/03_actores_y_roles.md` §1 R1 + §3 (rutas públicas)
  - `knowledge-base/09_decisiones_y_supuestos.md` D11 (precio/trial públicos)

---

### [C-11] `frontend-agenda-backoffice`
- **Estado**: `[ ]` pendiente
- **Scope**: Agenda del día + gestión staff + bandeja de devoluciones UI (épicas C1–C3, B3, D2, F1 cara interna)
  - Agenda del día aislada por profesional (odontólogo: solo la suya; recepcionista: todas, solo lectura salvo acciones permitidas)
  - ABM disponibilidad/bloqueos por odontólogo, marcar `atendido/no_show`, cancelar/reprogramar con motivo + historial visible actor+fecha (B3)
  - Reserva por teléfono a nombre del paciente (recepcionista, Q10: flujo exacto con datos mínimos DNI+mail)
  - Bandeja de devoluciones: aprobar/rechazar/ejecutar con trazabilidad turno↔pago↔devolución↔comprobante navegable; fichas de paciente (contacto + historial acotado)
  - Prohibiciones recepcionista enforced también en UI (no usuarios/roles, no config MP, no ARCA) — el backend ya las niega desde C-03
  - Tests E2E por rol: aislamiento de agenda, permisos bandeja, prohibiciones
- **Dependencias**: C-05, C-08
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/03_actores_y_roles.md` §1 R2/R3 + §2 (matriz completa)
  - `knowledge-base/06_funcionalidades.md` §Épicas B, C, D D2, F F1
  - `knowledge-base/07_flujos_principales.md` F2–F3
  - `knowledge-base/10_preguntas_abiertas.md` §3.10 (recepción por teléfono)

---

## FASE 6 — Reportes y cierre v1

### [C-12] `reportes-exportaciones`
- **Estado**: `[ ]` pendiente
- **Scope**: Reportes mínimos de asistencia + exportación CSV/PDF de turnos y caja (épicas F2–F3, RN-AUDIT)
  - Endpoints: conteos por estado y período (asistencia/ausentismo), caja (pagos/devoluciones conciliadas), solo roles autorizados (RBAC `03 §2`)
  - Exportación CSV/PDF de turnos y caja con filtros por odontólogo/período; auditoría exportable (D3: diferencial barato)
  - Métricas de entrega de mail visibles para el consultorio (base de C-09); métrica propia de ausentismo **excluida** (solo v2+ académico, D12/Q8)
  - UI mínima en `frontend/src/pages/reportes` con descarga y vista de conteos
  - Tests: permisos exportación, filtros, cuadre caja vs. eventos de pago
- **Dependencias**: C-05, C-07
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §Épica F F2–F4
  - `knowledge-base/05_reglas_de_negocio.md` §6 RN-AUDIT
  - `knowledge-base/09_decisiones_y_supuestos.md` D3, D12 (auditoría diferencial, ausentismo v2+)
  - `knowledge-base/11_pagos_mercadopago.md` §6–§7 (conciliación, trazabilidad para caja)

---

### [C-13] `hardening-cumplimiento-cierre`
- **Estado**: `[ ]` pendiente
- **Scope**: Endurecimiento v1 + cumplimiento mínimo explícito + verificación de recorte (criterios de éxito `01 §5`)
  - TLS en tránsito + cifrado declarado de sensibles en reposo; backups periódicos PostgreSQL con prueba de restore; job de retención RN-RETENCION con política publicada
  - Rate-limit auditado en todas las rutas públicas `03 §3`; verificación de flags v2 apagados (`WHATSAPP_ENABLED=false`, `ARCA_ENABLED=false`, `lista_espera` sin escrituras, sin sobre-turnos RN-SOBRETURNO)
  - Seed final completo `04 §5` (10 turnos todos los estados, 1 pago aprobado + 1 devolución 60 % ejecutada) + datos demo precio/trial públicos
  - Verificación E2E de los 5 criterios de éxito v1 (reserva→seña→mail sin intervención; no doble-reserva concurrente; rastro auditable total; confirmar/cancelar desde mail; recorte sostenido)
  - Riesgos Q11/Q12 documentados como limitaciones conocidas (sin validación usuarios reales, sin dictamen legal Ley 25.326/26.529)
  - Tests: restore backup, retención, flags v2 off, checklist criterios de éxito
- **Dependencias**: C-09, C-11, C-12
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/08_arquitectura_propuesta.md` §7 (cumplimiento técnico)
  - `knowledge-base/01_vision_y_objetivos.md` §4–§5 (fuera de alcance, criterios de éxito)
  - `knowledge-base/02_descripcion_general.md` §5 (cumplimiento mínimo)
  - `knowledge-base/10_preguntas_abiertas.md` §4 (Q11–Q14 limitaciones conocidas)

---

## Resumen

| Change | Nombre | Fase | Gov | Deps |
|---|---|---|---|---|
| C-01 | foundation-setup | 0 Cimientos | BAJO | — |
| C-02 | core-models-usuarios-pacientes | 0 Cimientos | CRITICO | C-01 |
| C-03 | auth-jwt-rbac | 1 Auth | CRITICO | C-02 |
| C-04 | disponibilidad-slots | 2 Turnos | MEDIO | C-03 |
| C-05 | reserva-turnos-estados | 2 Turnos | CRITICO | C-04 |
| C-06 | ficha-paciente-consentimiento | 2 Turnos | MEDIO | C-03 |
| C-07 | pagos-mp-checkout-webhook | 3 Pagos | CRITICO | C-05 |
| C-08 | devoluciones-comprobantes-conciliacion | 3 Pagos | CRITICO | C-07 |
| C-09 | mails-recordatorios | 4 Notif | ALTO | C-05, C-07 |
| C-10 | frontend-reserva-publica | 5 Frontend | BAJO | C-05, C-07 |
| C-11 | frontend-agenda-backoffice | 5 Frontend | MEDIO | C-05, C-08 |
| C-12 | reportes-exportaciones | 6 Cierre | MEDIO | C-05, C-07 |
| C-13 | hardening-cumplimiento-cierre | 6 Cierre | ALTO | C-09, C-11, C-12 |

**Primer change recomendado**: `C-01` (foundation-setup). Para arrancar: `/opsx:propose C-01-foundation-setup`
