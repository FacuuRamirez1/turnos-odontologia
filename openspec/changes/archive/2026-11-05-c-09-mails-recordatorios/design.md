# Design — c-09-mails-recordatorios

## Context

C-05 está archivado con la máquina de estados `transition()` como único seam de transición, mail-action JWTs de un solo uso (hoy con consumo en Redis/memoria, `app/core/security/action_tokens.py`) y cotización 100/60/0 pura (`app/domain/turnos/cancelacion.py`). C-03 aporta JWT y `require_role()`; C-02 el rol DB least-privilege; C-01 el worker esqueleto, MailHog y Compose.

**Brecha verificado en repo:** C-07 (pagos MP) y C-08 (devoluciones) no existen. Head Alembic real: `003_turno_historial`. `app/domain/pagos` y `app/domain/devoluciones` solo tienen `__init__.py`; no hay tablas `pago`/`devolucion`, ni webhook MP, ni bandeja. C-09 se construye igual por decisión explícita del usuario, dejando seams listos y testeando a nivel dominio lo que aún no tiene productor de producción.

## Goals / Non-Goals

**Goals:**
- Outbox de mails confiable: la fila se escribe en la misma transacción que el cambio de turno; una caída entre commit y publicación no pierde el mail.
- Entrega idempotente con reintentos acotados y fallos visibles.
- Confirmar/cancelar desde el mail con token de un solo uso cuya regla vive en DB, no en memoria.
- No introducir dependencias nuevas (SMTP stdlib) ni romper el contrato de entorno C-01.

**Non-Goals:**
- C-07 (checkout/webhook MP) y C-08 (bandeja/devolución real). No se simulan pagos ni se ejecutan devoluciones.
- WhatsApp (P13: conector apagado), reply-parse inbound, aperturas/rebotes vía proveedor.
- Actualizar el email de un paciente existente en `PacienteService.resolve_or_create` (follow-up documentado).
- Frontend (C-10/C-11).

## Decisions

### 1. Migración `004_recordatorio_mail` (no 005/006)

- El head real es `003_turno_historial` y no existen C-07/C-08. Alembic exige una cadena lineal: la siguiente revisión es `004`.
- `down_revision = "003_turno_historial"`. Cuando C-07 y C-08 se implementen tomarán `005_pago_evento` y `006_devolucion_comprobante`. Se documenta la renumeración en CHANGES.md (la nota histórica de C-05 decía C-07→004; queda superada por el orden real de implementación).
- Tabla `recordatorio_mail`:
  - `id UUID PK`, `turno_id UUID FK turno.id ON DELETE RESTRICT`.
  - `tipo VARCHAR(20) CHECK IN ('confirmacion','recordatorio','aviso_devolucion')`.
  - `destinatario VARCHAR(255) NOT NULL DEFAULT ''` (vacío cuando el paciente no tiene email).
  - `plantilla_version VARCHAR(20) NOT NULL DEFAULT 'v1'`.
  - `estado VARCHAR(30) CHECK IN ('encolado','enviado','reintentando','fallido','confirmado_desde_mail','cancelado_desde_mail')`, default `'encolado'`.
  - `intentos INTEGER NOT NULL DEFAULT 0 CHECK (intentos >= 0 AND intentos <= 3)`.
  - `ultimo_error TEXT NULL`, `proximo_intento_at TIMESTAMPTZ NULL`, `enviado_at TIMESTAMPTZ NULL`, `publicado_at TIMESTAMPTZ NULL`.
  - `token_accion_hash CHAR(64) NULL UNIQUE`, `token_expira_at TIMESTAMPTZ NULL`, `token_usado_at TIMESTAMPTZ NULL`; `CHECK (token_accion_hash IS NULL OR token_expira_at IS NOT NULL)`.
  - `contexto_json JSONB NOT NULL DEFAULT '{}'` — mínimo para transportar el porcentaje cotizado del aviso de devolución sin recomputarlo al enviar.
  - `UNIQUE (turno_id, tipo)` = idempotencia de encolado.
  - Audit columns (`is_active, created_at, updated_at, deleted_at`) para consistencia con el resto del modelo.
  - Índices: `(estado, proximo_intento_at)` parcial `WHERE is_active` (scheduler/reintentos), `turno_id` (trazabilidad), `token_accion_hash` ya cubierto por UNIQUE.
  - Grants: `SELECT, INSERT, UPDATE` a `app_turnos`; **sin** `DELETE`.
