# SKILL: validador-escenarios-turnos

## Nombre
`validador-escenarios-turnos`

## Propósito
Revisar los escenarios SDD (funcionamiento esperado, error de negocio y caso borde) propuestos para la reserva de turnos públicos (change C-10 `frontend-reserva-publica`), asegurando que cumplan las reglas de negocio del consultorio odontológico, especialmente las relacionadas con pagos simulados, expiración de slots y superposición de turnos. Esta skill no escribe código; solo valida que los escenarios propuestos estén completos, correctos y verificables antes de pasar a implementar.

## Cuándo se activa
Cuando el usuario pide validar un borrador de especificaciones SDD o escenarios de turnos, por ejemplo:
- "Valida los escenarios SDD para C-10"
- "Revisa si estos tres escenarios cumplen las reglas de negocio"
- "¿Faltan casos de borde en los escenarios de reserva de turno?"

## Entradas necesarias
1. El texto con los escenarios propuestos (propuesta de `proposal.md` o borrador de `tasks.md` del change C-10).
2. Acceso de lectura a los archivos de la base de conocimiento bajo `knowledge-base/`, en particular:
   - `knowledge-base/05_reglas_de_negocio.md` (RN-DOBLE, RN-SOLAPE, RN-LIBERACION, RN-PASADO, RN-ANTICIPACION, RN-SENIA-PAGO, RN-PAGO-SIMULADO, RN-ESTADOS)
   - `knowledge-base/04_modelo_de_datos.md` (entidades Turno, Pago, Disponibilidad, Bloqueo, idempotency_key, versión de lock optimista)
   - `knowledge-base/07_flujos_principales.md` (F1 reserva E2E, F2 cancelación, F3 reprogramación, F4.3 tokens de acción por mail, F5 pagos)
   - `knowledge-base/06_funcionalidades.md` (Épicas A, B, D1)
   - `knowledge-base/10_preguntas_abiertas.md` (Q1 monto default, Q3 diferencia de monto al reprogramar, Q4 devolución 60 % automática o manual)
   - `knowledge-base/11_pagos_mercadopago.md` (§0 modo simulado D14, §1 checkout, §3 webhook/idempotencia)

## Procedimiento paso a paso

### Paso 1: Leer las reglas de negocio vinculadas
Antes de validar cualquier escenario, leer y tener presentes las siguientes reglas del dominio:

| Regla | Descripción |
|-------|-------------|
| **RN-DOBLE** | No puede existir doble reserva: `UNIQUE (odontologo_id, inicio)` en Postgres. Dos turnos no pueden iniciar en el mismo instante para el mismo profesional. |
| **RN-SOLAPE** | No solapamiento por profesional: `EXCLUDE USING gist` (rangos de tiempo). Un turno no puede solaparse con otro del mismo odontólogo. |
| **RN-LIBERACION** | Slot expirado (TTL `RESERVA_TTL_MIN`, default 15 min) → estado `cancelado` + slot vuelve a disponible automáticamente. |
| **RN-PASADO** | `CHECK (inicio > now())`: no se puede reservar en el pasado. |
| **RN-ANTICIPACION** | Anticipación mínima configurable para cancelar/reprogramar. |
| **RN-SENIA-PAGO** | Seña: 100 % si dentro de término, 60 % si fuera de término, 0 % si no-show. |
| **RN-PAGO-SIMULADO** | En MVP (`PAGO_MODO=simulado`) no hay dinero real; el frontend nunca confirma pagos; solo el webhook (`POST /webhooks/mercadopago`) confirma; checkout simulado mediante `POST /pagos/{pago_id}/simular` con `checkout_token` de 1 uso. |
| **RN-ESTADOS** | Máquina de estados cerrada con actor+fecha: `creado → confirmado → {cancelado, reprogramado, atendido, no_show} → devuelto`. Cada transición registra actor, fecha y motivo en `TurnoHistorial` (append-only). |
| **RN-CONSENTIMIENTO** | Sin consentimiento registrado, no se persiste ficha ni se permite reserva (bloqueante). |

### Paso 2: Identificar los tres escenarios obligatorios
Verificar que el borrador incluya exactamente estos tres escenarios mínimos:

| # | Escenario | Qué debe verificar |
|---|-----------|-------------------|
| 1 | **Funcionamiento esperado** | Reserva feliz: paciente con DNI reconocido → elige profesional → elige fecha/hora (slot libre) → ve monto turno + seña → checkout simulado aprobado → turno `creado` + `pago(pendiente)` + `evento_pago(creado)` → webhook aprueba → turno `confirmado`. Debe incluir banner "(simulado)" en UI. |
| 2 | **Error de negocio** | Pago rechazado/expirado en checkout simulado → slot se libera automáticamente → turno pasa a `cancelado` → slot vuelve a estar disponible para otros pacientes. O bien: intento de reservar en slot ya ocupado → error 409 por `RN-DOBLE` o `RN-SOLAPE`. |
| 3 | **Caso borde** | Ejemplos válidos: slot expirado por TTL sin acción del usuario; reprogramación con diferencia de monto; intento de reservar en el pasado (`RN-PASADO`); paciente sin consentimiento (`RN-CONSENTIMIENTO`); doble-reserva concurrente (dos requests al mismo slot). |

