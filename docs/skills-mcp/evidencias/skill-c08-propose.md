# Evidencia de ejecución de Skill — `validador-escenarios-turnos` sobre `C-08`

- **Fecha**: 2026-11-16
- **Skill ejecutada**: [SKILL.md](../../../.agents/skills/validador-escenarios-turnos/SKILL.md)
- **Change evaluado**: `C-08` (`c-08-devoluciones-comprobantes-conciliacion`), fase `/opsx:propose`
- **Artefactos evaluados**: [specs/devoluciones](../../../openspec/changes/c-08-devoluciones-comprobantes-conciliacion/specs/devoluciones/spec.md), [specs/comprobantes](../../../openspec/changes/c-08-devoluciones-comprobantes-conciliacion/specs/comprobantes/spec.md), deltas de [pagos](../../../openspec/changes/c-08-devoluciones-comprobantes-conciliacion/specs/pagos/spec.md), [reserva-turnos-estados](../../../openspec/changes/c-08-devoluciones-comprobantes-conciliacion/specs/reserva-turnos-estados/spec.md) y [mails-recordatorios](../../../openspec/changes/c-08-devoluciones-comprobantes-conciliacion/specs/mails-recordatorios/spec.md)
- **Fuentes de contraste**: `knowledge-base/03_actores_y_roles.md`, `04_modelo_de_datos.md`, `05_reglas_de_negocio.md`, `06_funcionalidades.md`, `07_flujos_principales.md` (F2, F5), `10_preguntas_abiertas.md`, `11_pagos_mercadopago.md` (§0, §4–§5)
- **Adaptación**: la skill está escrita para C-10 (reserva pública). Para C-08 se mantuvo el procedimiento (pasos 1–5) y la tabla de 9 reglas, contrastando el dominio de devoluciones: RN-SENIA-PAGO 100/60/0, RN-PAGO-SIMULADO, RN-ESTADOS `cancelado→devuelto`, RN-ANTICIPACION (borde del cálculo), RN-LIBERACION (atomicidad de la cancelación), RN-CONSENTIMIENTO (N/A justificado) y las reglas duras P4/P8/P9/P10/P15 + Q4. Los "3 escenarios obligatorios" se verificaron **por requirement** (feliz / error de negocio / borde, regla U2).

---

## 1. Solicitud inicial y Borrador 1 (Antes)

**Solicitud**: *"Validá los escenarios SDD de C-08 (devoluciones, comprobantes, conciliación) contra las reglas de negocio y pagos simulados antes de pasar a design/tasks."*

**Borrador 1 evaluado**: primera versión de los 5 spec files (13 requirements en `devoluciones`, 5 en `comprobantes`, 4 MODIFIED en `pagos`, 1 en `reserva-turnos-estados`, 4 en `mails-recordatorios`), ya válida con `openspec validate --strict`. Escenarios centrales:
1. **Esperado**: cancelación de turno `confirmado` con pago aprobado → `devolucion(pendiente)` 100 % / 60 % → aprobación manual con monto confirmado → ejecución por el adaptador simulado (`sim_refund_*`) vía el handler del webhook → pago `reembolsado_*`, turno `devuelto` (actor `sistema`), recibo PDF con leyenda, `aviso_devolucion` "(simulado)".
2. **Error de negocio**: monto distinto → 422; ejecutar sin aprobar → 409; odontólogo ajeno lee detalle → 403; turno sin pago aprobado no genera devolución.
3. **Borde**: 0 % no aprobable; 60 % nunca se auto-aprueba (Q4); reintento/concurrencia de ejecución sin duplicar; `PAGO_MODO=mercadopago` → 503 sin fallback; DB impide retroceder una devolución ejecutada.

### Reporte de `validador-escenarios-turnos` sobre Borrador 1 (Antes)

