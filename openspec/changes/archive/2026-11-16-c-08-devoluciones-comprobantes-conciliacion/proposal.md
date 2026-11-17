# Proposal — c-08-devoluciones-comprobantes-conciliacion

## Why

C-07 dejó el cobro de seña simulado funcionando, pero la otra mitad de la Épica D sigue sin construir: al cancelar un turno, C-05 solo devuelve en la respuesta un `devolucion: {estado: "pendiente", porcentaje}` que no se persiste. No hay bandeja, no hay ejecución idempotente de la devolución, el turno nunca llega a `devuelto`, no hay recibo interno y el `aviso_devolucion` de C-09 no tiene productor real. Sin esto F2 (cancelación con devolución) no cierra, y la auditoría máxima día 1 (RN-BANDEJA, RN-AUDIT) no se cumple. Es CRÍTICO porque toca dinero (aunque sea simulado, D14) y es camino crítico (C-07 → **C-08** → C-11).

## What Changes

- **Modelo `Devolucion`** (bandeja) persistido: `pago_id`, `turno_id`, `monto`, `porcentaje ∈ {100, 60}`, `monto > 0`, `motivo`, `estado pendiente|aprobada|rechazada|ejecutada`, actor + fecha de cada paso, `idempotency_key` única, `mp_refund_id` único (sintético `sim_refund_<uuid>` en `PAGO_MODO=simulado`). Una devolución por pago (`UNIQUE(pago_id)`).
- **Modelo `Comprobante`** separado del turno/pago (D13): `tipo=recibo_interno` (v1), concepto `pago|devolucion`, número correlativo, `simulado` (bool, fijado al emitir), columnas ARCA (`cae`) presentes y apagadas (P13). Inmutable (sin UPDATE/DELETE).
- **Migración `006`** (down_revision `005_pago_evento_pago`): tablas `devolucion` + `comprobante`, constraints/trigger de transición de la devolución en DB (P6), alta del tipo `devolucion_rechazada` en `evento_pago`, grants least-privilege. Cero `create_all` (P3).
- **Alta automática de la devolución al cancelar**: toda transición `confirmado→cancelado` (staff, paciente por token, cancelación desde mail) crea en el mismo commit una `devolucion(pendiente)` con el porcentaje calculado por RN-SENIA-100/60 + `evento_pago(devolucion_solicitada)`, solo si el turno tiene un pago `aprobado` y la cotización es mayor a 0 %. **Con cotización 0 % no se crea devolución** (decisión del usuario en revisión): ni `devolucion`, ni recibo de devolución, ni `aviso_devolucion`; el pago sigue `aprobado` y el turno queda `cancelado` (nunca `devuelto`). `no_show` tampoco genera devolución (RN-SENIA-0).
- **Bandeja de devoluciones (staff, JWT)**: listar, ver detalle, aprobar (con confirmación explícita del monto), rechazar (motivo obligatorio) y ejecutar. RBAC en backend (P8): odontólogo solo las de sus turnos (forzado en repositorio), recepcionista/admin todas; paciente sin acceso. **Q4**: toda devolución (incluida la de 60 %) requiere aprobación manual; no se implementa auto-aprobación ni umbral.
- **Ejecución idempotente vía puerto de pagos** (P4/P10): `ProveedorPago` suma `ejecutar_devolucion` / `consultar_devolucion`; el adaptador simulado genera `sim_refund_<uuid>` determinístico a partir de la `idempotency_key`, emite un evento firmado HMAC y lo entrega al **mismo** handler del webhook, que con idempotencia por `mp_refund_id` marca la devolución `ejecutada`, el pago `reembolsado_parcial|reembolsado_total`, registra `evento_pago(devolucion_ejecutada)` y transiciona el turno `cancelado→devuelto` (actor `sistema`). Nada mueve dinero. Reintentos consultan antes de re-ejecutar.
- **Recibos internos PDF** por pago aprobado y por devolución ejecutada, con leyenda visible "SIMULADO — sin valor fiscal ni movimiento de dinero" cuando el comprobante es simulado (P15). PDF generado sin dependencias nuevas.
- **`aviso_devolucion` con productor real** (cierra el pendiente de C-09): se encola al resolverse la devolución (ejecutada o rechazada), informa monto/porcentaje/estado, lleva "(simulado)" y adjunta el recibo PDF cuando fue ejecutada (sin link público: P12).
- **Trazabilidad navegable** `turno ↔ pago ↔ devolución ↔ comprobante` (+ `evento_pago` y `turno_historial`) para staff, base para C-11/C-12.
- **Conciliación interna ampliada**: el job de C-07 reconoce los reembolsos (no los reporta como falsa discrepancia) y detecta inconsistencias devolución↔pago↔turno; las alertas se ven en la bandeja.
- **BREAKING (respuesta interna)**: `POST /api/reservas/{id}/cancelar` devuelve `devolucion` con `id` y `monto` reales, o `null` cuando el turno no tenía pago aprobado o la cotización fue 0 % (antes siempre devolvía un objeto `pendiente` no persistido). **Aprobado por el usuario/equipo en la revisión humana del propose.**

