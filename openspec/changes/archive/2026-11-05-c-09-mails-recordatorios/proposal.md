# Proposal — c-09-mails-recordatorios

## Why

El consultorio necesita avisar por mail sin intervención humana: confirmación al reservar (A3), recordatorio en ventana configurable (E1) y aviso de devolución (F2), con confirmar/cancelar desde el propio mail (E2) y fallos visibles (E3). Hoy no existe ninguna pieza de notificaciones: `worker` es un esqueleto, `app/domain/notificaciones` e `infra/smtp` están vacíos y no hay tabla de outbox.

**Brecha de dependencias verificada.** C-09 declara depender de C-05 y C-07. C-05 está archivado, pero **C-07 (pagos MP) y C-08 (devoluciones) no existen**: el head real de Alembic es `003_turno_historial`, `app/domain/pagos` y `app/domain/devoluciones` solo contienen `__init__.py`, y no hay tablas `pago`/`devolucion` ni rutas de pago. Por decisión explícita del usuario este change avanza igual, con una estrategia de integración tardía que no simula pagos ni devoluciones:

- la confirmación se engancha en la transición `creado→confirmado` con actor `sistema` (el mismo seam que C-07 disparará al aprobar el pago);
- el aviso de devolución se entrega como servicio de dominio testeable, sin productor real hasta C-08;
- la cancelación desde el mail usa la máquina de estados C-05 y la cotización 100/60/0, sin ejecutar devolución real.

## What Changes

- **Modelo + migración `004_recordatorio_mail`** (`down_revision = 003_turno_historial`): `recordatorio_mail` con `turno_id, tipo (confirmacion|recordatorio|aviso_devolucion), destinatario, plantilla_version, estado cerrado, intentos, token_accion_hash, token_expira_at, token_usado_at, ultimo_error, proximo_intento_at`. Justificación de numeración: el head real es 003; C-07/C-08 toman 005/006 cuando existan.
- **Outbox transaccional**: el insert de la fila ocurre en la **misma transacción** que el cambio de turno. Hook en `transition()` para `creado→confirmado` con actor `sistema`, de modo que C-07 no cambie código al aprobar el pago.
- **Servicios de dominio**: `encolar_confirmacion`, `encolar_recordatorio`, `encolar_aviso_devolucion` (idempotentes por `UNIQUE(turno_id, tipo)`; el último sin productor real hasta C-08).
- **Adaptador SMTP stdlib** (`smtplib` + `email.message.EmailMessage`) sin dependencias nuevas, configurado por `SMTP_HOST/PORT/USER/PASS` y `MAIL_FROM`; MailHog local `mailhog:1025` sin auth.
- **Plantillas versionadas v1**: confirmación, recordatorio y aviso de devolución, en texto + HTML con escaping, con links de acción.
- **Worker real** en `backend/app/workers/main.py`: BLPOP de `mail:pendientes` con payload `{"recordatorio_id": "<uuid>"}`, relectura desde DB, envío SMTP, 3 intentos con backoff 1 y 5 min vía `proximo_intento_at`, scheduler de ventana `RECORDATORIO_VENTANA_HS`, idempotencia y estados terminales.
- **Tokens de acción un solo uso**: un token por mail (`proposito="mail_accion"`), hash SHA-256 persistido en `token_accion_hash`, expiración `MAIL_ACTION_TTL_MIN` (default 2880), consumo single-use en DB (`token_usado_at`), **sin** depender del fallback en memoria de C-03 para la regla de un uso.
- **Endpoints públicos** `GET /api/mail/confirmar?token=` y `GET /api/mail/cancelar?token=` con rate-limit, HTML mínimo, idempotencia; cancelar usa la máquina de estados C-05 + cotización 100/60/0 y deja la devolución para C-08.
- **Config**: `MAIL_ACTION_TTL_MIN=2880`, `MAIL_RATE_LIMIT=30`, `API_PUBLIC_URL=http://localhost:8000` en `.env.example` raíz y backend. No se alteran las 15 variables pineadas por tests.
- **Docker Compose**: el `worker` recibe `DATABASE_URL`, SMTP y `MAIL_FROM`, y `depends_on` db/redis/mailhog; MailHog ya existe.
- **Métricas mínimas**: `contar_por_estado()` en dominio y `GET /api/mail/metricas` staff-only si no amplía el alcance; en su defecto se justifica y queda la base para C-12.
- **TDD estricto** (U2): 3 escenarios por regla (feliz / error de negocio / borde) en modelo/migración, tokens, plantillas, outbox, scheduler, worker (éxito, fallo, tercer fallo, replay), endpoints y rate-limit, con SMTP fake.

## Capabilities

### New Capabilities

- `mails-recordatorios`: outbox transaccional de mails con plantillas versionadas, tokens de acción un solo uso y hash en DB, worker Redis con backoff y scheduler de ventana, adaptador SMTP configurable, endpoints públicos de confirmar/cancelar y métricas de entrega.

### Modified Capabilities

<!-- Ninguna capability existente cambia sus requirements: la máquina de estados C-05 se reutiliza sin alterar su contrato y los pagos/devoluciones no existen todavía. -->

## Impact

- **Añade**: `backend/app/domain/notificaciones/` (modelo lógico, servicios de outbox, plantillas, tokens, scheduler, métricas), `backend/app/infra/smtp/` (adaptador stdlib), `backend/app/api/mail.py`, `backend/app/workers/main.py` (lógica real), modelo `RecordatorioMail`, migración `004_recordatorio_mail`, tests nuevos.
- **Modifica**: `backend/app/domain/turnos/estados.py` (hook de outbox en `creado→confirmado`), `backend/app/core/settings.py` (4 settings nuevos), `backend/app/main.py` (router), `docker-compose.yml` (worker), `.env.example` y `backend/.env.example`.
- **No toca**: `PacienteService.resolve_or_create` (no se actualiza el email del paciente existente; limitación documentada), pagos MP ni devoluciones (C-07/C-08), frontend (C-10/C-11), flags v2 (P13 intacto: WhatsApp apagado, sin escrituras en `lista_espera`), las 15 vars del contrato C-01.
- **Riesgo de secuencia**: hasta que C-07 exista, la confirmación no tiene productor en producción salvo el hook de `transition()`; hasta que C-08 exista, el aviso de devolución no se encola desde un flujo real. Ambos quedan listos y testeados a nivel dominio.