```markdown
## Resultado de validación — validador-escenarios-turnos
**Change**: C-08 devoluciones-comprobantes-conciliacion
**Fecha**: 2026-11-16
**Validador**: validador-escenarios-turnos

### Veredicto
❌ Reglas vulneradas

### Reglas de negocio revisadas
| Regla | ¿Cubierta en escenario 1? | ¿Cubierta en escenario 2? | ¿Cubierta en escenario 3? | Observación |
|---|---|---|---|---|
| RN-DOBLE | N/A | N/A | N/A | No aplica a devoluciones (no se reservan slots) |
| RN-SOLAPE | N/A | N/A | N/A | No aplica a devoluciones |
| RN-LIBERACION | Sí | N/A | Sí | Cancelación libera slot y, si falla el alta de la devolución, revierte todo |
| RN-PASADO | N/A | N/A | Sí | Cancelación post-`inicio` cotiza 0 % |
| RN-ANTICIPACION | Sí | No | ❌ No | Falta el borde exacto `inicio - ahora == ANTICIPACION_MIN_HS` (¿100 o 60?) |
| RN-SENIA-PAGO | Sí | Sí | ❌ Parcial | 100/60/0 cubiertos; "rounded to cents" sin modo de redondeo ni ejemplo verificable |
| RN-PAGO-SIMULADO | Sí | Sí | Sí | `sim_refund_*`, "(simulado)" en bandeja/respuesta/mail, leyenda PDF, sin fallback a simulado |
| RN-ESTADOS | ❌ Parcial | Sí | Sí | `cancelado→devuelto` con actor `sistema` OK, pero el paso "ejecutar" no registra qué staff lo pidió ni cuándo (RN-BANDEJA exige actor+fecha+monto en cada paso) |
| RN-CONSENTIMIENTO | N/A | N/A | N/A | No se crea ficha; los datos del recibo provienen de un paciente que ya pasó el gate de consentimiento en la reserva |

### Casos de borde detectados (faltantes)
- [ ] **P8 en acciones de escritura**: solo hay escenario 403 para *leer* devoluciones ajenas; falta que el odontólogo A no pueda aprobar/rechazar/ejecutar las de B (sin evento ni llamada al proveedor) y el caso de token `odontologo` sin `odontologo_id`.
- [ ] **RN-BANDEJA / RN-ESTADOS**: la ejecución solo deja `evento_pago(devolucion_ejecutada)` con actor `sistema`; falta registrar el staff que la solicitó (`ejecutada_por/at`).
- [ ] **RN-SENIA-60**: falta regla de redondeo verificable (p. ej. 60 % de 3333.33).
- [ ] **RN-ANTICIPACION**: falta el borde exacto de la ventana de anticipación al calcular el porcentaje.
- [ ] **Triada U2 incompleta** en 4 requirements: "No-show no genera devolución" (sin error de negocio), "Ciclo de estados" (sin feliz), "Devolución total o parcial ajusta el pago" (sin error), "Alertas de conciliación" (sin error de negocio de acceso).

### Ambigüedades pendientes
- Q1: monto default de seña — no afecta C-08 (el cálculo usa `pago.monto` ya cobrado).
- Q3: diferencia de monto al reprogramar — el spec devuelve sobre el pago heredado (seña original), coherente con el default de C-05/C-07; no se inventa cobro de diferencias.
- Q4: devolución 60 % automática vs. manual — el spec aplica el default de CHANGES.md (manual en bandeja) y no define umbral. Correcto, se mantiene abierta.
- RBAC `03 §2`: "paciente — solo ver estado de las suyas" no tiene endpoint en C-08 (declarado fuera de alcance; follow-up C-10/`/mis-turnos`).

### Correcciones requeridas
1. Agregar requirement "Acciones de bandeja restringidas al alcance del rol" con feliz (recepcionista aprueba de cualquier profesional), error (odontólogo ajeno → 403 sin evento ni proveedor) y borde (token odontólogo sin `odontologo_id` → 403).
2. Exigir en la ejecución `ejecutada_por` / `ejecutada_at` del staff solicitante y el `solicitado_por` + monto en el payload del evento.
3. Fijar redondeo half-up a centavos con ejemplo: 60 % de 3333.33 = 2000.00, nunca mayor al pago.
4. Agregar borde de límite exacto de anticipación → 100 % (igual que la cotización previa).
5. Completar la triada: `no_show→cancelado` → 422 sin devolución; recorrido válido `pendiente→aprobada→ejecutada`; rechazo no altera el pago; paciente/anónimo no ve alertas.

### Próximo paso
Pendiente de correcciones antes de redactar design.md y tasks.md.
```

---

## 2. Borrador 2 corregido (Después) y veredicto final

Se aplicaron las 5 correcciones en [specs/devoluciones/spec.md](../../../openspec/changes/c-08-devoluciones-comprobantes-conciliacion/specs/devoluciones/spec.md) (nuevo requirement de alcance en acciones, 9 escenarios nuevos, descripción de ejecución ampliada) y se re-validó con `openspec validate --strict` (válido). Se re-ejecutó `validador-escenarios-turnos`:

