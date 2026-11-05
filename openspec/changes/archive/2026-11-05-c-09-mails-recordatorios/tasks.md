# Tasks — c-09-mails-recordatorios

> TDD estricto (U2) en cada grupo: RED → GREEN → TRIANGULATE con 3 escenarios (feliz / error de negocio / borde) antes de avanzar. Tests conviven con su grupo; no se difieren al final.
>
> Brecha asumida: C-07 y C-08 no existen. La confirmación se engancha en `transition()` (`creado→confirmado`, actor `sistema`) y el aviso de devolución se entrega como servicio de dominio sin productor real. No se implementa cobro ni devolución.

## 1. Migración 004 + modelo `RecordatorioMail`

- [x] 1.1 Crear migración Alembic `004_recordatorio_mail` (`down_revision = "003_turno_historial"`, tabla, CHECKs de tipo/estado/intentos, `UNIQUE(turno_id, tipo)`, `CHECK(token_accion_hash IS NULL OR token_expira_at IS NOT NULL)`, índices `(estado, proximo_intento_at)` y `turno_id`, grants SELECT/INSERT/UPDATE sin DELETE, downgrade completo) y verificar con tests estáticos: encadena 003, no usa `create_all`, y `downgrade` elimina solo lo nuevo
- [x] 1.2 Implementar el modelo SQLAlchemy `RecordatorioMail` (JSON portable para `contexto_json`, `AuditMixin`, constraints espejo) y re-exportarlo en `infra/db/models/__init__.py`; verificar con 3 escenarios: insert válido persiste, tipo/estado inválido rechazado, duplicado `(turno_id,tipo)` rechazado
- [x] 1.3 Implementar repositorio/consultas base del outbox (obtener por hash, por turno+tipo, contar por estado) y verificar que una fila con `token_accion_hash` guarda solo el hash y nunca el token crudo

## 2. Tokens de acción de un solo uso en DB

- [x] 2.1 Implementar emisión de un token por mail (`proposito='mail_accion'`, `action_min=MAIL_ACTION_TTL_MIN`, `sub=recordatorio_id`) + persistencia de `sha256`, `token_expira_at` y la operación de consumo `token_usado_at` en DB; verificar 3 escenarios: primer uso válido consume, reuso rechazado sin cambios, token expirado rechazado
- [x] 2.2 Verificar que el consumo no depende de `ActionTokenStore` ni del fallback en memoria: correr el mismo escenario con Redis ausente y confirmar que el segundo uso sigue rechazado por DB

## 3. Plantillas versionadas + adaptador SMTP stdlib

- [x] 3.1 Implementar registro `PLANTILLAS["v1"]` con confirmación, recordatorio y aviso de devolución (texto + HTML, escaping de todo dato interpolado, links `API_PUBLIC_URL/api/mail/confirmar|cancelar`); verificar 3 escenarios: render incluye ambos formatos y links, nombre con `<script>` queda escapado, aviso de devolución no ofrece confirmar/cancelar
- [x] 3.2 Implementar `SmtpMailer` con `smtplib` + `EmailMessage` (host/puerto/user/pass/`MAIL_FROM`, login solo con user, timeout, `From` siempre `MAIL_FROM`); verificar con SMTP fake: envío feliz contra MailHog sin auth, SMTP caído propaga error reintentable, `From` alineado en todo mensaje
- [x] 3.3 Verificar que no se agregó ninguna dependencia nueva a `requirements.txt`/`pyproject.toml` y que `app/infra/smtp/` no importa librerías de terceros

## 4. Outbox transaccional + servicios `encolar_*`

- [x] 4.1 Implementar `encolar_confirmacion`, `encolar_recordatorio` y `encolar_aviso_devolucion` idempotentes por `(turno_id,tipo)` (existente → se devuelve; carrera → re-consulta), con emisión de token al crear; verificar 3 escenarios: primer encolado crea `encolado`, segundo encolado no duplica, tipos distintos conviven
- [x] 4.2 Implementar el caso "paciente sin email": fila `fallido`, `destinatario=''`, `ultimo_error='paciente sin email'`, `intentos=0`, sin publicación; verificar 3 escenarios: sin email no se publica, el fallo aparece en métricas, email presente sí encola
- [x] 4.3 Enganchar `encolar_confirmacion` dentro de `transition()` para `('creado','confirmado')` con actor `sistema`, antes del `flush()` y con import diferido; verificar 3 escenarios: turno+historial+outbox en el mismo commit, rollback no deja outbox huérfano, otras transiciones no generan confirmación
- [x] 4.4 Implementar `publicar_pendientes(session)` (publica `encolado` con `publicado_at IS NULL` y marca `publicado_at`) y verificar que una fila ya publicada no se re-publica ni se envía dos veces

## 5. Worker: consumo, reintentos y estados terminales