## Capabilities

### New Capabilities
- `devoluciones`: bandeja de devoluciones — alta por cancelación, cálculo 100/60 (0 % sin devolución), ciclo `pendiente→aprobada|rechazada→ejecutada` con actor+fecha+monto, ejecución idempotente, RBAC, `cancelado→devuelto`, aviso al paciente, trazabilidad navegable y alertas de conciliación.
- `comprobantes`: recibos internos por pago aprobado y devolución ejecutada, numeración, inmutabilidad, PDF con leyenda de simulado, columnas ARCA apagadas.

### Modified Capabilities
- `pagos`: el puerto `ProveedorPago` suma operaciones de devolución; `evento_pago` suma `devolucion_rechazada`; el webhook procesa eventos de devolución con idempotencia por `mp_refund_id` (separada de la de pago) y emite el recibo de pago al aprobar; la conciliación contempla reembolsos y no marca como discrepancia la seña retenida con 0 %.
- `reserva-turnos-estados`: confirmar una cancelación ahora persiste la devolución (antes solo la cotizaba en la respuesta) y la respuesta refleja la devolución real o `null` (sin pago aprobado o cotización 0 %).
- `mails-recordatorios`: `aviso_devolucion` pasa a tener productor real (con monto, estado, marca "(simulado)" y adjunto PDF); la cancelación desde el mail deja la devolución `pendiente` en bandeja (sigue sin ejecutar nada); el SMTP admite adjuntos sin dependencias nuevas.

## Impact

- **Backend**: `app/domain/devoluciones/` (servicio, cálculo, repositorio scoped), nuevo `app/domain/comprobantes/` (emisión + PDF), `app/api/devoluciones.py`, `app/api/comprobantes.py`, `app/api/trazabilidad` (endpoint staff), `app/api/pagos.py` (rama de devolución en el webhook + recibo de pago), `app/domain/pagos/proveedor.py`, `app/infra/pago_simulado/adapter.py`, `app/domain/turnos/estados.py` (hook en `confirmado→cancelado`), `app/api/reservas.py` (respuesta de cancelación), `app/domain/notificaciones/` (plantilla `aviso_devolucion` v2, contexto), `app/infra/smtp/client.py` (adjuntos), `app/workers/conciliacion.py`, `app/infra/db/models/` (`devolucion.py`, `comprobante.py`), `alembic/versions/006_devolucion_comprobante.py`, `seed_dev.py` (1 pago aprobado + 1 devolución 60 % ejecutada, KB 04 §5).
- **API nueva (solo staff, JWT, no amplía las 6 rutas públicas — P12)**: `GET /api/devoluciones`, `GET /api/devoluciones/{id}`, `POST /api/devoluciones/{id}/aprobar|rechazar|ejecutar`, `GET /api/comprobantes/{id}`, `GET /api/comprobantes/{id}/pdf`, `GET /api/turnos/{turno_id}/trazabilidad`.
- **DB**: migración `006`; `evento_pago` y `turno_historial` siguen append-only; `comprobante` sin UPDATE/DELETE.
- **Dependencias**: ninguna nueva (PDF y adjuntos con stdlib).
- **Fuera de alcance**: MercadoPago real (`PAGO_MODO=mercadopago`, v2), facturación ARCA (v2), auto-aprobación por umbral (Q4 abierta), vista del paciente del estado de su devolución (follow-up C-10/`/mis-turnos`), UI de bandeja (C-11), exportación CSV/PDF de caja (C-12).
