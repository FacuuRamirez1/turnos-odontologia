# Guion de Video y Guía de Demostración — TPI Metodología I (≤ 10 minutos)

> Diseñado para **4 integrantes** (`maaaattttiiii`, `FacuuRamirez1`, `FacundoDeseff`, `Santino`).
> Alcance actual del repositorio: **12 changes archivados y verificados** (`C-01` a `C-11` + `C-07F`), superando holgadamente el mínimo grupal (`2 × 4 = 8`). Quedan explícitamente como **pendientes** (`[ ]`) en [CHANGES.md](../../CHANGES.md) y [README.md](../../README.md): **`C-12` (`reportes-exportaciones`)** y **`C-13` (`hardening-cumplimiento-cierre`)**.

---

## 1. Preparación previa ANTES de grabar (hacer en frío)

1. **Verificar variables y entorno** (sin mostrar secretos ni `.env` reales en pantalla, regla `P5`):
   ```bash
   cp .env.example .env   # confirmar PAGO_MODO=simulado, WHATSAPP_ENABLED=false, ARCA_ENABLED=false
   docker compose up -d --build
   ```
2. **Aplicar migraciones hasta el head `006_devolucion_comprobante` y cargar seed ficticio**:
   ```bash
   cd backend
   python -m alembic upgrade head
   python -m app.infra.db.seed_dev
   ```
3. **Verificar servicios levantados antes de apretar REC**:
   - API + Swagger: `http://localhost:8000/api/health` y `http://localhost:8000/docs`
   - Frontend SPA: `http://localhost:5173`
   - MailHog (bandeja de mails local): `http://localhost:8025`
4. **Credenciales y datos ficticios listos en un bloc (P11)**:
   - **Password único de dev**: `dev-ficticio-123`
   - **Odontólogo 1**: `odonto1@clinica-ficticia.example.ar` · UUID: `11111111-1111-4111-8111-111111111111`
   - **Odontólogo 2**: `odonto2@clinica-ficticia.example.ar` · UUID: `22222222-2222-4222-8222-222222222222`
   - **Recepcionista**: `recep@clinica-ficticia.example.ar`
   - **Admin**: `admin@clinica-ficticia.example.ar`
   - **DNIs ficticios para reservar en vivo**: usar cualquier DNI de 8 dígitos ficticio, ej. `99999911` o `30111222`.
5. **Terminales listas (fuente grande, sin claves visibles)**:
   - Terminal 1: `cd backend && python -m pytest app/tests -q` (para correr en vivo en el bloque 6:00).
   - Terminal 2: `npm --prefix frontend run test` y `npm --prefix frontend run build` (para correr en vivo en el bloque 6:00).

---

## 2. Guion minuto a minuto (4 integrantes, máximo 10:00)

### Bloque 1 (`0:00 – 0:30`) · Presentación y alcance — **Integrante 1**
*(Cámara encendida mirando al frente al presentarse)*
- **En pantalla**: diapositiva de portada o `README.md` + `CHANGES.md` abierto en el árbol de dependencias.
- **Qué decir**:
  - *"Hola, somos [Nombres de los 4 integrantes], comisión [C?]. Presentamos el sistema web de turnos odontológicos single-sede en modo v1."*
  - *"De un roadmap de 13 changes, completamos, verificamos y archivamos **12 changes** (`C-01` a `C-11` más `C-07F`), superando el mínimo de 8 para 4 integrantes. Quedan explícitamente pendientes `C-12` (reportes/exportaciones) y `C-13` (hardening y cierre)."*

---

