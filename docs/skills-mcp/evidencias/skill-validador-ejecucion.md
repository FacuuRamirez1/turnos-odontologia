# Evidencia de ejecución de Skill — `validador-escenarios-turnos`

- **Fecha**: 2026-11-13
- **Skill ejecutada**: [SKILL.md](../../../.agents/skills/validador-escenarios-turnos/SKILL.md)
- **Change evaluado**: `C-10` (`frontend-reserva-publica`)
- **Fuentes de contraste**: `knowledge-base/03_actores_y_roles.md`, `04_modelo_de_datos.md`, `05_reglas_de_negocio.md`, `06_funcionalidades.md`, `07_flujos_principales.md`, `10_preguntas_abiertas.md`, `11_pagos_mercadopago.md`

---

## 1. Solicitud inicial y Borrador 1 (Antes)

**Solicitud**: *"Valida los escenarios SDD para C-10 contra las reglas de negocio y pagos simulados."*

**Borrador 1 evaluado (escenarios iniciales antes de la revisión)**:
1. **Escenario esperado**: Paciente ingresa DNI, selecciona odontólogo y slot libre en `/reservar`, confirma turno y pasa a `/checkout-simulado`; presiona Aprobar y el turno queda `confirmado`.
2. **Escenario de error de negocio**: Paciente intenta reservar un slot ya tomado (409) o rechaza el pago simulado; el slot queda disponible nuevamente.
3. **Escenario borde**: Paciente ingresa a `/mis-turnos?dni=30111222` para consultar sus turnos sin token y reprograma eligiendo cualquier fecha disponible.

### Reporte de `validador-escenarios-turnos` sobre Borrador 1 (Antes)

```markdown
## Resultado de validación — validador-escenarios-turnos
**Change**: C-10 frontend-reserva-publica
**Fecha**: 2026-11-13
**Validador**: validador-escenarios-turnos

### Veredicto
❌ Reglas vulneradas

### Reglas de negocio revisadas
| Regla | ¿Cubierta en escenario 1? | ¿Cubierta en escenario 2? | ¿Cubierta en escenario 3? | Observación |
|---|---|---|---|---|
| RN-DOBLE | Parcial | Sí (409) | No | Falta explicitar carrera concurrente / rechazo 409 |
| RN-SOLAPE | No | Parcial | No | Falta validar solape de rangos en slot ocupado |
| RN-LIBERACION | No | Sí | No | Falta verificar transición `cancelado` por rechazo/TTL |
| RN-PASADO | No | No | ❌ No | Reprogramación en Borrador 1 no bloquea fecha pasada |
| RN-ANTICIPACION | No | No | ❌ No | Omite anticipación mínima configurable y cotización 100/60 |
| RN-SENIA-PAGO | Parcial | No | ❌ No | Falta mostrar monto turno + seña antes de confirmar (A4) |
| RN-PAGO-SIMULADO | ❌ Parcial | Parcial | N/A | Omite banner "(simulado)", `checkout_token` 1 uso e `Idempotency-Key` |
| RN-ESTADOS | Parcial | Parcial | ❌ No | Omite actor `sistema` vía webhook y actor paciente en historial |
| RN-CONSENTIMIENTO | ❌ No | No | No | Omite bloqueo si `consentimiento_datos = false` |

### Casos de borde detectados (faltantes)
- [ ] **Seguridad P12 / `03 §3.5`**: Borrador 1 permite `/mis-turnos?dni=...` sin `token`; la regla exige `dni` + `token` (1 uso, nunca DNI solo).
- [ ] **RN-CONSENTIMIENTO / P11**: falta bloqueo explícito en paso 1 si el paciente nuevo no acepta `consentimiento_datos = true`.
- [ ] **RN-PAGO-SIMULADO / P10 / P15**: falta verificar banner `"(simulado)"`, no reutilización de `checkout_token` y ausencia de confirmación directa desde frontend.
- [ ] **Expiración TTL y `/mail/cancelar`**: falta escenario borde de checkout abandonado (TTL 15 min) y cancelación desde mail con cotización 100/60/0.

### Ambigüedades pendientes
- Q1: Monto default de seña configurable por odontólogo (abierto en `10 §1.1`; en UI se lee de backend).
- Q3: Reprogramación con diferencia de monto — Borrador 1 no aclara que en MVP se mantiene la seña original sin nuevo cobro (`10 §1.3`).
- Q4: Devolución 60 % automática vs. aprobación manual en bandeja (`10 §1.4`).

### Correcciones requeridas
1. Exigir `dni` y `token` en `/mis-turnos`; rechazar acceso con DNI solo (`401`).
2. Bloquear avance/envío si `consentimiento_datos = false` (`422 CONSENTIMIENTO_REQUERIDO`).
3. Añadir verificación explícita de monto turno + seña pre-confirmación, `Idempotency-Key`, `checkout_token` de 1 uso, banner `"(simulado)"`, actor `sistema` vía webhook y reglas `RN-PASADO`/`RN-ANTICIPACION`.
4. Dejar registradas `Q1`, `Q3` y `Q4` sin inventar comportamiento de cobro de diferencias.
```

