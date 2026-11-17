# Política de retención RN-RETENCION — v1 (C-13 task 3.1)

## Alcance
Se aplica a: turnos, mails (recordatorio_mail), eventos de pago (evento_pago)
e historial de turnos (turno_historial). Política publicada y versionada.

## Plazos de conservación

| Entidad | Campo de tiempo | Plazo | Acción tras vencimiento |
|---|---|---|---|
| `turno` | `created_at` | 24 meses | Anonimizar DNI/email/telefono (mantener conteo estadístico) |
| `turno_historial` | `fecha` | 24 meses | Mantener append-only (auditoría, no se borra) |
| `recordatorio_mail` | `created_at` | 12 meses | Eliminar registros `fallido`/`enviado` > 12 meses |
| `evento_pago` | `created_at` | 24 meses | Mantener append-only (auditoría de pagos, no se borra) |
| `pago` | `created_at` | 24 meses | Anonimizar datos de pago (mantener monto/estado) |
| `devolucion` | `created_at` | 24 meses | Mantener (trazabilidad de caja) |

## Excepciones
- `turno_historial` y `evento_pago` son append-only (P9): nunca se eliminan
  físicamente; solo se anonimizan campos sensibles según la política.
- Registros con `is_active = false` (soft-delete) se conservan indefinidamente
  como parte del audit trail.

## Ejecución
Job periódico (worker Redis/scheduler) que:
1. Lee la política publicada.
2. Identifica registros vencidos por entidad.
3. Anonimiza o elimina según la tabla anterior.
4. Deja rastro append-only de registros conservados/eliminados/anonimizados.

## Referencias
- `05_reglas_de_negocio.md` (RN-RETENCION).
- `08_arquitectura_propuesta.md` §7 (cumplimiento técnico v1).
