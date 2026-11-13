# Ficha de Investigación — Integración de Skill Propia y Servidor MCP

- **Materia**: Metodología I — Tecnicatura Universitaria en Programación (UTN)
- **Proyecto**: `turnos-odontologia` (sistema web single-sede de gestión odontológica)
- **Fecha de elaboración**: 2026-11-13
- **Change objetivo**: `C-10` (`frontend-reserva-publica`)

---

## 1. Necesidad real detectada y change elegido

De acuerdo con [CHANGES.md](../../CHANGES.md), `C-10` (`frontend-reserva-publica`) depende únicamente de `C-05` (`reserva-turnos-estados`) y `C-07` (`pagos-mp-checkout-webhook`, modo simulado D14), ambos ya implementados, verificados y archivados en `openspec/changes/archive/`. Por lo tanto, `C-10` puede prepararse con Spec-Driven Development sin depender de funcionalidades todavía inexistentes.

- **Tarea repetible resuelta por la Skill (`validador-escenarios-turnos`)**: al preparar cambios sobre reservas y pagos simulados, resulta propenso a errores verificar manualmente que los tres escenarios SDD obligatorios (esperado, error de negocio y borde) cubran las reglas de dominio de `knowledge-base/05_reglas_de_negocio.md` y `11_pagos_mercadopago.md` (`RN-DOBLE`, `RN-SOLAPE`, `RN-LIBERACION`, `RN-PASADO`, `RN-ANTICIPACION`, `RN-SENIA-PAGO`, `RN-PAGO-SIMULADO`, `RN-ESTADOS`, `RN-CONSENTIMIENTO`) y las reglas duras del proyecto (`P1`, `P10`, `P11`, `P12`, `P15`). Una skill dedicada estandariza esa auditoría antes de pasar a implementar.
- **Necesidad de información resuelta por el MCP (`Context7 MCP`)**: `C-10` construye una SPA en React `18.3.1` + TypeScript `5.6.3` + `react-router-dom` `6.28.0` + Vite `6.0.3` (rutas públicas de reserva en 3–4 pasos, `/mail/confirmar`, `/mail/cancelar`, `/mis-turnos` con token, checkout simulado). Contar con documentación oficial y versionada directamente en el contexto del agente evita APIs obsoletas o incompatibles con React Router v6 / React 18 al redactar `design.md` y `tasks.md`.
- **Sinergia para preparar `C-10`**: el MCP aporta certeza técnica actualizada de las librerías frontend para el diseño arquitectónico, mientras la skill audita la fidelidad clínica y de negocio de las especificaciones SDD.

---

## 2. Skill creadora y diseño de la skill propia

