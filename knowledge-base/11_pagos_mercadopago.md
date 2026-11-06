# 11 — Pagos (MercadoPago — modo simulado en MVP) [v1]

**Proyecto**: turnos-odontología · **Fecha**: 2026-10-14 · **Fuente**: `discovery/discovery.md` (§7–8) + análisis C.4 (motor de seña)
Relacionadas: `04_modelo_de_datos.md` (pago/devolucion/comprobante/evento_pago), `05_reglas_de_negocio.md` (RN-SENIA-*), `07_flujos_principales.md` (F1/F2/F5).
Referencias de mercado: cobro al reservar declarado por MedicAI; caja con MP en DentalSoft; cobro anticipado en Gendu (todo declaración de esos proveedores). Patrón comprobante+link+conciliación: ARCA-API / TusFacturasAPP.

## 0. Modo simulado (MVP) — D14

Decisión **D14** (2026-11-05, ver `09_decisiones_y_supuestos.md`): para el MVP la integración con MercadoPago se reemplaza por un **proveedor de pagos simulado** detrás del mismo puerto/adaptador (`08 §1`). La arquitectura no cambia: pasar a MP real después es solo cambiar el adaptador. Las secciones §1–§7 describen el **target de producción (MP real)**; cada una lleva una nota de qué cambia en el MVP.

- **Flag**: `PAGO_MODO=simulado|mercadopago`. Default `simulado` en MVP/dev; `mercadopago` queda **diseñado, no construido** en v1-MVP (v2/producción). `MP_ACCESS_TOKEN` y `MP_PUBLIC_KEY` pasan a **opcionales** (solo requeridas si `PAGO_MODO=mercadopago`). `MP_WEBHOOK_SECRET` se sigue usando también en modo simulado: el adaptador firma con HMAC el evento y lo entrega al **mismo** pipeline del webhook.
- **Flujo simulado**:
  1. `POST /reservas` crea `turno(creado)` + `pago(pendiente, proveedor='simulado', mp_payment_id sintético 'sim_pay_<uuid>')` + `evento_pago(creado)` y devuelve `checkout_url` (pantalla "Checkout simulado" del frontend) + `checkout_token` de 1 uso y vida corta.
  2. La pantalla permite elegir **Aprobar / Rechazar / (opcional) Expirar**. El frontend **nunca** confirma: llama a `POST /pagos/{pago_id}/simular` (con `checkout_token`), que le pide al adaptador simulado emitir el evento firmado.
  3. El adaptador entrega el evento al handler de `POST /webhooks/mercadopago`: valida firma `MP_WEBHOOK_SECRET` → persiste `evento_pago(webhook_recibido)` con payload crudo → idempotencia por `mp_payment_id` / `mp_refund_id` sintéticos → recién ahí dispara `creado→confirmado` o `creado→cancelado` con actor `sistema`.
  4. Se respeta el TTL de pre-reserva (`RESERVA_TTL_MIN`, 15 min): vencido el TTL el turno pasa a `cancelado` y el slot se libera, igual que con MP real.
- **Endpoint sandbox `POST /pagos/{pago_id}/simular`**: existe **solo** si `PAGO_MODO=simulado` (apagado en producción / modo `mercadopago`), exige `checkout_token` de 1 uso, con rate-limit. **No integra la lista de 6 rutas públicas de producción (P12)**: es una excepción documentada, condicionada por flag. El modo simulado **NUNCA** puede quedar habilitado en producción (P15).
- **Devoluciones**: se mantienen **completas** (bandeja, 100/60/0, `devolucion`, `comprobante`, PDF, `aviso_devolucion`, `cancelado→devuelto`); solo la **ejecución** la hace el adaptador simulado (genera `sim_refund_<uuid>` y registra `evento_pago(devolucion_ejecutada)`), sin mover dinero.
- **Marca "(simulado)"**: la UI de checkout, la bandeja, caja/reportes y los textos de mail (`aviso_devolucion`, confirmación, cancelación por mail) muestran banner/marca "(simulado)" cuando `PAGO_MODO=simulado`, para no prometer devoluciones reales. Los comprobantes PDF llevan la leyenda visible **"SIMULADO — sin valor fiscal ni movimiento de dinero"**.