- `JSONB` solo en Postgres. Como los tests corren sobre SQLite, el modelo SQLAlchemy usa `JSON` genérico (portable) y la migración usa `postgresql.JSONB`; el contrato se aserta estáticamente igual que C-05.

### 2. Outbox transaccional + publicación post-commit

- Los servicios `encolar_confirmacion`, `encolar_recordatorio` y `encolar_aviso_devolucion` **solo insertan/actualizan la fila**; no publican a Redis ni envían. El insert ocurre en la misma `Session`/transacción del caller.
- Hook en `transition()`: cuando el par es `('creado','confirmado')` y `actor_tipo == 'sistema'`, se llama `encolar_confirmacion(session, turno)` **antes** del `flush()`, con import diferido para evitar ciclos (`domain.turnos.estados` → `domain.notificaciones.outbox`). Si el outbox falla, falla toda la transición (nunca se confirma un turno sin rastro de mail).
- Publicación: la fila es la fuente de verdad. El worker, en cada tick del scheduler, publica a `mail:pendientes` las filas `encolado` con `publicado_at IS NULL` y las marca con `publicado_at = now()`. Esto cubre cualquier caída entre commit y push y también sirve de safety net para C-07, que no necesita código de mail.
- Consecuencia aceptada: la confirmación puede publicarse hasta un tick (60 s) después del commit. En v1 no hay productor real de `creado→confirmado` hasta C-07, así que no afecta la experiencia actual; cuando C-07 exista, puede llamar a `publicar_pendientes(session)` después de su commit para bajar la latencia.
- Idempotencia de encolado: `SELECT` por `(turno_id,tipo)`; si existe se devuelve. Si dos transacciones compiten, el `UNIQUE` arbitra y el perdedor re-consulta (`IntegrityError` → rollback → requery), igual que el patrón C-05.
- Sin email utilizable (NULL/blank): la fila nace `fallido`, `destinatario=''`, `ultimo_error='paciente sin email'`, `intentos=0`, `publicado_at=now()` (nunca se publica). Se prefiere esto a no crear la fila porque E3 exige que el fallo sea visible en métricas.

### 3. Tokens de acción: un token por mail, hash en DB

- Al crear la fila se emite **un** token `create_action_token(sub=str(recordatorio_id), proposito='mail_accion', action_min=MAIL_ACTION_TTL_MIN)`. El mismo token alimenta los links de confirmar y de cancelar; la acción la determina la ruta.
- Se persiste **solo** `sha256(token)` en `token_accion_hash`, más `token_expira_at`. El token crudo solo viaja en el cuerpo del mail.
- `token_usado_at` es la regla de un solo uso: la acción es un `UPDATE ... WHERE token_accion_hash = :hash AND token_usado_at IS NULL` (o chequeo + flush con lock implícito), por lo que no depende del fallback en memoria de `ActionTokenStore` ni de Redis. Aun así se valida la firma/expiración con `decode_and_validate(token, 'action', secret)`.
- El `sub` no se usa para autorizar el turno: el vínculo token→turno es la propia fila (`token_accion_hash` → `turno_id`).
- Reuso: segundo intento con mismo token → rechazo (409/422 HTML) sin transición. Turno ya confirmado con un token distinto → página idempotente "ya confirmado", sin historial nuevo.

### 4. Worker: consumo, reintentos y scheduler en el mismo proceso

