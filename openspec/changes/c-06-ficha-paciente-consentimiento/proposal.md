# Proposal

## Why

La reserva (C-05) y la agenda backoffice (C-11) necesitan una ficha de paciente mínima con identidad por DNI y consentimiento bloqueante, pero hoy solo existe la persistencia (`core-models-usuarios-pacientes`: UNIQUE DNI + CHECK consentimiento) sin API, sin reconocimiento con precarga (A2) y sin historial acotado visible por rol (F1). Sin este change, `POST /reservas` no puede exigir RN-CONSENTIMIENTO con error explícito ni precargar datos existentes.

## What Changes

- CRUD ficha mínima de paciente: `dni` (UNIQUE, solo dígitos 7–8, validación formato AR), `nombre`, `apellido`, `email`, `telefono`, `consentimiento_datos` (bool) + `consentimiento_fecha` (timestamp). Alta manual staff y alta implícita desde reserva comparten el mismo gate de consentimiento.
- RN-CONSENTIMIENTO enforced en dos puntos: alta manual (`POST /pacientes`) y creación implícita desde `POST /reservas` (contrato que C-05 debe honrar): sin `consentimiento=true` + fecha, rechazo explícito 422 `CONSENTIMIENTO_REQUERIDO`, no se persiste nada.
- `GET /pacientes?dni=` reconocimiento con precarga (A2): match exacto por DNI normalizado devuelve ficha mínima para precargar el flujo de reserva; sin match devuelve 200 vacío (no 404, para no filtrar existencia de forma distinta al flujo feliz — decisión: respuesta uniforme).
- Historial de turnos acotado por paciente: `GET /pacientes/{id}/turnos` devuelve pasados + futuros con campos `{turno_id, odontologo_id, inicio, fin, estado}` — SIN nada clínico (no hay campos clínicos en v1; garantía explícita por schema de respuesta cerrado `extra='forbid'`).
- Visibilidad por rol (decisión no-obvia, governance MEDIO — explicitada en design):
  - `odontologo` / `recepcionista|admin`: ven fichas (contacto + historial acotado). Odontólogo ve contacto completo (necesita contactar a sus pacientes); recepcionista ve todas.
  - `paciente` (no autenticado JWT): solo la propia vía token de acción mail (seam C-03 action-tokens) en `GET /mis-turnos`-equivalente; nunca lista ni busca por DNI ajeno; `GET /pacientes?dni=` y CRUD exigen JWT staff.
  - Exportación (CSV/PDF) fuera de alcance: solo roles autorizados la usarán en C-12; este change expone los mismos filtros pero no el formato export.
- Sin cambios de schema de tabla `paciente` (ya existe desde C-02); este change solo agrega API + enforcement + índices de lectura si faltan (índice parcial active + DNI normalizado vía migración versionada si se necesita, nunca `create_all`).

## Capabilities

### New Capabilities

- `ficha-paciente-consentimiento`: ficha mínima + gate RN-CONSENTIMIENTO + reconocimiento por DNI (A2) + historial acotado no-clínico (F1) con RBAC por rol. Cada requisito futuro de datos de paciente (retención RN-RETENCION en C-13, exportación en C-12) extiende esta capability.

### Modified Capabilities

- Ninguna. Se reutilizan sin cambiar: `core-models-usuarios-pacientes` (persistencia + UNIQUE DNI + CHECK consentimiento ya existen) y `auth-jwt-rbac` (seams `require_role()`, action-tokens base, matriz 03 §2). Este change no altera sus REQUIREMENTS, solo los consume.

## Impact

- Nuevo router `backend/app/api/pacientes.py` + schemas Pydantic v2 (`extra='forbid'`) + servicio `PacienteService` con gate de consentimiento + repositorio con soft-delete (respeta `is_active`).
- Contrato hacia C-05: `POST /reservas` debe propagar `CONSENTIMIENTO_REQUERIDO` (422) cuando falta consentimiento; documentado como dependencia de interfaz, no como código de C-05.
- Sin colisión con C-04 (disponibilidad-slots, propuesto en paralelo por otro agente): archivos disjuntos (`pacientes*` vs `disponibilidad*/bloqueo*`); único punto de contacto futuro es C-05 que consume ambos. Verificado: `openspec list` muestra 0 changes activos al crear este change.
- Tests: TDD 3 escenarios (U2) — bloqueo sin consentimiento, reconocimiento por DNI, visibilidad acotada por rol; solo DNI ficticios en seeds/tests (P11).