### Paso 3: Contrastar reglas contra los tres escenarios
Para cada escenario, marcar si cada regla aplicable está cubierta:

- ¿El escenario feliz incluye `PAGO_MODO=simulado` y la marca "(simulado)" en respuesta/UI?
- ¿El escenario de error de negocio cubre al menos una de: doble-reserva, solapamiento, pago rechazado, expiración de TTL?
- ¿El caso borde incluye actor+fecha en la transición de estado (si aplica)?
- ¿Se respeta que el frontend **nunca** confirma pagos (solo el webhook o el adaptador simulado vía endpoint sandbox)?
- ¿Se usa `checkout_token` de 1 uso y vida corta en el checkout simulado?
- ¿El `idempotency_key` está presente en la creación de turno+pago?

### Paso 4: Buscar casos de borde faltantes o ambigüedades
Buscar activamente lo siguiente y reportarlo si falta:

1. **Expiración de slot sin acción del usuario**: ¿qué pasa si el usuario abandona el checkout antes del TTL?
2. **Reprogramación con diferencia de monto**: ¿se cobra/paga diferencia o se mantiene la seña original? (abierta Q3 en `10_preguntas_abiertas.md` — registrar como ambigüedad si no está resuelta).
3. **Devolución 60 % automática vs. manual**: ¿quién aprueba la devolución al cancelar fuera de término? (abierta Q4).
4. **Paciente no reconocido por DNI**: ¿flujo de alta manual vs. reconocimiento automático? (A2 en Épica A).
5. **Consentimiento faltante**: ¿el escenario de reserva bloquea si `consentimiento_datos = false`?
6. **Concurrencia**: ¿dos requests simultáneos al mismo slot dan exactamente una reserva exitosa y una rechazada?
7. **Anticipación mínima**: ¿se puede cancelar/reprogramar dentro de la ventana prohibida por `RN-ANTICIPACION`?
8. **Slots en el pasado**: ¿el endpoint público `GET /disponibilidad` filtra horas pasadas?

### Paso 5: Emitir veredicto
Redactar un reporte breve con uno de estos dos resultados:

- **✅ Aprobado**: los tres escenarios cubren las reglas de negocio aplicables, no hay ambigüedades críticas y son verificables con TDD.
- **❌ Reglas vulneradas**: listar qué reglas faltan, qué escenarios están incompletos o qué ambigüedades deben resolverse antes de implementar.

## Resultado esperado
Un reporte breve en Markdown con este formato:

```markdown
## Resultado de validación — validador-escenarios-turnos
**Change**: C-10 frontend-reserva-publica
**Fecha**: YYYY-MM-DD
**Validador**: validador-escenarios-turnos

### Veredicto
✅ Aprobado  /  ❌ Reglas vulneradas

### Reglas de negocio revisadas
| Regla | ¿Cubierta en escenario 1? | ¿Cubierta en escenario 2? | ¿Cubierta en escenario 3? | Observación |
|-------|---------------------------|---------------------------|---------------------------|-------------|
| RN-DOBLE | | | | |
| RN-SOLAPE | | | | |
| RN-LIBERACION | | | | |
| RN-PASADO | | | | |
| RN-ANTICIPACION | | | | |
| RN-SENIA-PAGO | | | | |
| RN-PAGO-SIMULADO | | | | |
| RN-ESTADOS | | | | |
| RN-CONSENTIMIENTO | | | | |

### Casos de borde detectados (o faltantes)
- [ ] ...
- [ ] ...

### Ambigüedades pendientes
- Q3: ...
- Q4: ...

### Correcciones requeridas
1. ...
2. ...

### Próximo paso
Listo para pasar a implementar con TDD / Pendiente de correcciones antes de implementar.
```

## Criterios de revisión del resultado
- El reporte debe mencionar explícitamente al menos 6 de las 8 reglas de negocio listadas.
- Si el veredicto es "❌ Reglas vulneradas", debe incluir al menos una corrección accionable.
- Los casos de borde deben ser específicos del dominio odontológico (no genéricos como "error de red").
- No se debe marcar el change como implementado ni archivado; esta skill solo prepara y valida.

## Limitaciones
- Esta skill no escribe código ni modifica archivos de implementación.
- No resuelve las preguntas abiertas (Q1, Q3, Q4); solo las identifica y las registra como pendientes si no están resueltas.
- No verifica sintaxis de TypeScript ni de FastAPI; solo valida coherencia con reglas de negocio del dominio.
- Requiere que el usuario provea el texto de los escenarios; si no se provee, la skill solicita el borrador antes de proceder.