---

## 2. Borrador 2 corregido (Después) y veredicto final

Tras incorporar todas las correcciones en [spec.md](../../../openspec/changes/c-10-frontend-reserva-publica/specs/frontend-reserva-publica/spec.md), se re-ejecutó `validador-escenarios-turnos`:

```markdown
## Resultado de validación — validador-escenarios-turnos
**Change**: C-10 frontend-reserva-publica
**Fecha**: 2026-11-13
**Validador**: validador-escenarios-turnos

### Veredicto
✅ Aprobado

### Reglas de negocio revisadas
| Regla | ¿Cubierta en escenario 1? | ¿Cubierta en escenario 2? | ¿Cubierta en escenario 3? | Observación |
|---|---|---|---|---|
| RN-DOBLE | Sí | Sí | Sí | Flujo happy path + conflicto `409 SLOT_OCUPADO` en concurrencia |
| RN-SOLAPE | Sí | Sí | Sí | Slots ofrecidos filtrados por `GET /api/disponibilidad` y rechazo 409 |
| RN-LIBERACION | N/A | Sí | Sí | Pago rechazado o TTL expirado deja el turno `cancelado` y libera slot |
| RN-PASADO | Sí | Sí | Sí | Selector solo muestra fechas válidas; reprogramación/pasado rechazado `422` |
| RN-ANTICIPACION | Sí | N/A | Sí | Cotización 100/60 visible antes de cancelar; bloqueo fuera de ventana |
| RN-SENIA-PAGO | Sí | N/A | Sí | Paso 4 muestra monto turno + seña antes de reservar; Q3 mantiene seña original |
| RN-PAGO-SIMULADO | Sí | Sí | Sí | Banner `"(simulado)"`, `Idempotency-Key`, `checkout_token` 1 uso, solo webhook confirma |
| RN-ESTADOS | Sí | Sí | Sí | Transición `creado→confirmado`/`cancelado` por webhook (`sistema`) |
| RN-CONSENTIMIENTO | Sí | Sí | N/A | Paso 1 bloquea si `consentimiento_datos = false` y muestra `422 CONSENTIMIENTO_REQUERIDO` |

### Casos de borde cubiertos en `specs/frontend-reserva-publica/spec.md`
- [x] DNI solo en `/mis-turnos` rechazado (`401`) — exige `dni` + `token` (P12).
- [x] Reuso de `checkout_token` en `/checkout-simulado` o expiración TTL sin pago (`403`/`422`, slot liberado).
- [x] `consentimiento_datos = false` bloqueante (`RN-CONSENTIMIENTO`, `P11`).
- [x] Reprogramación heredando pago sin nuevo cobro (`Q3` registrado) y cotización 100/60 visible pre-cancelación (`B2`).
- [x] Ráfaga HTTP `429` y enlace `/mail/confirmar` o `/mail/cancelar` ya usado (respuesta idempotente amigable).

### Ambigüedades pendientes (registradas sin inventar solución)
- Q1: Monto default de seña por odontólogo (se consume el configurado en backend).
- Q3: Diferencia de monto al reprogramar (en MVP se informa mantenimiento de seña original).
- Q4: Devolución 60 % automática vs. aprobación manual en bandeja (fuera de C-10; corresponde a bandeja C-08/C-11).

### Próximo paso
Listo para completar `design.md` y `tasks.md` de C-10 sin marcar el change como implementado ni archivado.
```

## 3. Aporte concreto al change `C-10`

Permitió blindar `specs/frontend-reserva-publica/spec.md` antes de redactar `tasks.md`, eliminando dos violaciones críticas (`P12` en `/mis-turnos` y `RN-CONSENTIMIENTO`) y dejando explícitos los casos de borde del checkout simulado y la trazabilidad por `Idempotency-Key` y `checkout_token`.
