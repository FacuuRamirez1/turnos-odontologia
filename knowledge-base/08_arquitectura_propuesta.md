# 08 — Arquitectura propuesta

**Proyecto**: turnos-odontología · **Fecha**: 2026-10-14 · **Fuente**: `discovery/discovery.md` (§8–9)
Relacionadas: `02_descripcion_general.md`, `04_modelo_de_datos.md`, `07_flujos_principales.md`, `11_pagos_mercadopago.md`.

## 1. Patrones

- Monolito modular FastAPI por dominios (turnos, disponibilidad, pagos, devoluciones, notificaciones, reportes) con repositorios que fuerzan `odontologo_id` (aislamiento de agenda).
- Constraints de dominio en PostgreSQL (unicidad, exclusión de rangos, checks) + lock optimista (`version`) en reserva concurrente.
- Outbox transaccional o escritura atómica turno+pago+evento antes de llamar a MP (nunca cobrar sin rastro local).
- Workers Redis para mails (colas, reintentos con backoff, scheduler de ventana) separados del request path.
- Audit trail append-only: rol DB de app sin UPDATE/DELETE sobre `turno_historial` y `evento_pago`.
- Puertos/adaptadores para notificaciones (mail [v1], WhatsApp [v2] apagado) y pagos (MP [v1], ARCA [v2] apagado).

## 2. Estructura de directorios propuesta

```
backend/app/{api,core(security,jwt),domain/{turnos,disponibilidad,pagos,devoluciones,notificaciones,reportes},
infra/{db,redis,mp,smtp},workers,tests}  frontend/src/{pages/{reserva,agenda,bandeja,reportes},components,api,auth}
```

## 3. Seguridad JWT

- Access token corto + refresh rotativo; claims: `sub, rol, odontologo_id?`; RBAC de `03_actores_y_roles.md` exigido en cada endpoint (decorador + tests).
- Tokens de acción por mail (confirmar/cancelar, mis-turnos): JWT separados de corta vida + un solo uso (hash consumido en DB).
- Webhook MP: validación de firma con secreto; rate-limit en rutas públicas; DNI nunca como único factor (token al mail).
- Secretos solo por env vars; nada hardcodeado; `password_hash` con algoritmo moderno + salt.

## 4. Variables de entorno (lista mínima)

`DATABASE_URL, REDIS_URL, JWT_SECRET, JWT_ACCESS_MIN, MP_ACCESS_TOKEN, MP_WEBHOOK_SECRET, MP_PUBLIC_KEY, SMTP_HOST/PORT/USER/PASS, MAIL_FROM, SPF/DKIM/DMARC_* (docs del dominio), RECORDATORIO_VENTANA_HS, RESERVA_TTL_MIN, FRONTEND_URL, PRECIOS_PUBLICOS_JSON, WHATSAPP_ENABLED=false [v2], ARCA_ENABLED=false [v2]`.

## 5. Docker Compose (dev)

Servicios: `api (FastAPI), web (Vite dev), db (PostgreSQL + pgcrypto), redis, mailhog (mail local), worker (mails/scheduler)`. Volúmenes para pgdata; healthchecks; `seed` con los datos de `04_modelo_de_datos.md` §5.

## 6. Mail: SPF/DKIM/DMARC a nivel config [v1]

- El dominio del consultorio publica SPF (incluye al SMTP), DKIM (firma con selector) y DMARC (`p=quarantine/reject` + `rua`).
- La app envía solo desde `MAIL_FROM` alineado; plantillas versionadas (`recordatorio_mail.plantilla_version`); métricas de rebote visibles; si falla la alineación, el worker marca `fallido` en vez de reintentar infinitamente.
- Inbound (confirmar/cancelar desde el mail): links con token (no reply-parse en v1).

## 7. Cumplimiento técnico [v1]

Cifrado en tránsito (TLS) + cifrado declarado de sensibles en reposo; backups periódicos de PostgreSQL con prueba de restore; retención por job; consentimiento obligatorio (RN-CONSENTIMIENTO); exportación CSV/PDF solo roles autorizados.