```markdown
## Resultado de validación — validador-escenarios-turnos
**Change**: C-08 devoluciones-comprobantes-conciliacion
**Fecha**: 2026-11-16
**Validador**: validador-escenarios-turnos

### Veredicto
✅ Aprobado

### Reglas de negocio revisadas
| Regla | ¿Cubierta en escenario 1? | ¿Cubierta en escenario 2? | ¿Cubierta en escenario 3? | Observación |
|---|---|---|---|---|
| RN-DOBLE | N/A | N/A | N/A | No aplica a devoluciones |
| RN-SOLAPE | N/A | N/A | N/A | No aplica a devoluciones |
| RN-LIBERACION | Sí | N/A | Sí | Cancelación + alta de devolución atómicas; fallo → turno sigue `confirmado` con su slot |
| RN-PASADO | N/A | N/A | Sí | Cancelación post-`inicio` → 0 %, monto 0, solo rechazable |
| RN-ANTICIPACION | Sí | N/A | Sí | Límite exacto → 100 %, misma regla que la cotización previa |
| RN-SENIA-PAGO | Sí | Sí | Sí | 100 / 60 (half-up, 3333.33 → 2000.00) / 0 (no-show sin devolución; `no_show→cancelado` → 422) |
| RN-PAGO-SIMULADO | Sí | Sí | Sí | `sim_refund_*` estable por `idempotency_key`, ejecución solo vía handler del webhook firmado (P10), "(simulado)" en bandeja/respuesta/mail, leyenda PDF fija por comprobante (P15), sin fallback con `mercadopago` |
| RN-ESTADOS | Sí | Sí | Sí | `cancelado→devuelto` solo `sistema` con historial; staff → 403; cada paso de la devolución con actor+fecha (`aprobada_por`, `rechazada_por`, `ejecutada_por`) y ciclo cerrado en app + DB |
| RN-CONSENTIMIENTO | N/A | N/A | N/A | Sin ficha nueva; datos de paciente ya consentidos en la reserva; seeds con DNI ficticios (P11) |

### Reglas duras verificadas
- P4: `idempotency_key` única por devolución, reintento/concurrencia/replay por `mp_refund_id` sin duplicar.
- P8: lectura **y** acciones con scope en backend; odontólogo sin `odontologo_id` → 403.
- P9: `evento_pago` append-only con `devolucion_rechazada`; `comprobante` sin UPDATE/DELETE.
- P10: solo el handler del webhook marca `ejecutada`; idempotencia de pago y devolución separadas.
- P12: sin rutas públicas nuevas; recibo al paciente solo como adjunto.
- P15: leyenda "SIMULADO — sin valor fiscal ni movimiento de dinero" + "(simulado)" en mail.

### Casos de borde cubiertos
- [x] Odontólogo ajeno no aprueba/rechaza/ejecuta (403, sin evento ni proveedor).
- [x] Ejecuciones concurrentes / reintento post-respuesta del proveedor → una sola ejecución, mismo `mp_refund_id`.
- [x] Turno reprogramado: la devolución recae sobre el turno cancelado y el pago heredado.
- [x] Webhook de devolución sobre pago ya aprobado no se descarta como replay del pago.
- [x] Devolución 60 % nunca se auto-aprueba (Q4 default manual).

### Ambigüedades pendientes (registradas sin inventar solución)
- Q1: no afecta (se usa `pago.monto`).
- Q3: se devuelve sobre la seña original heredada; cobro de diferencias sigue abierto.
- Q4: default manual en bandeja; umbral de auto-aprobación sin definir y sin código condicional.
- RBAC paciente "ver estado de las suyas": follow-up fuera de C-08.

### Próximo paso
Listo para completar design.md y tasks.md de C-08 e implementar con TDD; el change no se marca implementado ni archivado.
```

## 3. Aporte concreto al change `C-08`

La validación detectó antes de diseñar cuatro huecos reales en un change CRÍTICO: (1) el scope P8 solo cubría lecturas, así que un odontólogo podía aprobar o ejecutar devoluciones ajenas sin que ningún escenario lo prohibiera; (2) la ejecución no guardaba qué staff la pidió, lo que rompía RN-BANDEJA; (3) el 60 % no tenía una regla de redondeo verificable; (4) faltaba el borde exacto de anticipación. Además completó la triada feliz/error/borde (U2) en 4 requirements. Las correcciones se volcaron después en `design.md` (D2 half-up, D3 columnas `ejecutada_por/at`, D8 scope en repositorio) y en `tasks.md` (grupos 2–4).

---

## 4. Revisión humana del propose y re-validación (Borrador 3)

