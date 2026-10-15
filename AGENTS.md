# turnos-odontología — Instrucciones para Agentes

> Este archivo (y su copia `CLAUDE.md`) es lo PRIMERO que todo agente lee al entrar al repo.
> Generado a partir de `knowledge-base/` y `CHANGES.md`. No editar a mano sin re-sincronizar ambos archivos.

---

## Stack Tecnológico

| Capa | Tecnología |
|------|------------|
| Backend | Python + FastAPI (Pydantic v2, request/response models en todo endpoint) |
| Auth | JWT (access + refresh) |
| ORM / Migraciones | SQLAlchemy + Alembic (cero `create_all` en runtime) |
| DB | PostgreSQL (constraints de dominio: unicidad de slot, no-solapamiento) |
| Async/colas | Redis (mails, reintentos, ventana de recordatorios, idempotencia) |
| Infra | Docker / Docker Compose |
| Frontend | React + TypeScript estricto + Vite (componentes en PascalCase, prohibido `any`) |
| Pagos [v1] | MercadoPago (checkout + webhooks + devoluciones; solo server-to-server) |
| Mail [v1] | SMTP con SPF/DKIM/DMARC, solo desde `MAIL_FROM` alineado, vía workers Redis |

Detalle completo: [knowledge-base/02_descripcion_general.md](knowledge-base/02_descripcion_general.md)

---

## Base de Conocimiento

La fuente de verdad del dominio vive en `knowledge-base/`. **Leé el archivo relevante ANTES de implementar.**

| Archivo | Cuándo leerlo |
|---------|---------------|
| [01_vision_y_objetivos.md](knowledge-base/01_vision_y_objetivos.md) | Propósito, alcance v1/v2 |
| [02_descripcion_general.md](knowledge-base/02_descripcion_general.md) | Stack, arquitectura, integraciones |
| [03_actores_y_roles.md](knowledge-base/03_actores_y_roles.md) | Auth, RBAC, rutas públicas (6) |
| [04_modelo_de_datos.md](knowledge-base/04_modelo_de_datos.md) | Entidades, ERD, seeds (DNI ficticios) |
| [05_reglas_de_negocio.md](knowledge-base/05_reglas_de_negocio.md) | Reglas RN-XX + máquina de estados |
| [06_funcionalidades.md](knowledge-base/06_funcionalidades.md) | Épicas A–G, historias |
| [07_flujos_principales.md](knowledge-base/07_flujos_principales.md) | Flujos E2E |
| [08_arquitectura_propuesta.md](knowledge-base/08_arquitectura_propuesta.md) | Patrones, directorios, env vars |
| [09_decisiones_y_supuestos.md](knowledge-base/09_decisiones_y_supuestos.md) | D1–D13 + supuestos |
| [10_preguntas_abiertas.md](knowledge-base/10_preguntas_abiertas.md) | ⚠️ Resolver las Alta ANTES de codear |
| [11_pagos_mercadopago.md](knowledge-base/11_pagos_mercadopago.md) | Checkout, webhooks, idempotencia, devoluciones |

> ⚠️ Resolver las preguntas de prioridad **Alta** de `10_preguntas_abiertas.md` antes de arrancar el primer change.

---

## Skills Disponibles

| Agente | Rol | Skills que carga |
|--------|-----|------------------|
| **Backend Core** | FastAPI, modelos, reglas de dominio | `python-fastapi-development`, `supabase-postgres-best-practices`, `tdd` |
| **Backend Aux** | Auth, pagos, colas, ficha clínica | `auth-implementation-patterns`, `stripe-integration` (análogo webhooks/idempotencia MP), `redis-core`, `healthcare-emr-patterns` |
| **Frontend** | Reserva 3-4 pasos, agenda, UX | `vercel-react-best-practices`, `frontend-design` |
| **Orquestación** | OPSX propone/aplica/archiva | `openspec-propose`, `openspec-explore`, `openspec-apply-change`, `openspec-archive-change`, `openspec-sync-specs`, `openspec-update-change` |

Cargá la skill correspondiente al contexto ANTES de escribir código.

> Los compact rules de cada skill los resuelve el orquestador desde `.atl/skill-registry.md` (generado por `skill-registry`; no versionado — no está en el repo). Esta tabla solo mapea skill→rol.

