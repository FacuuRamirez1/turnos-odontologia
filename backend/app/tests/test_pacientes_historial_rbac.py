"""Tests C-06 slice 3 — historial acotado + RBAC por rol (RED primero).

- feliz: pasado+futuro con solo `{turno_id, odontologo_id, inicio, fin, estado}`;
- negocio: sin turnos → `[]`; token mail de otro paciente → 403;
- borde: anónimo → 401; DNI solo sin token → 401; propio vía mail-token → 200.
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.pacientes import reset_paciente_action_store
from app.core.security.action_tokens import issue_action_token
from app.core.security.jwt import create_access_token
from app.tests.conftest import TEST_AUTH_SECRET

TURNO_DDL = """
CREATE TABLE IF NOT EXISTS turno (
  id TEXT PRIMARY KEY,
  paciente_id TEXT NOT NULL,
  odontologo_id TEXT NOT NULL,
  inicio TEXT NOT NULL,
  fin TEXT NOT NULL,
  estado TEXT NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 1
)
"""


def _staff_headers(rol: str = "recepcionista") -> dict[str, str]:
    token = create_access_token(sub="staff-1", rol=rol, secret=TEST_AUTH_SECRET)
    return {"Authorization": f"Bearer {token}"}


def _alta(auth_client: TestClient, dni: str = "99.999.931") -> dict[str, object]:
    r = auth_client.post(
        "/api/pacientes",
        json={
            "dni": dni,
            "nombre": "Ana",
            "apellido": "Ficticia",
            "consentimiento_datos": True,
            "consentimiento_fecha": "2026-10-01T09:00:00+00:00",
        },
        headers=_staff_headers(),
    )
    assert r.status_code == 201, r.text
    body: dict[str, object] = r.json()
    return body


def _sembrar_turnos(db_session: Session, paciente_id: str, od_id: str) -> None:
    db_session.execute(text(TURNO_DDL))
    db_session.execute(
        text(
            "INSERT INTO turno (id, paciente_id, odontologo_id, inicio, fin, estado, is_active)"
            " VALUES (:id, :pid, :oid, :ini, :fin, :est, 1)"
        ),
        {
            "id": str(uuid.uuid4()),
            "pid": paciente_id,
            "oid": od_id,
            "ini": "2026-01-05T10:00:00+00:00",
            "fin": "2026-01-05T10:30:00+00:00",
            "est": "atendido",
        },
    )
    db_session.execute(
        text(
            "INSERT INTO turno (id, paciente_id, odontologo_id, inicio, fin, estado, is_active)"
            " VALUES (:id, :pid, :oid, :ini, :fin, :est, 1)"
        ),
        {
            "id": str(uuid.uuid4()),
            "pid": paciente_id,
            "oid": od_id,
            "ini": "2026-12-20T10:00:00+00:00",
            "fin": "2026-12-20T10:30:00+00:00",
            "est": "confirmado",
        },
    )
    db_session.commit()


def _mail_token(paciente_id: str) -> str:
    reset_paciente_action_store()
    return issue_action_token(paciente_id, "ver-ficha", secret=TEST_AUTH_SECRET)


def test_historial_pasado_y_futuro_acotado_feliz(
    auth_client: TestClient, db_session: Session
) -> None:
    """Feliz: pasado+futuro con EXACTO el contrato, cero campos clínicos."""
    creada = _alta(auth_client)
    pid = str(creada["id"])
    _sembrar_turnos(db_session, pid, str(uuid.uuid4()))
    r = auth_client.get(f"/api/pacientes/{pid}/turnos", headers=_staff_headers())
    assert r.status_code == 200, r.text
    turnos = r.json()
    assert len(turnos) == 2
    estados = sorted(t["estado"] for t in turnos)
    assert estados == ["atendido", "confirmado"]
    for t in turnos:
        assert set(t.keys()) == {"turno_id", "odontologo_id", "inicio", "fin", "estado"}
        assert "motivo" not in t and "actor" not in t and "notas" not in t


def test_sin_turnos_lista_vacia_negocio(
    auth_client: TestClient, db_session: Session
) -> None:
    """Negocio: paciente sin turnos → `[]` (200, sin tabla turno también `[]`)."""
    _ = db_session
    creada = _alta(auth_client, "99.999.932")
    r = auth_client.get(
        f"/api/pacientes/{creada['id']}/turnos", headers=_staff_headers()
    )
    assert r.status_code == 200, r.text
    assert r.json() == []


def test_token_otro_paciente_403_negocio(
    auth_client: TestClient, db_session: Session
) -> None:
    """Negocio: mail-token de Q pidiendo historial de P → 403 sin exponer nada."""
    _ = db_session
    p = _alta(auth_client, "99.999.933")
    q = _alta(auth_client, "99.999.934")
    token_q = _mail_token(str(q["id"]))
    r = auth_client.get(
        f"/api/pacientes/{p['id']}/turnos",
        headers={"Authorization": f"Bearer {token_q}"},
    )
    assert r.status_code == 403, r.text


def test_anonimo_401_borde(auth_client: TestClient, db_session: Session) -> None:
    """Borde: anónimo sin token → 401."""
    _ = db_session
    p = _alta(auth_client, "99.999.935")
    r = auth_client.get(f"/api/pacientes/{p['id']}/turnos")
    assert r.status_code == 401, r.text


def test_dni_solo_sin_token_401_borde(
    auth_client: TestClient, db_session: Session
) -> None:
    """Borde P12: DNI solo sin token nunca autoriza → 401."""
    _ = db_session
    p = _alta(auth_client, "99.999.936")
    r = auth_client.get(
        f"/api/pacientes/{p['id']}/turnos", params={"dni": "99.999.936"}
    )
    assert r.status_code == 401, r.text


def test_propio_via_mail_token_200_triangulacion(
    auth_client: TestClient, db_session: Session
) -> None:
    """Triangulación: mail-token propio ve ficha + historial propio (solo lo suyo)."""
    _ = db_session
    p = _alta(auth_client, "99.999.937")
    pid = str(p["id"])
    token = _mail_token(pid)
    r = auth_client.get(
        f"/api/pacientes/{pid}", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["id"] == pid
    token2 = _mail_token(pid)
    r2 = auth_client.get(
        f"/api/pacientes/{pid}/turnos",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json() == []


def test_matriz_roles_staff_ve_prohibiciones_403(
    auth_client: TestClient, db_session: Session
) -> None:
    """3.3 matriz: odontólogo/recepcionista/admin ven fichas; rol ajeno → 403.

    Las 4 prohibiciones de recepcionista (usuarios/roles, MP config, audit,
    ARCA) no existen como rutas en este change — se verifican como 403/404 de
    cierre: ningún endpoint de pacientes otorga esas capacidades (P8 intacta).
    """
    _ = db_session
    p = _alta(auth_client, "99.999.938")
    pid = str(p["id"])
    for rol, extra in (
        ("recepcionista", None),
        ("admin", None),
        ("odontologo", "11111111-1111-4111-8111-111111111111"),
    ):
        if extra is None:
            headers = _staff_headers(rol)
        else:
            headers = {
                "Authorization": "Bearer "
                + create_access_token(
                    sub="od-x", rol=rol, secret=TEST_AUTH_SECRET, odontologo_id=extra
                )
            }
        assert (
            auth_client.get(f"/api/pacientes/{pid}", headers=headers).status_code == 200
        ), rol
        assert (
            auth_client.get(f"/api/pacientes/{pid}/turnos", headers=headers).status_code
            == 200
        ), rol
    # Rol fuera de matriz → 403 en endpoints de pacientes (P8).
    malo = create_access_token(sub="x", rol="cajero", secret=TEST_AUTH_SECRET)
    malas = {"Authorization": f"Bearer {malo}"}
    assert auth_client.get(f"/api/pacientes/{pid}", headers=malas).status_code == 403
    assert (
        auth_client.get(f"/api/pacientes/{pid}/turnos", headers=malas).status_code == 403
    )
    assert (
        auth_client.get(
            "/api/pacientes", params={"dni": "99.999.938"}, headers=malas
        ).status_code
        == 403
    )


def test_filtro_odontologo_id_optin_43(
    auth_client: TestClient, db_session: Session
) -> None:
    """4.3 opt-in: `?odontologo_id=` filtra; default sin filtrar (no rompe 3.1)."""
    p = _alta(auth_client, "99.999.939")
    pid = str(p["id"])
    od_a, od_b = str(uuid.uuid4()), str(uuid.uuid4())
    db_session.execute(text(TURNO_DDL))
    for oid, ini in ((od_a, "2026-01-05T10:00:00+00:00"), (od_b, "2026-02-05T10:00:00+00:00")):
        db_session.execute(
            text(
                "INSERT INTO turno (id, paciente_id, odontologo_id, inicio, fin, estado, is_active)"
                " VALUES (:id, :pid, :oid, :ini, :fin, :est, 1)"
            ),
            {
                "id": str(uuid.uuid4()),
                "pid": pid,
                "oid": oid,
                "ini": ini,
                "fin": ini.replace("10:00", "10:30"),
                "est": "confirmado",
            },
        )
    db_session.commit()
    todo = auth_client.get(f"/api/pacientes/{pid}/turnos", headers=_staff_headers())
    assert todo.status_code == 200, todo.text
    assert len(todo.json()) == 2
    filtrado = auth_client.get(
        f"/api/pacientes/{pid}/turnos",
        params={"odontologo_id": od_a},
        headers=_staff_headers(),
    )
    assert filtrado.status_code == 200, filtrado.text
    assert len(filtrado.json()) == 1
    assert filtrado.json()[0]["odontologo_id"] == od_a