**Decisiones del usuario (2026-11-16)**:
1. **Respuesta de `POST /reservas/{id}/cancelar`** (devuelve la devolución real o `null`, marcado BREAKING): **aprobada** sin cambios de fondo; quedó registrada como decisión aprobada por el equipo en `design.md` (D1) y en `proposal.md`.
2. **Devolución del 0 %**: si la cotización es 0 % **no se crea devolución**. Sustituye la decisión anterior (persistir una fila con monto 0 que solo se podía rechazar). Se propagó a `proposal.md`, `design.md` (D1, D2, D3, D9, Risks, Migration Plan), `tasks.md` (1.3, 1.4, 2.1, 2.3, 2.4, 2.5, 3.3, 5.1, 7.2) y a los specs `devoluciones`, `reserva-turnos-estados`, `mails-recordatorios`, `pagos` y `comprobantes`. Se eliminaron el escenario "Devolución del 0 % no se puede aprobar" (`DEVOLUCION_MONTO_CERO`) y el escenario que persistía `devolucion(porcentaje = 0, monto = 0)`; la migración 006 queda con `CHECK porcentaje IN (100,60)` y `CHECK monto > 0`. En `CHANGES.md` solo se ajustó el texto del modelo `Devolucion` a `porcentaje 100|60`.

### Reporte de `validador-escenarios-turnos` sobre los escenarios afectados por la decisión 2

```markdown
## Resultado de validación — validador-escenarios-turnos
**Change**: C-08 devoluciones-comprobantes-conciliacion (re-validación parcial, decisión 2)
**Fecha**: 2026-11-16
**Validador**: validador-escenarios-turnos

### Veredicto
✅ Aprobado

### Escenarios re-evaluados
| Spec / Requirement | Escenario | Resultado |
|---|---|---|
| devoluciones / Devolución persistida con constraints | Porcentaje o monto fuera de dominio (ahora incluye `porcentaje = 0` y `monto = 0`) | ✅ Verificable con inserción adversa directa a DB |
| devoluciones / Alta automática al cancelar | Descripción exige pago aprobado **y** cotización > 0 % | ✅ Coherente con la decisión |
| devoluciones / Cotización de 0 % no genera devolución | Feliz: no-show retiene la seña · Error: `no_show→cancelado` → 422 · Borde: cancelación post-`inicio` (0 %) sin devolución, sin `devolucion_solicitada`, sin recibo, sin aviso, pago `aprobado`, turno `cancelado` (nunca `devuelto`), respuesta `null` | ✅ Triada completa (U2) |
| devoluciones / Aprobación manual | El escenario de 0 % se reemplazó por "aprobar una devolución ya resuelta → 409" | ✅ Triada intacta |
| reserva-turnos-estados / Cotización previa | Nuevo borde: cancelación con 0 % responde `devolucion = null` | ✅ |
| mails-recordatorios / Cancelar desde el mail | Nuevo borde: 0 % no crea `devolucion` ni `aviso_devolucion` | ✅ |
| comprobantes / Recibo por devolución ejecutada | Nuevo borde: cancelación con 0 % no emite recibo de devolución | ✅ |
| pagos / Conciliación | Nuevo: pago `aprobado` de turno cancelado/no_show con 0 % no es discrepancia | ✅ |

### Reglas revisadas
| Regla | Observación |
|---|---|
| RN-SENIA-PAGO (RN-SENIA-0) | 0 % retiene la seña en no-show y en cancelación post-`inicio`, sin fila de devolución |
| RN-ESTADOS | El turno con 0 % termina en `cancelado`; `cancelado→devuelto` solo ocurre tras una devolución ejecutada |
| RN-LIBERACION | La cancelación con 0 % libera el slot igual que el resto |
| RN-PASADO / RN-ANTICIPACION | El 0 % surge solo de cancelar después de `inicio`; el límite exacto de anticipación sigue en 100 % |
| RN-PAGO-SIMULADO | Sin cambios; no se emite "(simulado)" de devolución porque no hay devolución |
| RN-BANDEJA | La bandeja ya no recibe filas de 0 %; la trazabilidad de esa cancelación queda en `turno_historial` |

### Observaciones (sin bloquear)
- El pedido hablaba de "cancelación fuera de término con 0 %". En la KB, cancelar fuera de término da 60 % (RN-SENIA-60); el 0 % solo aparece al cancelar después de `inicio` o con un no-show. El escenario se redactó con la condición real ("cancelado after its `inicio`").
- La KB sigue diciendo `porcentaje (100|60|0)` en `04_modelo_de_datos.md` §2 y `cancelado → devuelto (100/60/0)` en `05` §4; `CHANGES.md` también conserva "Cálculo 100/60/0 (RN-SENIA-*) registrado en `devolucion.porcentaje`" en el scope de C-08. No se editaron porque no estaba pedido; conviene sincronizarlos.

### Próximo paso
Listo para `/opsx:apply` con TDD; el change no se marca implementado ni archivado.
```
