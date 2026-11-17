"""Tests C-10 task 1.2 — `GET /api/precios` público (RED primero).

Escenarios (U2 feliz / negocio / borde):
- feliz: lista solo odontólogos activos con `monto_turno`/`monto_senia` +
  trial D11, sin PII de pacientes y con marca `"(simulado)"`;
- negocio: query param no declarado → 422 (contrato cerrado, P2);
- borde: ráfaga sobre el límite público → 429.
"""

import uuid
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api import precios as precios_mod

HASH = "$2b$04$" + "q" * 53


def _sembrar_odonto(
    db_session: Session, *, activo: bool = True,
    monto_turno: str = "70000", monto_senia: str = "65000",
) -> uuid.UUID:
    from app.infra.db.models import Odontologo, Usuario

    suf = uuid.uuid4().hex[:8]
    u = Usuario(email=f"od-precios-{suf}@clinica-ficticia.example.ar",
                password_hash=HASH, rol="odontologo")
    db_session.add(u)
    db_session.commit()
    od = Odontologo(user_id=u.id, monto_turno=Decimal(monto_turno),
                    monto_senia=Decimal(monto_senia), activo=activo)
    db_session.add(od)
    db_session.commit()
    return uuid.UUID(str(od.id))


def test_precios_lista_activos_y_trial_sin_pii_feliz(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Feliz: solo activos, montos públicos, trial D11 y cero PII de pacientes."""
    from datetime import UTC, datetime

    from app.infra.db.models import Paciente

    activo = _sembrar_odonto(db_session)
    _sembrar_odonto(db_session, activo=False, monto_turno="1", monto_senia="1")
    db_session.add(Paciente(dni="99888777", nombre="Paciente", apellido="Oculto",
                            consentimiento_datos=True,
                            consentimiento_fecha=datetime(2026, 10, 1, tzinfo=UTC)))
    db_session.commit()

    precios_mod.reset_precios_limiter(limit=30, window_seconds=60)
    try:
        r = auth_client.get("/api/precios")
    finally:
        precios_mod.reset_precios_limiter()

    assert r.status_code == 200, r.text
    cuerpo = r.json()
    ids = [fila["odontologo_id"] for fila in cuerpo["odontologos"]]
    assert ids == [str(activo)]
    assert Decimal(str(cuerpo["odontologos"][0]["monto_turno"])) == Decimal("70000")
    assert Decimal(str(cuerpo["odontologos"][0]["monto_senia"])) == Decimal("65000")
    assert cuerpo["trial"]["disponible"] is True
    assert cuerpo["trial"]["requiere_tarjeta"] is False
    assert cuerpo["marca"] == "(simulado)"
    assert "99888777" not in r.text
    assert "Oculto" not in r.text


def test_precios_query_extra_rechazada_negocio(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Negocio: parámetro no declarado → 422 por contrato cerrado (P2)."""
    _ = db_session
    precios_mod.reset_precios_limiter(limit=30, window_seconds=60)
    try:
        r = auth_client.get("/api/precios", params={"dni": "99888777"})
    finally:
        precios_mod.reset_precios_limiter()
    assert r.status_code == 422, r.text


def test_precios_rafaga_429_borde(
    auth_client: TestClient, db_session: Session,
) -> None:
    """Borde: supera el umbral público → 429."""
    _sembrar_odonto(db_session)
    precios_mod.reset_precios_limiter(limit=2, window_seconds=60)
    try:
        assert auth_client.get("/api/precios").status_code == 200
        assert auth_client.get("/api/precios").status_code == 200
        assert auth_client.get("/api/precios").status_code == 429
    finally:
        precios_mod.reset_precios_limiter()
