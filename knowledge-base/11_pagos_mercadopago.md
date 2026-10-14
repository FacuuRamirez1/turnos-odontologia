# 11 — Pagos con MercadoPago (extra, a fondo) [v1]

**Proyecto**: turnos-odontología · **Fecha**: 2026-10-14 · **Fuente**: `discovery/discovery.md` (§7–8) + análisis C.4 (motor de seña)
Relacionadas: `04_modelo_de_datos.md` (pago/devolucion/comprobante/evento_pago), `05_reglas_de_negocio.md` (RN-SENIA-*), `07_flujos_principales.md` (F1/F2/F5).
Referencias de mercado: cobro al reservar declarado por MedicAI; caja con MP en DentalSoft; cobro anticipado en Gendu (todo declaración de esos proveedores). Patrón comprobante+link+conciliación: ARCA-API / TusFacturasAPP.

## 1. Checkout

1. Reserva crea `turno(creado)` + `pago(pendiente)` con `idempotency_key` única; se genera preferencia MP (`mp_preference_id`) por el monto de seña del odontólogo.
2. El paciente paga en checkout MP; la app **nunca** confirma el turno por callback del frontend: solo el webhook server-to-server confirma.
3. Pre-reserva con TTL: si no hay aprobación en la ventana, turno `cancelado` (pago fallido) y slot liberado.

## 2. Webhooks

- Endpoint público `POST /webhooks/mercadopago`: valida firma (`MP_WEBHOOK_SECRET`) → persiste `evento_pago(webhook_recibido)` con payload crudo → procesa.
- Idempotencia: clave `mp_payment_id`; replays del mismo evento no duplican transiciones (verifican estado actual antes de mutar).
- Tras procesar: `aprobado` → turno `confirmado` + mail confirmación; `rechazado` → turno `cancelado` + aviso.

## 3. Idempotencia (auditoría máxima día 1)

- `UNIQUE` en `pago.idempotency_key`, `pago.mp_payment_id`, `turno.idempotency_key`.
- Reintentos de red/MP: misma key → mismo resultado, sin doble cobro ni doble devolución.

## 4. Bandeja de devoluciones

- Estados: `pendiente → aprobada/rechazada → ejecutada`; cada paso guarda actor + fecha + monto + motivo.
- Porcentajes: 100 % en término / 60 % fuera / 0 % no-show (RN-SENIA-*); el cálculo queda registrado en `devolucion.porcentaje`.
- Ejecución contra API MP guarda `mp_refund_id`; reintentos consultan antes de re-ejecutar.

## 5. Comprobantes

- Recibo interno **[v1]** por cada pago aprobado y cada devolución ejecutada (PDF descargable + link en mail).
- `comprobante` separado del turno/pago desde v1; campos ARCA (`cae`, factura A/B/C) **[v2]** apagados pero columnados.

## 6. Conciliación

- Job diario: compara `pago.estado` local vs. estado MP (API) por `mp_payment_id`; discrepancias → `evento_pago(conciliado)` + alerta en bandeja.
- Exportación CSV/PDF de caja para roles autorizados **[v1]**.

## 7. Audit trail

- `evento_pago` append-only (creado, webhook_recibido, aprobado, rechazado, devolucion_solicitada/aprobada/ejecutada, conciliado) con payload y actor; sin UPDATE/DELETE.
- Trazabilidad turno↔pago↔devolución↔comprobante navegable desde agenda y bandeja.
