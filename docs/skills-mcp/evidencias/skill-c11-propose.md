# Evidencia de ejecución de Skill — `validador-escenarios-turnos` en `C-11` (`propose`)

- **Fecha**: 2026-11-17
- **Skill ejecutada**: [SKILL.md](../../../.agents/skills/validador-escenarios-turnos/SKILL.md)
- **Change evaluado**: `C-11` (`frontend-agenda-backoffice`)
- **Fuentes contrastadas**: `knowledge-base/03_actores_y_roles.md` (§1 R2/R3, §2 matriz RBAC), `05_reglas_de_negocio.md`, `06_funcionalidades.md` (§B3, §C, §D2, §F1), `07_flujos_principales.md` (F2, F3), `10_preguntas_abiertas.md` (`Q3`, `Q4`, `Q10`).

---

## 1. Borrador inicial (Antes) y reporte `❌ Reglas vulneradas`

**Solicitud**: *"Valida los escenarios SDD iniciales propuestos para C-11 (`frontend-agenda-backoffice`) antes de implementar."*

**Omisiones detectadas en el Borrador 1**:
1. Permitía mostrar el formulario de **reserva telefónica** (`POST /api/reservas/telefonica`) para cualquier usuario logueado en `/agenda`, olvidando que la matriz RBAC (`03 §2`, `P8`) **prohíbe** esa ruta al rol `odontologo` (solo `recepcionista` y `admin`).
2. En la **bandeja de devoluciones** (`/bandeja`), el escenario de aprobación no exigía confirmar `monto_confirmado` (`422 MONTO_NO_COINCIDE`) ni registraba explícitamente que `Q4` prohíbe auto-aprobar el `60 %`.
3. Faltaba contemplar el borde `503 PROVEEDOR_NO_DISPONIBLE` cuando `PAGO_MODO=mercadopago` (`P13`/`P15`) y el bloqueo `consentimiento_datos = false` en la reserva telefónica (`RN-CONSENTIMIENTO`/`P11`).

**Veredicto sobre Borrador 1**: `❌ Reglas vulneradas` (`RN-ESTADOS`, `RN-CONSENTIMIENTO`, `RN-PAGO-SIMULADO`, `P8`/`P15`).

---

## 2. Spec corregida (Después) y veredicto `✅ Aprobado`

Tras ajustar [spec.md](../../../openspec/changes/c-11-frontend-agenda-backoffice/specs/frontend-agenda-backoffice/spec.md), [design.md](../../../openspec/changes/c-11-frontend-agenda-backoffice/design.md) y [tasks.md](../../../openspec/changes/c-11-frontend-agenda-backoffice/tasks.md):

| Regla | Cobertura en `C-11` | Referencia en spec/design |
|---|---|---|
| **RN-DOBLE / RN-SOLAPE** | Alta de disponibilidad/bloqueos valida orden horario (`422`) y reprogramación maneja `409 SLOT_OCUPADO` | Requirements 4 y 5 |
| **RN-LIBERACION** | Cancelación staff desde `/agenda` libera slot y da origen a devolución trazable en `/bandeja` | Requirements 2 y 5 |
| **RN-PASADO** | Reserva telefónica y reprogramación staff rechazan horarios pasados (`422`) | Requirement 5 |
| **RN-ANTICIPACION** | Cancelación staff consulta cotización previa (`100 % / 60 % / 0 %`) y motivo antes de confirmar | Requirement 5 |
| **RN-SENIA-PAGO** | Reprogramación mantiene aviso `Q3` sin recalcular seña en cliente; devolución `Q4` exige confirmación `monto_confirmado` | Requirements 2 y 5 |
| **RN-PAGO-SIMULADO** | Bandeja `/bandeja`, trazabilidad y recibos PDF muestran banner/marca `"(simulado)"`; `503` sin fallback si `mercadopago` (`P15`) | Requirements 2 y 3 |
| **RN-ESTADOS** | Trazabilidad e historial muestran actor + fecha (`P9`) y toda transición ocurre en backend (`P10`) | Requirement 3 |
| **RN-CONSENTIMIENTO** | Reserva telefónica `Q10` bloquea avance y no persiste si `consentimiento_datos = false` (`P11`) | Requirement 5 |

**Veredicto final**: `✅ Aprobado` — listo para implementar con TDD (`U2`) en `tasks.md`.
