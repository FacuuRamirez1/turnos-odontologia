# Design

## Context

Datos ya existentes (ver proposal.md): `turno`, `turno_historial`, `pago`, `evento_pago`, `devolucion`, `recordatorio_mail`. `domain/reportes/` es un paquete vacío; `domain/notificaciones/metricas.py` ya cuenta mails por estado; `comprobantes/pdf.py` genera PDF a mano sin dependencias; `require_role` y `scoped_odontologo_id` fuerzan RBAC/aislamiento (P8). `frontend/pages/reportes/ReportesPage.tsx` es un stub. No hay migraciones pendientes para este change.

## Goals / Non-Goals

**Goals:**
- Reportes y exportaciones de solo lectura, aislados por profesional, reproducibles.
- Totales de caja derivados de las mismas filas que el detalle (cuadre verificable).

**Non-Goals:**
- Métrica propia de ausentismo (D12/Q8), dashboards gráficos, programación de envíos, XLSX.
- Escrituras en tablas append-only; rutas públicas (P12).

## Decisions

1. **Router `/api/reportes` + servicio en `domain/reportes/`**: consultas SQL agregadas (`GROUP BY`) en `consultas.py`, formateo en `csv_export.py` y `pdf_export.py`; el router solo valida y delega. *Alternativa*: lógica en el router (rechazada: sin testeo unitario).
2. **Aislamiento en el servicio, no en el parámetro**: si el rol es `odontologo` se ignora el `odontologo_id` de la query y se usa `scoped_odontologo_id(ident)`; staff administrativo usa el filtro opcional. Todas las consultas reciben un `odontologo_id | None` ya resuelto.
3. **PDF mínimo propio** reutilizando el enfoque de `comprobantes/pdf.py` (sin dependencia nueva), tabular, con paginado simple y leyenda "(simulado)". *Alternativa*: reportlab (rechazada: dependencia nueva fuera de lo aprobado, P14).
4. **CSV con neutralización de fórmulas** y `csv` de stdlib en `StreamingResponse` (UTF-8 con BOM para Excel). Límite de período configurable (default 366 días) para acotar volumen.
5. **Caja = suma de `pago.estado='aprobado'` y `devolucion.estado='ejecutada'`** por fecha de aprobación/ejecución; el detalle incluye ids para trazabilidad. Un test de cuadre compara contra `evento_pago`. `marca` desde `marca_pago_actual()`.
6. **Auditoría = unión de `turno_historial` y `evento_pago`** ordenada por fecha, exportada solo en CSV; sin payload crudo de webhooks (puede contener datos del proveedor).
7. **Frontend**: módulo `api/reportes.ts` tipado espejo de los schemas Pydantic (`extra='forbid'`, P2); descarga vía `fetch` con bearer y `Blob`, sin guardar nada en storage.

## Risks / Trade-offs

- [Exportación grande bloquea el request] → límite de rango y streaming; paginación diferida.
- [PDF hecho a mano limitado en layout] → tabla simple, aceptable para v1; cambiar a librería es decisión de otro change.
- [Zona horaria en límites de período] → períodos inclusivos en UTC documentados; fechas en la UI interpretadas como día completo.
- [Fuga de datos entre profesionales] → aislamiento forzado en servicio + tests por rol en cada endpoint.

## Open Questions

- Fecha de corte de caja por `created_at` del evento vs. `updated_at` del pago: se usa el evento `webhook_recibido`/`devolucion_ejecutada`; confirmar en apply si hay discrepancias.
