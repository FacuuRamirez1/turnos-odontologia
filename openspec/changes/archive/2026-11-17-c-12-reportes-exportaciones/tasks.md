# Tasks

> TDD estricto: test en rojo primero (feliz / error de negocio / borde). Sin migraciones.

## 1. Consultas de reporte (dominio)

- [x] 1.1 Escribir tests y luego `domain/reportes/consultas.py::conteo_por_estado` (7 estados con ceros, período, filtro odontólogo); verificar `pytest app/tests/test_reportes_asistencia.py` en verde incluyendo período vacío y `desde > hasta`
- [x] 1.2 Tests y `resumen_caja` (aprobado, devuelto, neto, detalle trazable, excluye no aprobados); verificar `pytest app/tests/test_reportes_caja.py` incluyendo cuadre contra `evento_pago`
- [x] 1.3 Tests y consulta de auditoría (`turno_historial` + `evento_pago`, scoped, sin payload crudo); verificar `pytest app/tests/test_reportes_auditoria.py`

## 2. Exportadores

- [x] 2.1 Tests y `csv_export.py` (cabeceras, comillas, BOM, neutralización de `=+-@`); verificar `pytest app/tests/test_reportes_csv.py`
- [x] 2.2 Tests y `pdf_export.py` (tabla de turnos y caja, leyenda "(simulado)", paginado); verificar `pytest app/tests/test_reportes_pdf.py` (header `%PDF`, texto de marca presente)

## 3. API y RBAC

- [x] 3.1 Tests y router `app/api/reportes.py` (`/asistencia`, `/caja`, `/mail`, `/turnos.csv|pdf`, `/caja.csv|pdf`, `/auditoria.csv`) con schemas `extra='forbid'` y `require_role`; registrar en `main.py`; verificar `pytest app/tests/test_reportes_api.py` (200 por rol, 401, 403, `marca`)
- [x] 3.2 Tests de aislamiento: odontólogo ignora `odontologo_id` ajeno, sin vínculo → 403; verificar `pytest app/tests/test_reportes_scope.py`
- [x] 3.3 Verificar que `PUBLIC_ROUTES` no cambió (P12) y documentar los endpoints en el README del backend; comando: `pytest app/tests/test_p3_v2off.py` + test de rutas públicas existente

## 4. Frontend

- [x] 4.1 Crear `frontend/src/api/reportes.ts` tipado (sin `any`) y tests con Vitest de parseo de errores y descarga Blob; verificar `npm test`
- [x] 4.2 Implementar `ReportesPage.tsx` (filtros, conteos, caja, mail, descargas, banner "(simulado)", estados loading/vacío/error) con tests de componente; verificar `npm run typecheck && npm run lint && npm test && npm run build`
- [x] 4.3 Enrutar/enlazar la página solo para roles staff y testear que un rol no permitido no la ve; verificar test de rutas

## 5. Cierre

- [x] 5.1 Correr suite completa backend + frontend y registrar evidencia TDD (tabla del apply); marcar C-12 `[x]` en `CHANGES.md` solo al archivar
