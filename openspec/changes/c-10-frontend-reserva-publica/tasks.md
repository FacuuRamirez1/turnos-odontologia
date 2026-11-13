# Tasks: `C-10` — `frontend-reserva-publica`

> **Alcance TP Metodología I**: Este change está **preparado** en fase OPSX (`proposal.md`, `specs/`, `design.md`, `tasks.md`). Las tareas permanecen pendientes (`[ ]`) hasta la instancia posterior de implementación y archivado. En toda tarea de producción aplica TDD (`U2`: RED → GREEN → TRIANGULATE con 3 escenarios: funcionamiento esperado, error de negocio y caso borde).

## 1. Costuras mínimas de Backend y Test Runner Frontend

- [ ] 1.1 Exponer `pago_id` en `ReservaOut` y en la query string de `PagoSimuladoAdapter.generar_checkout` (`/checkout-simulado?pago_id=...&token=...`), aplicando TDD con 3 escenarios en `pytest` (feliz: `POST /api/reservas` devuelve `pago_id` + `checkout_token` + URL válida; error de negocio: intento de reserva sin consentimiento retorna `422`; borde: turno con seña $0 omite checkout sin fallar). Verificación: `pytest backend/tests -k "reserva and pago"`.
- [ ] 1.2 Implementar router `backend/app/api/precios.py` para `GET /api/precios` (`extra="forbid"`, rate-limit público, sin PII de pacientes), verificando en `pytest` 3 escenarios (feliz: lista aranceles activos y datos de trial `D11`; error de negocio: query extra no declarada rechazada por `extra="forbid"`; borde: supera umbral de rate-limit público retornando `429`). Verificación: `pytest backend/tests -k precios`.
- [ ] 1.3 Agregar soporte JSON en `GET /api/mail/confirmar` y `GET /api/mail/cancelar` (vía cabecera `Accept: application/json`, preservando retrocompatibilidad con `C-09`), verificando en `pytest` 3 escenarios (feliz: token válido confirma/cancela y responde JSON estructurado; error de negocio: token expirado o ya usado retorna `400`/`409` en JSON; borde: petición HTML estándar sigue funcionando sin romper tests de `C-09`). Verificación: `pytest backend/tests -k mail`.
- [ ] 1.4 Configurar `vitest`, `@testing-library/react`, `@testing-library/jest-dom` y `jsdom` en `frontend/package.json` + script `"test": "vitest run"`, verificando que el runner arranca en TypeScript estricto sin `any`. Verificación: `npm --prefix frontend run test` y `npm --prefix frontend run typecheck`.

## 2. Cliente API Público y Tipado Estricto (`P1`, `P2`, `P12`)

- [ ] 2.1 Definir en `frontend/src/api/types.ts` y `frontend/src/api/public.ts` los contratos estrictos (sin `any`, `auth: false` en `apiFetch`) para precios, disponibilidad, reserva, checkout simulado, estado de pago, `/mis-turnos` y acciones de mail, verificando tests unitarios de serialización y mapeo de errores (`400/404/409/422/429`). Verificación: `npm --prefix frontend run test -- publicClient` y `npm --prefix frontend run typecheck`.

## 3. Wizard Público de Reserva y Checkout Simulado (`/reservar`, `/checkout-simulado`)

- [ ] 3.1 Implementar `ReservaPage` (`frontend/src/pages/reserva/ReservaPage.tsx` y subcomponentes en PascalCase con imports de `"react-router-dom"` `6.28.0`) con pasos Datos+Consentimiento → Profesional (`monto_turno` + `monto_senia`) → Fecha/Hora (`GET /api/disponibilidad`) → Confirmación (`POST /api/reservas`), cubriendo en tests RTL los 3 escenarios (feliz: reserva completa navega a `/checkout-simulado`; error de negocio: `consentimiento_datos=false` bloquea avance y `409` devuelve al Paso 3 conservando datos del Paso 1; borde: fechas pasadas o por debajo de anticipación mínima `Q1` deshabilitadas/advertidas y recarga de slots). Verificación: `npm --prefix frontend run test -- ReservaPage`.
- [ ] 3.2 Implementar `CheckoutSimuladoPage` (`frontend/src/pages/reserva/CheckoutSimuladoPage.tsx`) leyendo `?pago_id=&token=` con `useSearchParams` de `"react-router-dom"`, mostrando banner `"(simulado)"`, botones Aprobar/Rechazar/Expirar hacia `POST /api/pagos/{pago_id}/simular` y lectura real vía `GET /api/pagos/{pago_id}`, cubriendo en tests RTL los 3 escenarios (feliz: aprobar refleja estado `pagado/confirmado (simulado)` desde servidor; error de negocio: rechazar/expirar informa liberación de slot y ofrece volver a `/reservar`; borde: reintentar con `checkout_token` consumido o faltante muestra bloqueo idempotente sin confirmar en cliente). Verificación: `npm --prefix frontend run test -- CheckoutSimuladoPage`.

## 4. Páginas de Mail, Mis Turnos y Precios (`/mail/*`, `/mis-turnos`, `/precios`)

- [ ] 4.1 Implementar `MailAccionPage` para `/mail/confirmar` y `/mail/cancelar` leyendo `?token=` con `useSearchParams`, cubriendo en tests RTL los 3 escenarios (feliz: confirmación/cancelación exitosa en estado legible; error de negocio: token inválido/expirado muestra mensaje claro y enlace a `/reservar`; borde: acceso sin `token` en querystring evita llamadas rotas y guía al paciente). Verificación: `npm --prefix frontend run test -- MailAccionPage`.
- [ ] 4.2 Implementar `MisTurnosPage` (`/mis-turnos`) exigiendo `dni + token` (`P12`), mostrando reglas de cancelación/reprogramación desde `cotizar-cancelacion` (respetando `Q3` sin calcular seña en cliente) y `PreciosPage` (`/precios`), cubriendo en tests RTL los 3 escenarios (feliz: lista turnos del paciente con `dni + token` y muestra tarifas/trial; error de negocio: consulta solo con DNI sin token bloqueada en UI/cliente; borde: backend responde `429` o turno no cancelable mostrando mensaje amigable sin filtrar PII ajena). Verificación: `npm --prefix frontend run test -- MisTurnosPage PreciosPage`.
- [ ] 4.3 Registrar las rutas públicas en `frontend/src/App.tsx` (`/reservar`, `/checkout-simulado`, `/mail/confirmar`, `/mail/cancelar`, `/mis-turnos`, `/precios`) usando exclusivamente `"react-router-dom"`, y verificar flujo de integración completo (wizard → checkout simulado → estado final) con tests RTL. Verificación: `npm --prefix frontend run test -- PublicRoutes`.

## 5. Verificación Integrada de Calidad y Reglas Duras

- [ ] 5.1 Ejecutar suite completa de checks backend + frontend al finalizar la implementación: `pytest backend/tests`, `npm --prefix frontend run typecheck`, `npm --prefix frontend run lint`, `npm --prefix frontend run test` y `npm --prefix frontend run build`, confirmando cero `any`, cero fugas PII y presencia explícita de `"(simulado)"`. Verificación: todos los comandos retornan código de salida `0`.

## Workflow follow-up

- Implementar las tareas `1.1` a `5.1` mediante `/opsx:apply c-10-frontend-reserva-publica` en una instancia posterior (fuera del alcance del TP actual).
- Una vez implementadas y verificadas todas las tareas, ejecutar `/opsx:archive c-10-frontend-reserva-publica` y actualizar `CHANGES.md` a `[x]`.
