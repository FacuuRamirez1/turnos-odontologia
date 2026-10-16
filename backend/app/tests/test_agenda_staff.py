"""Tests C-05 §5.1 — agenda del día + telefónica (RED primero, task 5.1).

Escenarios (U2 feliz / error-negocio / borde):
- feliz: odontólogo ve los suyos (`GET /api/agenda?fecha&odontologo_id`);
- error: odontólogo en ruta telefónica → 403;
- borde: odontólogo no ve turnos ajenos aunque haya seed cruzado;
  recepcionista crea telefónica 201 `canal='recepcion'`.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security.jwt import create_access_token
from app.infra.db.models import Usuario
from app.tests.conftest import TEST_AUTH_SECRET


def _sembrar(db_session: Session) -> dict[str, object]:
    from app.infra.db.models import Odontologo, Paciente, Turno, Usuario

    h = "$2b$04$" + "q" * 53
    fecha = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    ua = Usuario(email=f"od-ag-a-{uuid.uuid4().hex[:6]}@clinica-ficticia.example.ar",
                 password_hash=h, rol="odontologo")
    ub = Usuario(email=f"od-ag-b-{uuid.uuid4().hex[:6]}@clinica-ficticia.example.ar",
                 password_hash=h, rol="odontologo")
    ur = Usuario(email=f"recep-ag-{uuid.uuid4().hex[:6]}@clinica-ficticia.example.ar",
                 password_hash=h, rol="recepcionista")
    db_session.add_all([ua, ub, ur])
    db_session.commit()
    pa = Odontologo(user_id=ua.id, monto_turno=Decimal("70000"), monto_senia=Decimal("65000"))
    pb = Odontologo(user_id=ub.id, monto_turno=Decimal("80000"), monto_senia=Decimal("65000"))
    db_session.add_all([pa, pb])
    db_session.commit()
    ua.odontologo_id, ub.odontologo_id = pa.id, pb.id
    db_session.commit()
    p1 = Paciente(dni=f"55{uuid.uuid4().hex[:6]}", nombre="Ana", apellido="Ficticia",
                  consentimiento_datos=True, consentimiento_fecha=fecha)
    db_session.add(p1)
    db_session.commit()
    ini = datetime.now(UTC).replace(microsecond=0) + timedelta(days=30)
    ini = ini.replace(hour=12, minute=0, second=0, microsecond=0)
    for od_id, key in ((pa.id, "ag-a"), (pb.id, "ag-b")):
        db_session.add(Turno(
            paciente_id=p1.id, odontologo_id=od_id, inicio=ini,
            fin=ini + timedelta(minutes=30), estado="confirmado",
            canal="web", idempotency_key=f"key-{key}-{uuid.uuid4().hex[:8]}"))
    db_session.commit()
    return {"od_a": pa.id, "od_b": pb.id, "fecha": ini.date().isoformat(),
            "ua": ua, "ub": ub, "ur": ur}


def _token(usuario: Usuario, rol: str, od_id: object = None) -> dict[str, str]:
    t = create_access_token(
        sub=str(usuario.id), rol=rol, secret=TEST_AUTH_SECRET,
        odontologo_id=str(od_id) if od_id is not None else None)
    return {"Authorization": f"Bearer {t}"}


def test_odontologo_ve_solo_su_agenda_feliz(
    auth_client: TestClient, db_session: Session,
) -> None:
    ctx = _sembrar(db_session)
    r = auth_client.get("/api/agenda",
                        params={"fecha": cast(str, ctx["fecha"]),
                                "odontologo_id": str(ctx["od_a"])},
                        headers=_token(cast(Usuario, ctx["ua"]), "odontologo", ctx["od_a"]))
    assert r.status_code == 200, r.text
    turnos = r.json()
    assert len(turnos) == 1
    assert turnos[0]["odontologo_id"] == str(ctx["od_a"])


def test_odontologo_en_ruta_telefonica_403_negocio(
    auth_client: TestClient, db_session: Session,
) -> None:
    ctx = _sembrar(db_session)
    r = auth_client.post(
        "/api/reservas/telefonica",
        json={"odontologo_id": str(ctx["od_a"]),
              "inicio": (datetime.now(UTC) + timedelta(days=31)).isoformat(),
              "dni": "55550001", "nombre": "T", "apellido": "F",
              "consentimiento_datos": True,
              "consentimiento_fecha": "2030-01-01T09:00:00+00:00"},
        headers={**_token(cast(Usuario, ctx["ua"]), "odontologo", ctx["od_a"]),
                 "Idempotency-Key": f"rk-{uuid.uuid4().hex[:12]}"})
    assert r.status_code == 403, r.text


def test_odontologo_no_ve_ajenos_aunque_haya_seed_cruzado_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    ctx = _sembrar(db_session)
    # Pide la agenda de B con identidad de A → 403, nunca datos ajenos.
    r = auth_client.get("/api/agenda",
                        params={"fecha": cast(str, ctx["fecha"]),
                                "odontologo_id": str(ctx["od_b"])},
                        headers=_token(cast(Usuario, ctx["ua"]), "odontologo", ctx["od_a"]))
    assert r.status_code == 403, r.text
    # Y su propia agenda no filtra nada de B.
    propia = auth_client.get(
        "/api/agenda",
        params={"fecha": cast(str, ctx["fecha"]), "odontologo_id": str(ctx["od_a"])},
        headers=_token(cast(Usuario, ctx["ua"]), "odontologo", ctx["od_a"]))
    assert propia.status_code == 200
    assert {t["odontologo_id"] for t in propia.json()} == {str(ctx["od_a"])}


def test_recepcionista_reserva_telefonica_201_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    import datetime as dt
    from datetime import time

    from app.infra.db.models import Disponibilidad

    ctx = _sembrar(db_session)
    objetivo = datetime.now(UTC).replace(microsecond=0) + timedelta(days=31)
    db_session.add(Disponibilidad(
        odontologo_id=ctx["od_a"], dia_semana=objetivo.weekday(),
        hora_inicio=time(0, 0), hora_fin=time(23, 30),
        duracion_min=30, tope_dia=48))
    db_session.commit()
    inicio = objetivo.replace(hour=10, minute=0, second=0, microsecond=0)
    r = auth_client.post(
        "/api/reservas/telefonica",
        json={"odontologo_id": str(ctx["od_a"]), "inicio": inicio.isoformat(),
              "dni": "55550002", "nombre": "Tel", "apellido": "Fonica",
              "consentimiento_datos": True,
              "consentimiento_fecha": "2030-01-01T09:00:00+00:00"},
        headers={**_token(cast(Usuario, ctx["ur"]), "recepcionista"),
                 "Idempotency-Key": f"rk-{uuid.uuid4().hex[:12]}"})
    assert r.status_code == 201, r.text
    assert r.json()["canal"] == "recepcion"
    _ = dt