- **Skill creadora**: `skill-creator` — fuente oficial [`anthropics/skills`](https://github.com/anthropics/skills/tree/main/skills/skill-creator). Es compatible con el estándar Agent Skills (`SKILL.md` con frontmatter YAML `name` + `description`) utilizado por **OpenCode**, **Claude Code** y **Antigravity**.
- **Instalación, comprobación y generación**: siguiendo la regla dura **U3** (prohibido instalar globalmente con `-g`), toda skill del proyecto reside en `.agents/skills/` y se indexa en `.atl/skill-registry.md`. La creación base de `validador-escenarios-turnos` ya fue realizada y versionada por el equipo (commit `cc56b86`), comprobándose su disponibilidad en `.agents/skills/validador-escenarios-turnos/SKILL.md`.
- **Diseño de la skill propia (`validador-escenarios-turnos`)**:
  - **Ubicación**: `.agents/skills/validador-escenarios-turnos/SKILL.md` (referenciada en `.atl/skill-registry.md`, `AGENTS.md` y `CLAUDE.md`).
  - **Propósito**: revisar escenarios SDD de reserva pública (`C-10`) y detectar reglas faltantes, violaciones de contrato (`P10`/`P15`) o ambigüedades antes de implementar código. No escribe código de aplicación.
  - **Cuándo se activa**: ante pedidos como *"Valida los escenarios SDD para C-10"* o durante la revisión de `proposal.md`, `specs/` y `tasks.md` del change.
  - **Entradas necesarias**: texto de los escenarios propuestos + lectura de `knowledge-base/` (`04`, `05`, `06`, `07`, `10`, `11`).
  - **Procedimiento**: (1) cargar las 9 reglas `RN-*`; (2) verificar presencia de los 3 escenarios mínimos (esperado, error de negocio, borde); (3) contrastar cada escenario contra las reglas y el flujo `PAGO_MODO=simulado`; (4) relevar bordes y preguntas abiertas (`Q1`, `Q3`, `Q4`); (5) emitir veredicto (`✅ Aprobado` / `❌ Reglas vulneradas`).
  - **Resultado esperado y criterios de revisión**: reporte Markdown estructurado que evalúe explícitamente al menos 6 de las reglas listadas, cite casos de borde propios del dominio odontológico (no genéricos), no invente respuestas a `Q1`/`Q3`/`Q4` y, en caso de rechazo, incluya correcciones accionables.

---

## 3. Comparación de servidores MCP y elección justificada

| Criterio | Context7 MCP (`@upstash/context7-mcp`) | PostgreSQL MCP (`@modelcontextprotocol/server-postgres`) |
|---|---|---|
| **Propósito** | Recuperar documentación oficial y ejemplos actualizados por librería y versión. | Inspeccionar esquemas y ejecutar consultas SQL sobre PostgreSQL. |
| **Capacidades / Tools** | `resolve-library-id` (resuelve nombre → ID) y `query-docs` (antes `get-library-docs`, consulta snippets por tópico). | `query` (consultas SQL de solo lectura) y recursos de introspección de tablas/columnas. |
| **Compatibilidad** | Transporte estándar `stdio` compatible con OpenCode, Antigravity, Claude Code y VS Code. | Transporte `stdio` compatible con clientes MCP estándar. |
| **Instalación / Requisitos** | Node.js (ya requerido por frontend: `v24.16.0` instalado; mínimo repo v20) vía `npx -y @upstash/context7-mcp`. | Node.js + instancia PostgreSQL activa (`docker compose up -d db`) con migraciones aplicadas. |
| **Permisos / Credenciales** | Solo lectura HTTP a documentación pública. Sin secretos obligatorios (`CONTEXT7_API_KEY` opcional para mayor cuota). | Requiere cadena `DATABASE_URL` con credenciales locales (riesgo de exposición si no se aísla bien, P5). |
| **Costo y mantenimiento** | Gratuito (uso estándar sin clave o tier free); paquete activamente mantenido por Upstash. | Gratuito; el paquete oficial `@modelcontextprotocol/server-postgres` figura archivado como referencia en `modelcontextprotocol/servers-archived`. |

- **Elección justificada**: se selecciona **`@upstash/context7-mcp` (Context7 MCP)**. `C-10` es un change puramente de **frontend** sobre endpoints ya existentes y cerrados (`C-04`, `C-05`, `C-07`, `C-09`), sin cambios de base de datos ni migraciones Alembic. Context7 aporta directamente a diseñar el enrutado y manejo de estado en React + React Router v6, no requiere levantar contenedores Docker ni manipular credenciales `DATABASE_URL`, y resulta 100 % reproducible por cualquier integrante del equipo.
- **Configuración reproducible y verificación**:
  1. **Prerrequisitos**: Node.js `>= 20` (`npm`/`npx` disponibles) y acceso a internet para descargar documentación pública.
  2. **Configuración en OpenCode (`opencode.json` en raíz o global, sin secretos)**:
     ```json
     {
       "$schema": "https://opencode.ai/config.json",
       "mcp": {
         "context7": {
           "type": "local",
           "command": ["npx", "-y", "@upstash/context7-mcp"],
           "enabled": true
         }
       }
     }
     ```
     *(Nota: para clientes estándar tipo `mcpServers` como Claude Desktop/Antigravity, se declara `"command": "npx", "args": ["-y", "@upstash/context7-mcp"]`. Si se utiliza cuota ampliada, pasar `CONTEXT7_API_KEY` solo vía variable de entorno `{env:CONTEXT7_API_KEY}`, nunca en texto plano).*
  3. **Comprobación de conexión y herramienta real**: iniciar el cliente MCP, verificar que el servidor `context7` figure habilitado con sus 2 tools, ejecutar `resolve-library-id` con `libraryName: "react-router"` y luego `query-docs` con el ID resuelto (ej. consulta sobre `useSearchParams` / rutas v6).
- **Límites de acceso y datos de prueba**: acceso **únicamente de solo lectura** a documentación pública de librerías open source; el servidor no tiene acceso a archivos locales del repositorio, variables `.env`, PostgreSQL ni Redis (**P5**). Para todo ejemplo o escenario generado en `C-10` se usan exclusivamente DNI ficticios del seed dev (**P11**).

---

## 4. Archivos de la fundación previstos para actualizar (Parte 2)

1. `.agents/skills/validador-escenarios-turnos/SKILL.md`: incorporar frontmatter YAML (`name`, `description`) requerido por Agent Skills y corregir detalle de consistencia (cantidad exacta de reglas `RN-*` en criterios de revisión).
2. `.atl/skill-registry.md`: verificar registro actualizado de `validador-escenarios-turnos` e indexar `AGENTS.md`/`CLAUDE.md`.
3. `AGENTS.md` y `CLAUDE.md`: documentar en ambos de forma sincronizada cuándo usar `validador-escenarios-turnos` y documentar `Context7 MCP` como **integración** (propósito, herramientas, momento de uso y límites; nunca registrado como skill).
4. `README.md` y archivo de ejemplo `opencode.json` (sin secretos): documentar prerrequisitos, configuración reproducible del MCP, comprobación y troubleshooting.
5. `CHANGES.md` y `openspec/changes/c-10-frontend-reserva-publica/`: preparar `proposal.md`, `design.md`, `specs/frontend-reserva-publica/spec.md` (3 escenarios verificables) y `tasks.md` sin marcar como implementado ni archivado.

---

## 5. Estado de verificación y fuentes consultadas

- **Pendiente para Parte 2** (no ejecutado aún en esta etapa de investigación): comprobación en vivo de `resolve-library-id` + `query-docs` sobre `@upstash/context7-mcp`, prueba de activación de `validador-escenarios-turnos` en sesión nueva y redacción de `docs/skills-mcp/aplicacion.md`.
- **Fuentes (fecha de consulta: 2026-11-13)**:
  - Anthropic Agent Skills & `skill-creator`: `https://github.com/anthropics/skills` y `https://skills.sh/`
  - Upstash Context7 MCP (`@upstash/context7-mcp`): `https://github.com/upstash/context7` y `https://www.npmjs.com/package/@upstash/context7-mcp`
  - Model Context Protocol PostgreSQL Server (archivado): `https://www.npmjs.com/package/@modelcontextprotocol/server-postgres` y `https://github.com/modelcontextprotocol/servers-archived/tree/main/src/postgres`
  - Documentación MCP de OpenCode: `https://opencode.ai/docs/mcp-servers`