## 1. Checkout

> **MVP (D14)**: no hay preferencia MP ni checkout externo; el `checkout_url` apunta a la pantalla "Checkout simulado" (ver §0). Lo de abajo es el target `PAGO_MODO=mercadopago`.

1. Reserva crea `turno(creado)` + `pago(pendiente)` con `idempotency_key` única; se genera preferencia MP (`mp_preference_id`) por el monto de seña del odontólogo.
2. El paciente paga en checkout MP; la app **nunca** confirma el turno por callback del frontend: solo el webhook server-to-server confirma.
3. Pre-reserva con TTL: si no hay aprobación en la ventana, turno `cancelado` (pago fallido) y slot liberado.

## 2. Webhooks

> **MVP (D14)**: el handler es el mismo; en modo simulado el evento lo emite internamente el adaptador (firmado con `MP_WEBHOOK_SECRET`) por pedido del endpoint sandbox. Los ids son sintéticos (`sim_pay_*`, `sim_refund_*`).

- Endpoint público `POST /webhooks/mercadopago`: valida firma (`MP_WEBHOOK_SECRET`) → persiste `evento_pago(webhook_recibido)` con payload crudo → procesa.
- Idempotencia: clave `mp_payment_id`; replays del mismo evento no duplican transiciones (verifican estado actual antes de mutar).
- Tras procesar: `aprobado` → turno `confirmado` + mail confirmación; `rechazado` → turno `cancelado` + aviso.

## 3. Idempotencia (auditoría máxima día 1)

> **MVP (D14)**: sin cambios; vale igual con ids sintéticos y es parte del contrato a testear.

- `UNIQUE` en `pago.idempotency_key`, `pago.mp_payment_id`, `turno.idempotency_key`.
- Reintentos de red/MP: misma key → mismo resultado, sin doble cobro ni doble devolución.

## 4. Bandeja de devoluciones

> **MVP (D14)**: flujo completo; la ejecución la hace el adaptador simulado (`sim_refund_<uuid>`), sin mover dinero. UI con marca "(simulado)".

- Estados: `pendiente → aprobada/rechazada → ejecutada`; cada paso guarda actor + fecha + monto + motivo.
- Porcentajes: 100 % en término / 60 % fuera / 0 % no-show (RN-SENIA-*); el cálculo queda registrado en `devolucion.porcentaje`.
- Ejecución contra API MP guarda `mp_refund_id`; reintentos consultan antes de re-ejecutar.

## 5. Comprobantes

> **MVP (D14)**: PDF con leyenda "SIMULADO — sin valor fiscal ni movimiento de dinero".

- Recibo interno **[v1]** por cada pago aprobado y cada devolución ejecutada (PDF descargable + link en mail).
- `comprobante` separado del turno/pago desde v1; campos ARCA (`cae`, factura A/B/C) **[v2]** apagados pero columnados.

## 6. Conciliación

> **MVP (D14)**: el job se mantiene pero contra el estado del proveedor simulado (compara `pago`/`evento_pago` internos); se reporta como **verificación de consistencia interna**, no contra la API de MP. Caja con banner "(simulado)". Lo de abajo es el target de producción.

- Job diario: compara `pago.estado` local vs. estado MP (API) por `mp_payment_id`; discrepancias → `evento_pago(conciliado)` + alerta en bandeja.
- Exportación CSV/PDF de caja para roles autorizados **[v1]**.

## 7. Audit trail

> **MVP (D14)**: sin cambios; `evento_pago` sigue append-only y registra también los eventos del adaptador simulado.

- `evento_pago` append-only (creado, webhook_recibido, aprobado, rechazado, devolucion_solicitada/aprobada/ejecutada, conciliado) con payload y actor; sin UPDATE/DELETE.
- Trazabilidad turno↔pago↔devolución↔comprobante navegable desde agenda y bandeja.