---

## Roadmap de Changes

El plan completo está en [CHANGES.md](CHANGES.md). Resumen:

- **Total**: 13 changes en 7 fases.
- **Camino crítico** (9): `C-01 → C-02 → C-03 → C-04 → C-05 → C-07 → C-08 → C-11 → C-13`.
- **Primer change**: `C-01-foundation-setup`.

**Antes de cualquier `/opsx:propose`**: leé [CHANGES.md](CHANGES.md), identificá dependencias y archivos de "Leer antes".

---

## Reglas Duras

> No hay `~/.claude/CLAUDE.md` global en este entorno: las reglas universales viven ACÁ (U1–U3). Si un global aparece después, estas prevalecen hasta re-sincronizar.

Universales:
- **U1.** NUNCA commitear ni pushear sin pedido explícito → preguntar siempre antes.
- **U2.** NUNCA producción sin test en rojo primero → TDD RED → GREEN → TRIANGULATE con **3 escenarios** (feliz / error de negocio / borde).
- **U3.** NUNCA instalar skills globales (`-g`) → todo a `.agents/skills/` del proyecto.

Específicas del proyecto (contrato; romperlas es un defecto):
- **P1.** NUNCA `any` en TypeScript → tipado estricto, `tsconfig` strict, componentes en PascalCase.
- **P2.** NUNCA schema Pydantic v2 sin `extra='forbid'` → request/response models en todo endpoint, rechazar campos no declarados.
- **P3.** NUNCA cambiar el schema sin migración Alembic versionada → cero `create_all` en runtime.
- **P4.** NUNCA cobrar ni devolver sin idempotency key → webhooks reintentables sin duplicar plata (ver P10).
- **P5.** NUNCA hardcodear secretos → JWT secret, keys de MP y SMTP solo por env vars documentadas.
- **P6.** NUNCA validar reglas de dominio solo en la app → unicidad de slot y no-solapamiento también como constraints en Postgres.
- **P7.** Commits convencionales (`feat(C-01): ...`, `docs(...)`, `chore(...)`), sin co-autoría de IA, **cada integrante con commits propios** (trazabilidad).
- **P8.** NUNCA permiso solo en UI → RBAC exigible en backend con `require_role()` + `odontologo_id` forzado en repositorio; recepcionista: 6 permisos sí / 4 prohibiciones no.
- **P9.** NUNCA transición sin actor+fecha → máquina cerrada creado→confirmado→atendido/cancelado/reprogramado/no_show→devuelto; `turno_historial`/`evento_pago` append-only, revoke UPDATE/DELETE.
- **P10.** NUNCA confirmar pagos por frontend → solo `POST /webhooks/mercadopago` server-to-server, valida firma `MP_WEBHOOK_SECRET`, persiste `webhook_recibido` con payload crudo, idempotencia por `mp_payment_id` / `mp_refund_id`.
- **P11.** NUNCA dato real de paciente + NUNCA ficha sin consentimiento → solo DNI ficticios; RN-CONSENTIMIENTO bloqueante.
- **P12.** NUNCA ruta pública fuera de lista → solo las 6 de 03 §3, todas con rate-limit; `GET /mis-turnos` exige token, nunca DNI solo; tokens de mail de 1 uso y vida corta.
- **P13.** NUNCA v2 encendido en v1 → `WHATSAPP_ENABLED=false`, `ARCA_ENABLED=false`, lista de espera sin escrituras, sin sobre-turnos, single-sede.
- **P14.** NUNCA fuera de contrato OPSX → leer `CHANGES.md` antes de `/opsx:propose`; en Apply no inventar lo no aprobado en Propose; mail solo desde `MAIL_FROM` alineado vía workers Redis.

---

## Flujo de Trabajo

```
1. Leer la KB relevante (knowledge-base/)        → entender el dominio
2. Identificar el change en CHANGES.md           → respetar dependencias
3. /opsx:propose C-NN-nombre                     → proposal + design + specs + tasks
4. Implementar las tasks (cargando skills)       → respetando las reglas duras
5. /opsx:archive C-NN-nombre + marcar [x]        → cerrar el change
```

Aplicar TODAS las reglas duras en cada paso. Ante conflicto entre la KB y este archivo, las reglas duras prevalecen.