- `backend/app/workers/main.py` deja de ser esqueleto:
  - `BLPOP mail:pendientes` → payload `{"recordatorio_id": "<uuid>"}` → relectura de la fila desde DB (fuente de verdad, el payload no confía en estado).
  - Guardas: solo procesa `encolado` o `reintentando` con `proximo_intento_at <= now()`; si no, descarta el job (idempotencia de replay).
  - Envío SMTP; éxito → `enviado`, `enviado_at`, `publicado_at` seteado.
  - Fallo → `intentos += 1`; si `intentos < 3` → `reintentando` y `proximo_intento_at = now() + delay`; si `intentos == 3` → `fallido`.
  - Backoff fijo: delays `[1, 5]` minutos. Es decir: fallo del intento 1 → +1 min; fallo del intento 2 → +5 min; fallo del intento 3 → `fallido`.
- Scheduler: tick periódico (`WORKER_SCHEDULER_TICK_S`, default 60 s) en el mismo proceso:
  1. publica outbox pendiente (`encolado` sin `publicado_at`);
  2. re-publica `reintentando` con `proximo_intento_at <= now()` y `publicado_at <= proximo_intento_at` (evita doble publicación entre ticks);
  3. busca turnos `confirmado` con `inicio` dentro de `RECORDATORIO_VENTANA_HS` y sin `recordatorio` existente → `encolar_recordatorio`.
- El heartbeat (`/tmp/worker.heartbeat`) se conserva para el healthcheck de Compose.

### 5. SMTP stdlib y plantillas versionadas

- `app/infra/smtp/client.py`: `SmtpMailer(host, port, user, pass, mail_from, timeout=10)` con `smtplib.SMTP`; login solo si `SMTP_USER` no está vacío; envío con `EmailMessage` (`set_content` texto + `add_alternative` HTML). MailHog (`mailhog:1025`, sin auth) funciona sin configuración extra. Cero dependencias nuevas.
- `app/domain/notificaciones/plantillas.py`: registro `PLANTILLAS = {"v1": {...}}` con tres plantillas. Cada render devuelve `(asunto, texto, html)`. Todo valor interpolado se escapa con `html.escape(quote=False)` para HTML; el texto plano no interpola HTML. Los links usan `API_PUBLIC_URL` y `urllib.parse.quote` del token.
- `plantilla_version` se persiste en la fila para que un cambio futuro de copy sea auditable y no reescriba mails ya encolados.

### 6. Endpoints públicos `/api/mail/*`

- `GET /api/mail/confirmar?token=` y `GET /api/mail/cancelar?token=`, `HTMLResponse` mínima y sin datos de otros pacientes.
- Rate-limit por IP con `LoginRateLimiter` reutilizado, límite `MAIL_RATE_LIMIT` (default 30/60 s), clave `mail:ratelimit:{ip}` (mismo formato `:` de redis-core). El rate-limit se evalúa **antes** de consumir el token: una ráfaga no quema links válidos.
- Confirmar: busca la fila por hash, valida firma/expiración, exige `turno.estado == 'confirmado'`, marca `token_usado_at` y `estado='confirmado_desde_mail'`. No emite una transición C-05 porque el turno ya está confirmado; escribe un `turno_historial` de trazabilidad con `estado_anterior = estado_nuevo = 'confirmado'`, actor `paciente` y motivo `confirmado_desde_mail` (cumple P9: actor+fecha incluso en una acción que no cambia estado).
- Cancelar: cotiza con `cotizar_devolucion(turno.inicio, ANTICIPACION_MIN_HS)`, ejecuta `transition(..., 'cancelado', actor_tipo='paciente', actor_id=paciente_id, motivo='cancelado_desde_mail')` y marca la fila `cancelado_desde_mail`. Muestra el porcentaje. **No** crea ni ejecuta devolución real (C-08 pendiente).
- HTML de error: 400 token inválido/expirado/usado, 409 estado incompatible, 429 rate-limit, 404 fila inexistente. Nunca se loguea el token crudo ni la URL completa.

### 7. Métricas

- `contar_por_estado(session, desde=None, hasta=None) -> dict[str,int]` en dominio; devuelve las 6 claves con 0 cuando no hay filas.
- `GET /api/mail/metricas` staff-only (`require_role("odontologo","recepcionista","admin")`, P8) devuelve conteos agregados (sin destinatarios ni tokens). Es barato y deja la base para C-12, que podrá reutilizar el servicio.

