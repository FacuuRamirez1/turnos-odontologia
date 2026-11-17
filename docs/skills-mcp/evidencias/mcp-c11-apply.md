# Evidencia MCP Context7 + Skill `validador-escenarios-turnos` — apply de `C-11` (`frontend-agenda-backoffice`)

- **Fecha**: 2026-11-17
- **Change**: `C-11` (`frontend-agenda-backoffice`) — fase `/opsx:apply` y auditoría pre-archivo
- **Configuración MCP**: [opencode.json](../../../opencode.json) (`type: "local"`, `npx -y @upstash/context7-mcp`, sin secretos `P5`)
- **Servidor conectado**: `Context7 Documentation MCP Server v4.7.3` (protocolo `2024-11-05`, transporte `stdio`)
- **Versiones reales contrastadas** ([frontend/package.json](../../../frontend/package.json)): `react@18.3.1`, `react-router-dom@6.28.0`, `@testing-library/react@16.3.2`, `vitest@2.1.8`, `typescript@5.6.3`.

---

## 1. Consultas reales a Context7 MCP durante `/opsx:apply`

### Consulta 1 — `react-router-dom`: `NavLink` y callback `isActive` en `AppShell`

- **Solicitud ejecutada**: `query-docs` sobre `/websites/reactrouter` con `query: "NavLink isActive Outlet nested routes v6"`.
- **Extracto real devuelto**:
  ```tsx
  <NavLink
    to="/messages"
    className={({ isActive }) => (isActive ? "active" : "")}
  >
    Messages
  </NavLink>
  ```
- **Aporte concreto**: validó la API oficial de `NavLink` (importado desde `"react-router-dom"` conforme `frontend/package.json` `6.28.0`) y `Outlet` al incorporar la barra de navegación staff (`/agenda` y `/bandeja`) en [AppShell.tsx](../../../frontend/src/components/AppShell.tsx) y la ruta protegida `/bandeja` en [App.tsx](../../../frontend/src/App.tsx).

### Consulta 2 — `@testing-library/react`: `findByRole` y queries asíncronas sobre roles ARIA

- **Solicitud ejecutada**: `query-docs` sobre `/testing-library/react-testing-library` con `query: "waitFor findByRole async testing"`.
- **Extracto real devuelto**:
  ```typescript
  export async function testScreen() {
    render(<button />)
    await screen.findByRole('button')
  }
  ```
- **Aporte y detección en tests**: orientó las aserciones por rol ARIA y selector específico en [BandejaPage.test.tsx](../../../frontend/src/pages/bandeja/BandejaPage.test.tsx) y [AgendaBackoffice.test.tsx](../../../frontend/src/pages/agenda/AgendaBackoffice.test.tsx) (evitando falsos ambiguos cuando textos como `"pendiente"` o `"pausa"` aparecen tanto en `<option>` como en el estado renderizado).

---

## 2. Auditoría de `validador-escenarios-turnos` sobre código y tests de `C-11`

### Defecto detectado durante la implementación TDD (Antes vs. Después)

- **Hallazgo en `BandejaPage.tsx`**: el primer borrador reutilizaba `<StatusBadge estado={item.estado} />` para el estado de la devolución (`pendiente`, `aprobada`, `rechazada`, `ejecutada`). Al correr `BandejaPage.test.tsx`, el DOM mostró `Desconocido` porque `StatusBadge` mapea exclusivamente estados de **turno** (`EstadoTurno`: `creado`, `confirmado`, `atendido`, etc.), no de devolución (`EstadoDevolucion`).
- **Corrección aplicada**: en [BandejaPage.tsx](../../../frontend/src/pages/bandeja/BandejaPage.tsx) se renderiza `<span className={`status-badge status-badge--${item.estado}`}>{item.estado}</span>`, conservando `StatusBadge` únicamente para turnos (`AgendaPage` y `TrazabilidadPanel`). Además se verificó en `BandejaPage.test.tsx` que `"pendiente"` se renderice fielmente sin mutar ante un `422 MONTO_NO_COINCIDE`.

### Veredicto post-apply

```markdown
## Resultado de validación — validador-escenarios-turnos (Post-apply C-11)
**Change**: C-11 frontend-agenda-backoffice
**Fecha**: 2026-11-17
**Validador**: validador-escenarios-turnos

### Veredicto
✅ Aprobado

### Cobertura verificada de reglas y controles RBAC
- RN-DOBLE / RN-SOLAPE: validados orden horario en `DisponibilidadBloqueosPanel` y manejo `409 SLOT_OCUPADO` en reprogramación staff (`AgendaBackoffice.test.tsx`).
- RN-LIBERACION / RN-ANTICIPACION / RN-SENIA-PAGO: `AgendaPage` cotiza antes de cancelar (`cotizarCancelacionStaff`) y muestra aviso `Q3` al reprogramar; `BandejaPage` exige `monto_confirmado` manual (`Q4`, `422 MONTO_NO_COINCIDE`).
- RN-PASADO / RN-CONSENTIMIENTO (`P11`): `ReservaTelefonicaPanel` bloquea fechas pasadas y `consentimiento_datos = false` antes de llamar a `POST /api/reservas/telefonica`.
- RN-PAGO-SIMULADO / RN-ESTADOS (`P8`, `P9`, `P10`, `P15`): banner y badges `"(simulado)"` en `/bandeja`, `TrazabilidadPanel` y comprobantes PDF; `503 PROVEEDOR_NO_DISPONIBLE` sin fallback cliente; formulario telefónico oculto/bloqueado para `odontologo`; `AppShell` sin accesos a usuarios/roles, `PAGO_MODO` ni ARCA.
```