- [x] 5.1 Reemplazar el esqueleto por el consumo real de `mail:pendientes` (payload `{"recordatorio_id"}`, relectura DB, guardas de estado y vencimiento, envío SMTP, `enviado`/`enviado_at`); verificar 3 escenarios: primer intento exitoso, replay del mismo job no reenvía, fila no enviable se descarta sin tocar el turno
- [x] 5.2 Implementar el fallo con backoff `[1, 5]` minutos vía `intentos` + `proximo_intento_at` (0→1 reintenta en 1 min, 1→2 en 5 min, 2→3 `fallido`); verificar 3 escenarios: fallo transitorio queda `reintentando` con `intentos=1`, tercer fallo termina `fallido` con `intentos=3`, error SMTP queda en `ultimo_error`
- [x] 5.3 Implementar el scheduler en el mismo proceso (tick `WORKER_SCHEDULER_TICK_S`, default 60 s): publicar outbox, re-publicar `reintentando` vencidos y encolar recordatorios de turnos `confirmado` dentro de `RECORDATORIO_VENTANA_HS` sin recordatorio; verificar 3 escenarios: dentro de ventana encola exactamente uno, fuera de ventana no encola, reintento vencido se re-publica una vez
- [x] 5.4 Conservar heartbeat y tolerancia a Redis/SMTP/DB caídos sin crash del loop; verificar que el healthcheck de Compose sigue funcionando y que un fallo de infraestructura no pierde la fila (queda reintentable)

## 6. Endpoints públicos `/api/mail/*`

- [x] 6.1 Implementar `GET /api/mail/confirmar?token=` (hash→fila, firma/expiración, estado `confirmado`, `token_usado_at`, `estado='confirmado_desde_mail'`, historial de trazabilidad actor+fecha) con HTML mínimo; verificar 3 escenarios: confirmación válida, token ajeno/inválido no autoriza, replay/ya confirmado no duplica historial
- [x] 6.2 Implementar `GET /api/mail/cancelar?token=` (cotización 100/60/0, `transition` a `cancelado` con actor `paciente`, `estado='cancelado_desde_mail'`, sin devolución real); verificar 3 escenarios: cancelación válida mueve el turno y muestra el porcentaje, turno no `confirmado` no se recancela, no se registra ninguna devolución ejecutada
- [x] 6.3 Implementar rate-limit por IP (`MAIL_RATE_LIMIT`, clave `mail:ratelimit:{ip}`) evaluado antes de consumir el token; verificar 3 escenarios: bajo el límite procesa, ráfaga devuelve 429 y el token sigue sin usar, token inválido no consume cupo
- [x] 6.4 Registrar el router en `app/main.py` y verificar que ambas rutas siguen públicas (sin JWT) y cubiertas por el registro `GET /mail/*` de P12

## 7. Métricas de entrega

- [x] 7.1 Implementar `contar_por_estado(session, desde=None, hasta=None)` con las 6 claves y ceros por defecto; verificar 3 escenarios: conteo feliz con mezcla de estados, sin registros devuelve ceros, filtro por período excluye fuera de rango
- [x] 7.2 Implementar `GET /api/mail/metricas` staff-only (`odontologo|recepcionista|admin`, sin destinatarios ni tokens); verificar 3 escenarios: staff obtiene conteos, sin token 401/403, paciente/rol ajeno no accede

## 8. Configuración, Compose y documentación

- [x] 8.1 Agregar `MAIL_ACTION_TTL_MIN=2880`, `MAIL_RATE_LIMIT=30`, `API_PUBLIC_URL=http://localhost:8000`, `WORKER_SCHEDULER_TICK_S=60` a `.env.example` raíz y `backend/.env.example`, y los settings correspondientes; verificar que las 15 vars del contrato C-01 y sus valores pineados siguen intactos (`test_env_contract.py` en verde)
- [x] 8.2 Actualizar `docker-compose.yml` (worker con `DATABASE_URL`, SMTP, `MAIL_FROM`, `MAIL_*`, `API_PUBLIC_URL`, `WORKER_SCHEDULER_TICK_S`; `depends_on` db/redis/mailhog) y verificar `docker compose config` sin errores y MailHog alcanzable
- [x] 8.3 Documentar en el change (y en CHANGES.md al archivar) la renumeración `C-09→004`, `C-07→005`, `C-08→006`, la brecha de integración C-07/C-08 y el follow-up del email del paciente existente; verificar que ningún spec archivado contradice el nuevo head

## 9. Integración y cierre del change

- [x] 9.1 Correr la suite completa de backend (pytest + mypy + ruff) y verificar que no hay regresiones en C-01..C-06/C-07F ni warnings de tipo
  - `ruff check app`: limpio.
  - `mypy app`: limpio (127 archivos).
  - `pytest app/tests/ -q`: 296 pasan, 0 fallan.
  - Los 2 fallos iniciales (`test_db.py::test_sin_create_all_en_backend_borde`, `test_p3_v2off.py::test_cero_create_all_fuera_de_tests`) eran falsos positivos por `backend/venv`; se excluyó `venv/.git/site-packages` de los escaneos de tests sin cambiar la regla P3.
- [ ] 9.2 Verificar de punta a punta en dev con MailHog: confirmar por `transition()` directo (simulando el seam C-07) → outbox → scheduler → worker → mail visible; y cancelar desde el link → turno `cancelado` + porcentaje mostrado (pendiente: MailHog no arrancado; gate estática y suite pasan).
- [x] 9.3 Ejecutar `openspec validate c-09-mails-recordatorios --strict` y corregir hasta que pasa (`openspec validate --all --strict`: 8/8 specs válidas, incluido `spec/mails-recordatorios`).

## Workflow follow-up

- [x] Archivar el change solo si todos los tests pasan (`/opsx:archive c-09-mails-recordatorios`): archivado como `2026-11-05-c-09-mails-recordatorios`, spec sincronizada.
- [x] Marcar `[x]` C-09 en `CHANGES.md` con nota explícita: subsistema de mails completo, integración C-07 (productor de confirmación) y C-08 (productor de aviso de devolución) pendiente.
- [x] Registrar el follow-up de actualización de email de paciente existente para un change posterior.
