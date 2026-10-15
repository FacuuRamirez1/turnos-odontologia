# Tasks

## 1. Schemas + gate de consentimiento (slice vertical 1)

- [ ] 1.1 RED: test `POST /pacientes` sin consentimiento → 422 `CONSENTIMIENTO_REQUERIDO` y cero filas; verificar con `pytest backend/app/tests/test_pacientes_consentimiento.py -k sin_consentimiento` en rojo
- [ ] 1.2 GREEN: schemas Pydantic v2 (`PacienteCreate/Update/Read`, `extra='forbid'`, DNI 7–8 dígitos + normalización) + `PacienteService.create()` con gate + `POST /pacientes` staff-only (`require_role`); verificar test 1.1 en verde + 422 no declara campos extra
- [ ] 1.3 TRIANGULATE borde: DNI `30.123.456` / con espacios se normaliza a `30123456`, duplicado → 409 sin segunda fila, `password`-like campo extra → 422; verificar suite del archivo en verde

## 2. Reconocimiento por DNI A2 (slice vertical 2)

- [ ] 2.1 RED: tests `GET /pacientes?dni=` — match exacto devuelve ficha para precarga, DNI no registrado → 200 vacío uniforme, sin JWT → 401; verificar en rojo con `pytest backend/app/tests/test_pacientes_reconocimiento.py`
- [ ] 2.2 GREEN: implementar `GET /pacientes?dni=` (normaliza, exact-match, respuesta `{found, paciente|null}`, `require_role` staff, rate-limit Redis heredado de C-03); verificar suite 2.1 en verde
- [ ] 2.3 Documentar respuesta uniforme en OpenAPI del router y verificar `GET /api/openapi.json` expone el schema sin campos extra

## 3. Historial acotado + RBAC por rol (slice vertical 3)

- [ ] 3.1 RED: tests `GET /pacientes/{id}/turnos` — devuelve pasado+futuro con solo `{turno_id, odontologo_id, inicio, fin, estado}`, paciente sin turnos → `[]`, token mail de otro paciente → 403, anónimo → 401, DNI solo sin token → 401; verificar en rojo con `pytest backend/app/tests/test_pacientes_historial_rbac.py`
- [ ] 3.2 GREEN: implementar endpoint historial (query solo columnas del contrato, keyset `(inicio,id)`, aislado por `paciente_id`; self-service vía seam action-token C-03 con comparación `token.paciente_id == id`); verificar suite 3.1 en verde
- [ ] 3.3 RBAC matriz: recepcionista ve fichas OK, las 4 prohibiciones siguen 403 a través de estos endpoints; verificar con test parametrizado por rol en verde

## 4. Contrato reserva + integración

- [ ] 4.1 Exponer `PacienteService.resolve_or_create()` reutilizable por C-05 con test de contrato: sin consentimiento levanta `ConsentimientoRequerido` (mapea a 422, UoW aborta sin paciente ni turno — mock de turno, no código C-05); verificar test de contrato en verde
- [ ] 4.2 Integración: `alembic upgrade head` en DB de test + `ruff`/`mypy`/`pytest` backend en verde; verificar `rg create_all backend/app` da cero matches (P3) y que ningún seed/test usa DNI real (patrón ficticio, P11)
- [ ] 4.3 (Opcional, solo si la revisión lo pide) filtro `?odontologo_id` opt-in en historial para rol odontólogo con default sin filtrar; verificar test del filtro en verde sin romper los de 3.1

## Workflow follow-up

- Revisar artefactos y pedir `/opsx:apply c-06-ficha-paciente-consentimiento` en una nueva solicitud (el propose no implementa).
- Tras implementar, `/opsx:archive c-06-ficha-paciente-consentimiento` y tildar C-06 en CHANGES.md.
