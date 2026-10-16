# Design

## Context

Ver `proposal.md` (Why). Estado actual: tabla `paciente` existe desde C-02 (migración 001) con `UNIQUE(dni)` + CHECK de consentimiento a nivel persistencia; no hay API. Seams reutilizables de C-03 (archivado): `require_role()`, filtro `odontologo_id` en repositorio, action-tokens mail (JWT separados, un uso, vida corta), rate-limit Redis, error envelope. Tabla `turno` aún no existe (la crea C-05); el historial acotado debe diseñarse contra su contrato futuro sin acoplarse a su implementación.

## Goals / Non-Goals

**Goals:**

- API mínima de ficha + gate RN-CONSENTIMIENTO en servicio (no solo DB) con error explícito reutilizable por C-05.
- Reconocimiento A2 y historial acotado con schemas cerrados que garanticen "sin nada clínico".
- RBAC por rol explicitado y testeable por rol.

**Non-Goals:**

- Ningún cambio de tabla `paciente` (si se necesita índice de lectura, migración versionada aparte, nunca `create_all` — P3).
- Nada clínico / odontograma (F5 es v2, excluido por diseño de schema).
- Exportación CSV/PDF (C-12 la consume; aquí solo filtros de lectura).
- Reserva, pagos, mails (C-05/C-07/C-09): este change solo publica el contrato `CONSENTIMIENTO_REQUERIDO` que ellos honran.

## Decisions

1. **Gate de consentimiento en capa servicio (`PacienteService`), no solo CHECK DB.**
   Rationale: el CHECK DB es última defensa pero devuelve error genérico; el servicio valida `consentimiento_datos is true AND consentimiento_fecha is not null` antes de persistir y devuelve 422 `CONSENTIMIENTO_REQUERIDO` con mensaje explícito. Alternativa (solo DB): descartada, error 500-ish e inconsistente con el envelope.
   `POST /reservas` (C-05) llama al mismo `PacienteService.resolve_or_create()`; si falla, aborta la UoW completa (ni paciente ni turno). Contrato documentado en spec, no código de C-05 aquí.

2. **"Historial acotado" = `{turno_id, odontologo_id, inicio, fin, estado}` pasado+futuro, ordenado por `inicio`, paginado por keyset.**
   Rationale (decisión no-obvia, governance MEDIO): pasados para contexto de asistencia + futuros para gestión; se excluyen `motivo`, `actor`, notas (no existen campos clínicos en v1, pero el schema cerrado lo garantiza por construcción). Keyset sobre `(inicio, id)` en vez de OFFSET (tabla crece; convención Postgres del registry). Alternativa (todo el turno): descartada, expondría canal/idempotency y futuros campos sensibles.

3. **Lectura de historial contra vista de contrato, no contra modelo C-05.**
   El endpoint hace `SELECT turno.id, odontologo_id, inicio, fin, estado WHERE paciente_id AND is_active` — solo columnas del contrato. Si C-05 agrega columnas, este endpoint no las expone salvo change explícito. Turnos `cancelado/devuelto` se incluyen (siguen siendo historial); filtro por estado es opt-in por query param.

4. **Reconocimiento `GET /pacientes?dni=` devuelve 200 vacío si no hay match (no 404).**
   Rationale: el flujo A2 llama en cada reserva; 404 vs 200 distinguiría existencia y complicaría el frontend (dos caminos de error). Respuesta uniforme `{found: bool, paciente: {...} | null}`. DNI se normaliza (quitar `.`/espacios) antes de buscar. Búsqueda exacta únicamente — sin LIKE parcial (evita enumeración).

5. **Paciente sin JWT: solo vía action-token mail (seam C-03), scope `paciente_id` обязаны.**
   El token porta `paciente_id`; el handler lo compara con el `{id}` pedido — mismatch → 403. Tokens son un uso + vida corta + hash consumido en servidor (heredado de C-03, no reimplementar). `GET /pacientes?dni=` y CRUD quedan staff-only (`require_role('odontologo','recepcionista','admin')`).

6. **Odontólogo ve contacto completo de fichas (no solo las de sus turnos).**
   Rationale (decisión no-obvia): necesita contactar pacientes para reprogramar; el aislamiento RN-AISLAMIENTO aplica a agendas/turnos, no a la ficha de contacto (matriz 03 §2: recepcionista "ver fichas mínimas" sin restricción por profesional; odontólogo hereda al absorber funciones sin recepcionista — 03 §R2). El aislamiento por profesional se enforcea en el historial vía JOIN turno→odontólogo cuando el rol es odontólogo? Decisión: NO filtrar historial por odontólogo (el paciente puede tener turnos con varios profesionales; ocultar parciales rompería "historial acotado" completo). Registrar como supuesto explícito para revisión.

7. **Sin migración en este change salvo índice de lectura.**
   `UNIQUE(dni)` ya indexa el reconocimiento. Si EXPLAIN muestra seq-scan por `is_active + dni`, migración `00N` con índice parcial — versionada Alembic, P3 intacto. Secreto JWT y demás por env (P5); sin secretos nuevos.

## Risks / Trade-offs

- [Risk] C-05 interpreta distinto `CONSENTIMIENTO_REQUERIDO` (p. ej. lo convierte en 400 genérico) → Mitigación: código de error + schema documentados en spec + test de contrato listado en tasks que C-05 debe pasar.
- [Risk] Historial sin filtrar por odontólogo expone a odontólogo turnos con colegas → Mitigación: supuesto explícito arriba; si revisión lo rechaza, agregar filtro `?odontologo_id` opt-in sin romper el default (tarea marcada opcional en tasks).
- [Risk] Normalización DNI diverge entre alta y búsqueda (dobles registros `30123456` vs `30.123.456`) → Mitigación: normalizar en un único helper + CHECK de formato en servicio + test de borde con puntos/espacios.
- [Risk] Condición de carrera: dos altas simultáneas mismo DNI → Mitigación: `UNIQUE(dni)` DB como árbitro + manejo 409; servicio no intenta "check-then-insert" sin capturar integridad.
- [Trade-off] 200 vacío vs 404: se pierde semántica HTTP canónica a cambio de flujo A2 simple y sin oracle de existencia diferenciado.

## Migration Plan

- Deploy: solo código (router + servicio + schemas + tests). Sin migración de datos esperada.
- Si se agrega índice: `alembic upgrade head` estándar; rollback `downgrade -1` (índice drop, sin pérdida).
- Rollback de código seguro: endpoints nuevos, sin modificar rutas existentes.

## Open Questions

- Ninguna bloqueante. Revisión abierta (no cambia specs/tasks): ¿filtrar historial por `odontologo_id` para rol odontólogo? Default propuesto: no filtrar; tarea opcional preparada.