### 8. Configuración y Compose

- Nuevos settings (todos por env, P5): `MAIL_ACTION_TTL_MIN=2880`, `MAIL_RATE_LIMIT=30`, `API_PUBLIC_URL=http://localhost:8000`, `WORKER_SCHEDULER_TICK_S=60`.
- Se documentan en `.env.example` raíz y `backend/.env.example`. **No se tocan** las 15 variables del contrato C-01 ni sus valores pineados (`RECORDATORIO_VENTANA_HS=24`, `RESERVA_TTL_MIN=15`, `WHATSAPP_ENABLED=false`, `ARCA_ENABLED=false`).
- Compose `worker`: agrega `DATABASE_URL`, `SMTP_HOST/PORT/USER/PASS`, `MAIL_FROM`, `MAIL_*`, `API_PUBLIC_URL`, `WORKER_SCHEDULER_TICK_S`; `depends_on` pasa a db/redis/mailhog (api se mantiene si se quiere esperar migraciones). MailHog ya existe.

### 9. Limitaciones explícitas (no se resuelven acá)

- `PacienteService.resolve_or_create` no actualiza `email/telefono` de un paciente existente. Si el paciente reservó antes sin mail y luego lo provee, los mails seguirán fallando hasta un follow-up. Se documenta en CHANGES.md y en el design; no se cambia el contrato C-06 en este change.
- Sin C-07, `creado→confirmado` no tiene productor web; el hook queda listo y testeado con `transition()` directo.
- Sin C-08, `encolar_aviso_devolucion` no tiene productor de flujo; se testea a nivel dominio.
- Sin TLS/SPF/DKIM reales: el adaptador usa SMTP plano en dev. Producción exige configurar un relay autenticado/TLS por env; no se agrega starttls automático en v1 para no inventar topología.

## Risks / Trade-offs

- **[Risk] Publicación hasta un tick tarde** → aceptado en v1 (sin productor real de confirmación); `publicar_pendientes()` disponible para que C-07 reduzca la latencia.
- **[Risk] Duplicado de job en la cola** → el worker re-lee la DB y descarta filas no enviables; `publicado_at` evita republicar en cada tick.
- **[Risk] Token en URL puede quedar en logs de proxy** → no se loguea la URL ni el token; el token es de un solo uso y TTL 48 h por defecto.
- **[Risk] `JSONB` no existe en SQLite** → el modelo usa `JSON` portable; la migración usa `JSONB` y el test estático lo verifica, igual que el patrón C-05 con `EXCLUDE`.
- **[Risk] Email faltante o inválido** → se marca `fallido` visible sin reintentos; no se valida sintaxis de email en v1 (evita rechazar direcciones válidas raras).
- **[Risk] Cancelación desde mail sin devolución real** → el paciente ve la cotización, pero C-08 aún no ejecuta el reembolso. Es una brecha de producto conocida y se registra en CHANGES.md.
- **[Trade-off] Un token para confirmar y cancelar** → simplifica el mail y el modelo; confirmar consume el token e invalida el cancelar, lo cual es correcto (el turno ya no debe cancelarse desde ese mail).

## Migration Plan

1. `alembic upgrade head` → `004_recordatorio_mail` (tabla + constraints + índices + grants).
2. Deploy API y worker juntos; el worker nuevo necesita `DATABASE_URL` y SMTP.
3. Verificación: `alembic current = 004_recordatorio_mail`; insertar fila adversa (estado inválido, tipo inválido, duplicado turno+tipo) debe fallar; `alembic downgrade -1` elimina solo la tabla nueva.
4. Rollback de aplicación: el hook de `transition()` es aditivo; si se revierte el código, las filas quedan huérfanas pero inofensivas (no hay productor).

## Open Questions

- Ventana de métricas por defecto (propuesto: todos los registros activos; C-12 podrá filtrar por período).
- Relay SMTP de producción (TLS/auth) queda como configuración de despliegue, fuera del alcance v1.
- Follow-up de actualización de email del paciente existente (no bloquea C-09).