### Bloque 2 (`0:30 – 3:00`) · Recorrido por los changes y flujo SDD — **Integrante 2**
- **En pantalla**: mostrar rápidamente `CHANGES.md`, la carpeta `openspec/changes/archive/` (`12` carpetas cerradas) y `git log --oneline -15` (mostrando commits propios de los 4 integrantes, `P7`).
- **Qué mostrar y explicar (con palabras propias, sin leer código línea por línea)**:
  1. **Base de datos y reglas duras (`C-01` a `C-06`)**: *"Aislamos la agenda por rol en backend (`P8`), garantizamos no doble-reserva y no-solapamiento directo como constraints en PostgreSQL (`RN-DOBLE`, `RN-SOLAPE`) y consentimiento bloqueante (`RN-CONSENTIMIENTO`)."*
  2. **Pagos simulados + devoluciones + mails (`C-07`, `C-08`, `C-09`)**: *"Por decisión de diseño `D14`, en MVP la seña usa `PAGO_MODO=simulado` detrás de un puerto/adaptador: el frontend nunca confirma pagos (`P10`), todo entra firmado HMAC por `POST /api/webhooks/mercadopago` con idempotencia, y en `C-08` sumamos devoluciones manuales 100 % / 60 %, recibos PDF y avisos por MailHog."*
  3. **Frontend público y backoffice (`C-10` y `C-11`)**: *"Hoy sumamos toda la SPA pública de reserva/checkout/autogestión y el backoffice completo de agenda y bandeja de devoluciones."*

---

### Bloque 3 (`3:00 – 6:00`) · Skill propia y MCP Context7 con evidencia real — **Integrante 3**
- **En pantalla**: mostrar `SKILL.md` (`.agents/skills/validador-escenarios-turnos/SKILL.md`), `AGENTS.md`, `opencode.json`, y abrir las evidencias reales en `docs/skills-mcp/evidencias/` (`skill-validador-ejecucion.md`, `skill-c08-propose.md`, `skill-c11-propose.md`, `mcp-c08-apply.md`, `mcp-c10-apply.md`, `mcp-c11-apply.md`).
- **Qué explicar (obligatorio por rúbrica del TPI)**:
  1. **Skill propia (`validador-escenarios-turnos`)**:
     - *"La creamos con `skill-creator` y la integramos en `.atl/skill-registry.md` y `AGENTS.md`/`CLAUDE.md` para auditar escenarios SDD contra las 9 reglas `RN-*` y 3 escenarios obligatorios (feliz, error de negocio, borde)."*
     - **Caso concreto Antes vs. Después**: *"En `C-10` el borrador inicial dejaba consultar `/mis-turnos` solo con DNI (`❌`), violando `P12`, y omitía bloquear `consentimiento_datos = false`. Y en `C-11` detectamos en el apply que `StatusBadge` mostraba 'Desconocido' para estados de devolución (`pendiente`/`aprobada`) y lo corregimos verificándolo en `BandejaPage.test.tsx`."*
  2. **MCP (`@upstash/context7-mcp`)**:
     - *"Conectado por `stdio` en `opencode.json` en solo lectura y sin secretos (`P5`)."*
     - **Caso concreto Antes vs. Después**: *"Cuando consultamos `useSearchParams` de `react-router`, Context7 devolvió un snippet de v7 importando desde `"react-router"`, pero nuestro `package.json` fija `react-router-dom@6.28.0`. Contrastar eso evitó errores de compilación en `C-10` y `C-11`. También lo usamos en `C-08` para `Response` binaria de PDF en FastAPI y `ConfigDict(extra='forbid')` en Pydantic v2, y en el apply de `C-10` descubrimos que `CheckoutSimuladoPage` consultaba `GET /api/pagos/{id}` (staff-only) y lo corregimos."*

---

### Bloque 4 (`6:00 – 10:00`) · Tests en vivo + Sistema funcionando E2E — **Integrante 4** *(y cierre grupal)*

#### Parte 4A (`6:00 – 7:00`) — Tests automatizados en vivo
- Mostrar Terminal 1 y Terminal 2:
  1. `cd backend && python -m pytest app/tests -q` → mostrar **`483 passed`** (mencionar tests adversos de migración `006` y `test_f2_devolucion_e2e.py`).
  2. `npm --prefix frontend run test` → mostrar **`10 test files, 51 passed`** + `npm --prefix frontend run build` en verde (`tsc --noEmit && vite build`).

#### Parte 4B (`7:00 – 10:00`) — Demo en vivo en el navegador (`http://localhost:5173`)
Seguir **este orden exacto** (flujo completo sin cortes):
1. **`/precios`** (`C-10`, D11): mostrar aranceles públicos por profesional, condiciones de trial sin tarjeta y badge **`(simulado)`** sin estar logueado.
2. **`/reservar` → `/checkout-simulado`** (`C-10` + `C-07`, D14):
   - Paso 1: cargar DNI ficticio (`30111222`), nombre/apellido/email ficticios; mostrar que **si no tildás consentimiento no te deja avanzar** (`RN-CONSENTIMIENTO` / `P11`), luego aceptar.
   - Paso 2–4: elegir odontólogo (`11111111-...`), fecha futura y horario libre, mostrar monto total + seña + badge **`(simulado)`**, y confirmar.
   - Redirige a `/checkout-simulado?pago_id=...&token=...`: señalar leyenda *"SIMULADO — sin valor fiscal ni movimiento de dinero"*, hacer clic en **Aprobar** → el backend dispara el webhook HMAC y confirma el turno.
3. **`/mis-turnos` o `/agenda` Staff (`C-07F` + `C-11`)**:
   - Mostrar `/mis-turnos` bloqueando consulta **solo con DNI sin token** (`P12`).
   - Entrar a `/login` como **odontólogo** (`odonto1@clinica-ficticia.example.ar` / `dev-ficticio-123`): mostrar que su UUID viene fijo (solo lectura, `P8`) y que **la reserva telefónica está bloqueada para ese rol**.
   - Cerrar sesión e iniciar sesión como **recepcionista** (`recep@clinica-ficticia.example.ar` / `dev-ficticio-123`):
     - Pegar UUID `11111111-1111-4111-8111-111111111111`, abrir **Disponibilidad y bloqueos** y **Reserva telefónica (Q10)**.
     - Sobre el turno recién reservado: abrir **Ficha de paciente** (contacto + historial) y **Ver trazabilidad** (`evento_pago` + historial con actor y fecha, `P9`).
     - Hacer clic en **Cancelar** (mostrar cotización `100 %` antes de confirmar + motivo) y confirmar.
4. **`/bandeja` (`C-08` + `C-11`) + PDF + MailHog**:
   - Ir a **Bandeja de devoluciones** (`/bandeja`), mostrar banner **`(simulado)`** y la devolución generada en `pendiente`.
   - Clic en **Aprobar devolución** → ingresar `monto_confirmado` exacto (`Q4`) → luego **Ejecutar devolución** (`sim_refund_...` simulado).
   - Abrir **Ver trazabilidad** → descargar el **recibo PDF (`Descargar PDF ...`)** y mostrar brevemente MailHog (`http://localhost:8025`) con el mail enviado (y recordar que `C-12` reportes/exportaciones y `C-13` hardening quedan como pendientes).

---

## 3. Archivo `.txt` final de entrega en el campus

Crear y subir en **Entrega TPI** un único archivo llamado **`TPI-C?-Apellido1-Apellido2-Apellido3-Apellido4.txt`** (reemplazando `C?` por `C1`, `C3` o `C4` y los apellidos reales del grupo):

```text
ENTREGA — TPI METODOLOGÍA I
Comisión: <1, 3 o 4>
Video explicativo: <link público con permisos verificados>
Repositorio del proyecto: https://github.com/FacuuRamirez1/turnos-odontologia
Cantidad de integrantes: 4
Integrantes:
1. <Nombre y Apellido — commit author en main>
2. <Nombre y Apellido — commit author en main>
3. <Nombre y Apellido — commit author en main>
4. <Nombre y Apellido — commit author en main>
```

> **Chequeo final antes de subir**: verificar en modo incógnito que tanto el link de GitHub como el link del video abran sin pedir permisos privados, y que los 4 integrantes aparezcan en `git log --format="%an <%ae>" | sort -u`.
