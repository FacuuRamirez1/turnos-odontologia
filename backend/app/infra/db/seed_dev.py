"""Seed dev idempotente C-02 (KB `04 §5` acotado al scope: sin turnos/pagos).

Contenido: 2 odontólogos (montos distintos), 1 recepcionista + 1 admin con
hash bcrypt demo FIJO (60 chars, nunca plaintext; solo dev — C-03 hashea de
verdad), 5 pacientes DNI ficticios `99.999.9xx` con consentimiento (P11).
Idempotencia por natural-key vía `ON CONFLICT DO NOTHING` (PG y SQLite).
Feriado + bloqueo de ejemplo: fixture JSON en `seed_data/` (tabla `bloqueo`
= C-04 por Non-Goals). Sin escrituras v2 (P13). Secretos solo por env (P5).
"""

import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.security.passwords import hash_password
from app.infra.db.models import (
    Bloqueo,
    Comprobante,
    Devolucion,
    Disponibilidad,
    EventoPago,
    Odontologo,
    Paciente,
    Pago,
    RecordatorioMail,
    Turno,
    TurnoHistorial,
    Usuario,
)

# Password dev documentada (SOLO dev, nunca producción): C-03 hashea de verdad
# y el spec § passwords exige que todo seed staff autentique con ella (P11: ficticia).
DEV_PASSWORD = "dev-ficticio-123"
DEMO_HASH = hash_password(DEV_PASSWORD)
assert len(DEMO_HASH) == 60

DOMINIO = "clinica-ficticia.example.ar"

# Fechas del seed relativas a "hoy": `turno` tiene CHECK (inicio > now())
# (ck_turno_inicio_futuro, RN-PASADO), así que las fechas fijas de noviembre
# 2026 dejan de insertarse una vez vencidas. Se desplazan en múltiplos de 7
# días (conserva día de semana y distancias relativas); antes del 3/11/2026
# el desplazamiento es 0 y el seed queda idéntico al original.
_SEED_ANCLA = date(2026, 11, 3)  # primer turno del seed
_SHIFT_DIAS = max(0, -(-((datetime.now(UTC).date() - _SEED_ANCLA).days + 1) // 7) * 7)


def _nov(dia: int, hora: int, minuto: int = 0) -> datetime:
    """Datetime UTC del seed (día de noviembre 2026) desplazado a futuro."""
    return datetime(2026, 11, dia, hora, minuto, tzinfo=UTC) + timedelta(days=_SHIFT_DIAS)


CONSENT_AT = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)

ID_ODONTO_1 = uuid.UUID("11111111-1111-4111-8111-111111111111")
ID_USER_ODONTO_1 = uuid.UUID("11111111-1111-4111-8111-111111111112")
ID_ODONTO_2 = uuid.UUID("22222222-2222-4222-8222-222222222222")
ID_USER_ODONTO_2 = uuid.UUID("22222222-2222-4222-8222-222222222223")
ID_RECEP = uuid.UUID("33333333-3333-4333-8333-333333333333")
ID_ADMIN = uuid.UUID("44444444-4444-4434-8444-444444444444")

USUARIOS: list[dict[str, Any]] = [
    {
        "id": ID_USER_ODONTO_1,
        "email": f"odonto1@{DOMINIO}",
        "password_hash": DEMO_HASH,
        "rol": "odontologo",
        "odontologo_id": ID_ODONTO_1,
        "activo": True,
        "is_active": True,
    },
    {
        "id": ID_USER_ODONTO_2,
        "email": f"odonto2@{DOMINIO}",
        "password_hash": DEMO_HASH,
        "rol": "odontologo",
        "odontologo_id": ID_ODONTO_2,
        "activo": True,
        "is_active": True,
    },
    {
        "id": ID_RECEP,
        "email": f"recep@{DOMINIO}",
        "password_hash": DEMO_HASH,
        "rol": "recepcionista",
        "odontologo_id": None,
        "activo": True,
        "is_active": True,
    },
    {
        "id": ID_ADMIN,
        "email": f"admin@{DOMINIO}",
        "password_hash": DEMO_HASH,
        "rol": "admin",
        "odontologo_id": None,
        "activo": True,
        "is_active": True,
    },
]

# Montos demo distintos por profesional (default comercial se cierra en C-07/Q1).
PERFILES: list[dict[str, Any]] = [
    {
        "id": ID_ODONTO_1,
        "user_id": ID_USER_ODONTO_1,
        "monto_turno": Decimal("70000.00"),
        "monto_senia": Decimal("65000.00"),
        "activo": True,
        "is_active": True,
    },
    {
        "id": ID_ODONTO_2,
        "user_id": ID_USER_ODONTO_2,
        "monto_turno": Decimal("80000.00"),
        "monto_senia": Decimal("70000.00"),
        "activo": True,
        "is_active": True,
    },
]

PACIENTES: list[dict[str, Any]] = [
    {
        "id": uuid.UUID(f"90000000-0000-4000-8000-00000000000{i}"),
        "dni": f"99.999.90{i}",
        "nombre": nombre,
        "apellido": "Ficticio/a",
        "email": None,
        "telefono": None,
        "consentimiento_datos": True,
        "consentimiento_fecha": CONSENT_AT,
        "is_active": True,
    }
    for i, nombre in enumerate(
        ("Ana", "Bruno", "Carla", "Diego", "Elena"), start=1
    )
]

# C-04: disponibilidad L–V 9–17 por odontólogo (04 §5: 30 min, tope 14/día).
# IDs deterministas (uuid5) → re-corridas colisionan en PK y se ignoran (P13: nada v2).
VIGENTE_DESDE = date(2026, 1, 1)
VIGENTE_HASTA = date(2026, 12, 31)
DISPONIBILIDAD: list[dict[str, Any]] = [
    {
        "id": uuid.uuid5(uuid.NAMESPACE_OID, f"disponibilidad-{od}-{dia}"),
        "odontologo_id": od,
        "dia_semana": dia,
        "hora_inicio": time(9, 0),
        "hora_fin": time(17, 0),
        "duracion_min": 30,
        "tope_dia": 14,
        "vigente_desde": VIGENTE_DESDE,
        "vigente_hasta": VIGENTE_HASTA,
        "is_active": True,
    }
    for od in (ID_ODONTO_1, ID_ODONTO_2)
    for dia in range(5)
]

# C-04: 1 feriado = 2 filas (D-BLOQ, una por profesional) + 1 bloqueo ejemplo.
# Espeja `seed_data/feriados_bloqueos_ejemplo.json` (DNIs ficticios P11: n/a aqu��).
CORDOBA_FERIADO_DESDE = datetime(2026, 12, 24, 0, 0)
CORDOBA_FERIADO_HASTA = datetime(2026, 12, 26, 23, 59, 59)
BLOQUEOS: list[dict[str, Any]] = [
    {
        "id": uuid.uuid5(uuid.NAMESPACE_OID, f"bloqueo-feriado-{od}"),
        "odontologo_id": od,
        "desde": CORDOBA_FERIADO_DESDE,
        "hasta": CORDOBA_FERIADO_HASTA,
        "motivo": "feriado",
        "created_by": None,
        "is_active": True,
    }
    for od in (ID_ODONTO_1, ID_ODONTO_2)
] + [
    {
        "id": uuid.uuid5(uuid.NAMESPACE_OID, "bloqueo-ejemplo-odonto1"),
        "odontologo_id": ID_ODONTO_1,
        "desde": _nov(2, 13, 0).replace(tzinfo=None),
        "hasta": _nov(2, 14, 0).replace(tzinfo=None),
        "motivo": "bloqueo",
        "created_by": None,
        "is_active": True,
    }
]

# C-08: 1 pago aprobado con recibo + 1 devolucion 60% ejecutada con recibo.
# Proveedor simulado, ids/mp_* deterministicos, DNI ficticios (P11), idempotente.
SEED_INICIO_APROBADO = _nov(3, 12, 0)
SEED_INICIO_DEVUELTO = _nov(4, 12, 0)
ID_TURNO_PAGO_APROBADO = uuid.UUID("55555555-5555-4555-8555-555555555551")
ID_TURNO_DEVUELTO = uuid.UUID("55555555-5555-4555-8555-555555555552")
ID_TURNO_CREADO = uuid.UUID("55555555-5555-4555-8555-555555555553")
ID_TURNO_ATENDIDO = uuid.UUID("55555555-5555-4555-8555-555555555554")
ID_TURNO_CANCELADO = uuid.UUID("55555555-5555-4555-8555-555555555555")
ID_TURNO_REPROGRAMADO = uuid.UUID("55555555-5555-4555-8555-555555555556")
ID_TURNO_NO_SHOW = uuid.UUID("55555555-5555-4555-8555-555555555557")
ID_TURNO_CREADO_2 = uuid.UUID("55555555-5555-4555-8555-555555555558")
ID_TURNO_CONFIRMADO_2 = uuid.UUID("55555555-5555-4555-8555-555555555559")
ID_TURNO_ATENDIDO_2 = uuid.UUID("55555555-5555-4555-8555-55555555555A")
ID_PAGO_APROBADO = uuid.UUID("66666666-6666-4666-8666-666666666661")
ID_PAGO_DEVUELTO = uuid.UUID("66666666-6666-4666-8666-666666666662")
ID_DEVOLUCION_EJECUTADA = uuid.UUID("77777777-7777-4777-8777-777777777771")
ID_COMPROBANTE_PAGO = uuid.UUID("88888888-8888-4888-8888-888888888881")
ID_COMPROBANTE_DEVOLUCION = uuid.UUID("88888888-8888-4888-8888-888888888882")
ID_EVENTO_PAGO_APROBADO_CREADO = uuid.UUID("99999999-9999-4999-8999-999999999901")
ID_EVENTO_PAGO_APROBADO_WEBHOOK = uuid.UUID("99999999-9999-4999-8999-999999999902")
ID_EVENTO_PAGO_DEVUELTO_CREADO = uuid.UUID("99999999-9999-4999-8999-999999999903")
ID_EVENTO_PAGO_DEVUELTO_WEBHOOK = uuid.UUID("99999999-9999-4999-8999-999999999904")
ID_EVENTO_DEV_SOLICITADA = uuid.UUID("99999999-9999-4999-8999-999999999905")
ID_EVENTO_DEV_APROBADA = uuid.UUID("99999999-9999-4999-8999-999999999906")
ID_EVENTO_DEV_EJECUTADA = uuid.UUID("99999999-9999-4999-8999-999999999907")
ID_HIST_APROBADO_CREADO = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1")
ID_HIST_APROBADO_CONFIRMADO = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2")
ID_HIST_DEVUELTO_CREADO = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3")
ID_HIST_DEVUELTO_CONFIRMADO = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa4")
ID_HIST_DEVUELTO_CANCELADO = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa5")
ID_HIST_DEVUELTO_DEVUELTO = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa6")
ID_RECORDATORIO_AVISO_DEVOLUCION = uuid.UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1")

ID_HIST_CREADO_CREADO = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccc01")
ID_HIST_ATENDIDO_CREADO = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccc02")
ID_HIST_ATENDIDO_ATENDIDO = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccc03")
ID_HIST_CANCELADO_CREADO = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccc04")
ID_HIST_CANCELADO_CANCELADO = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccc05")
ID_HIST_REPROGRAMADO_CREADO = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccc06")
ID_HIST_REPROGRAMADO_REPROGRAMADO = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccc07")
ID_HIST_NO_SHOW_CREADO = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccc08")
ID_HIST_NO_SHOW_NO_SHOW = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccc09")
ID_HIST_CREADO_2_CREADO = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccc10")
ID_HIST_CONFIRMADO_2_CREADO = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccc11")
ID_HIST_CONFIRMADO_2_CONFIRMADO = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccc12")
ID_HIST_ATENDIDO_2_CREADO = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccc13")
ID_HIST_ATENDIDO_2_ATENDIDO = uuid.UUID("cccccccc-cccc-4ccc-8ccc-cccccccccc14")

TURNOS: list[dict[str, Any]] = [
    {
        "id": ID_TURNO_PAGO_APROBADO,
        "paciente_id": PACIENTES[0]["id"],
        "odontologo_id": ID_ODONTO_1,
        "inicio": SEED_INICIO_APROBADO,
        "fin": SEED_INICIO_APROBADO.replace(minute=30),
        "estado": "confirmado",
        "canal": "web",
        "idempotency_key": "seed-c08-turno-aprobado",
        "version": 2,
        "pago_id": ID_PAGO_APROBADO,
        "reprogramado_de_id": None,
        "is_active": True,
    },
    {
        "id": ID_TURNO_DEVUELTO,
        "paciente_id": PACIENTES[1]["id"],
        "odontologo_id": ID_ODONTO_1,
        "inicio": SEED_INICIO_DEVUELTO,
        "fin": SEED_INICIO_DEVUELTO.replace(minute=30),
        "estado": "devuelto",
        "canal": "web",
        "idempotency_key": "seed-c08-turno-devuelto",
        "version": 4,
        "pago_id": ID_PAGO_DEVUELTO,
        "reprogramado_de_id": None,
        "is_active": True,
    },
    {
        "id": ID_TURNO_CREADO,
        "paciente_id": PACIENTES[2]["id"],
        "odontologo_id": ID_ODONTO_2,
        "inicio": _nov(5, 9, 0),
        "fin": _nov(5, 9, 30),
        "estado": "creado",
        "canal": "web",
        "idempotency_key": "seed-c13-turno-creado",
        "version": 1,
        "pago_id": None,
        "reprogramado_de_id": None,
        "is_active": True,
    },
    {
        "id": ID_TURNO_ATENDIDO,
        "paciente_id": PACIENTES[3]["id"],
        "odontologo_id": ID_ODONTO_1,
        "inicio": _nov(6, 10, 0),
        "fin": _nov(6, 10, 30),
        "estado": "atendido",
        "canal": "recepcion",
        "idempotency_key": "seed-c13-turno-atendido",
        "version": 2,
        "pago_id": None,
        "reprogramado_de_id": None,
        "is_active": True,
    },
    {
        "id": ID_TURNO_CANCELADO,
        "paciente_id": PACIENTES[4]["id"],
        "odontologo_id": ID_ODONTO_2,
        "inicio": _nov(7, 11, 0),
        "fin": _nov(7, 11, 30),
        "estado": "cancelado",
        "canal": "web",
        "idempotency_key": "seed-c13-turno-cancelado",
        "version": 2,
        "pago_id": None,
        "reprogramado_de_id": None,
        "is_active": True,
    },
    {
        "id": ID_TURNO_REPROGRAMADO,
        "paciente_id": PACIENTES[0]["id"],
        "odontologo_id": ID_ODONTO_1,
        "inicio": _nov(8, 12, 0),
        "fin": _nov(8, 12, 30),
        "estado": "reprogramado",
        "canal": "web",
        "idempotency_key": "seed-c13-turno-reprogramado",
        "version": 2,
        "pago_id": None,
        "reprogramado_de_id": None,
        "is_active": True,
    },
    {
        "id": ID_TURNO_NO_SHOW,
        "paciente_id": PACIENTES[1]["id"],
        "odontologo_id": ID_ODONTO_2,
        "inicio": _nov(9, 13, 0),
        "fin": _nov(9, 13, 30),
        "estado": "no_show",
        "canal": "recepcion",
        "idempotency_key": "seed-c13-turno-no-show",
        "version": 2,
        "pago_id": None,
        "reprogramado_de_id": None,
        "is_active": True,
    },
    {
        "id": ID_TURNO_CREADO_2,
        "paciente_id": PACIENTES[2]["id"],
        "odontologo_id": ID_ODONTO_1,
        "inicio": _nov(10, 14, 0),
        "fin": _nov(10, 14, 30),
        "estado": "creado",
        "canal": "web",
        "idempotency_key": "seed-c13-turno-creado-2",
        "version": 1,
        "pago_id": None,
        "reprogramado_de_id": None,
        "is_active": True,
    },
    {
        "id": ID_TURNO_CONFIRMADO_2,
        "paciente_id": PACIENTES[3]["id"],
        "odontologo_id": ID_ODONTO_2,
        "inicio": _nov(11, 15, 0),
        "fin": _nov(11, 15, 30),
        "estado": "confirmado",
        "canal": "web",
        "idempotency_key": "seed-c13-turno-confirmado-2",
        "version": 2,
        "pago_id": None,
        "reprogramado_de_id": None,
        "is_active": True,
    },
    {
        "id": ID_TURNO_ATENDIDO_2,
        "paciente_id": PACIENTES[4]["id"],
        "odontologo_id": ID_ODONTO_1,
        "inicio": _nov(12, 16, 0),
        "fin": _nov(12, 16, 30),
        "estado": "atendido",
        "canal": "recepcion",
        "idempotency_key": "seed-c13-turno-atendido-2",
        "version": 2,
        "pago_id": None,
        "reprogramado_de_id": None,
        "is_active": True,
    },
]

PAGOS: list[dict[str, Any]] = [
    {
        "id": ID_PAGO_APROBADO,
        "turno_id": ID_TURNO_PAGO_APROBADO,
        "odontologo_id": ID_ODONTO_1,
        "monto": Decimal("65000.00"),
        "moneda": "ARS",
        "proveedor": "simulado",
        "mp_payment_id": "sim_pay_seed_c08_aprobado",
        "mp_preference_id": None,
        "estado": "aprobado",
        "idempotency_key": "idem-seed-c08-pago-aprobado",
        "is_active": True,
    },
    {
        "id": ID_PAGO_DEVUELTO,
        "turno_id": ID_TURNO_DEVUELTO,
        "odontologo_id": ID_ODONTO_1,
        "monto": Decimal("65000.00"),
        "moneda": "ARS",
        "proveedor": "simulado",
        "mp_payment_id": "sim_pay_seed_c08_devuelto",
        "mp_preference_id": None,
        "estado": "reembolsado_parcial",
        "idempotency_key": "idem-seed-c08-pago-devuelto",
        "is_active": True,
    },
]

DEVOLUCIONES: list[dict[str, Any]] = [
    {
        "id": ID_DEVOLUCION_EJECUTADA,
        "pago_id": ID_PAGO_DEVUELTO,
        "turno_id": ID_TURNO_DEVUELTO,
        "monto": Decimal("39000.00"),
        "porcentaje": 60,
        "motivo": "cancelacion fuera de termino (seed C-08)",
        "motivo_rechazo": None,
        "estado": "ejecutada",
        "idempotency_key": f"dev_{ID_PAGO_DEVUELTO}",
        "mp_refund_id": "sim_refund_seed_c08_60",
        "aprobada_por": ID_RECEP,
        "aprobada_at": _nov(4, 10, 0),
        "rechazada_por": None,
        "rechazada_at": None,
        "ejecutada_por": ID_RECEP,
        "ejecutada_at": _nov(4, 10, 5),
        "is_active": True,
    },
]

COMPROBANTES: list[dict[str, Any]] = [
    {
        "id": ID_COMPROBANTE_PAGO,
        "pago_id": ID_PAGO_APROBADO,
        "devolucion_id": None,
        "turno_id": ID_TURNO_PAGO_APROBADO,
        "tipo": "recibo_interno",
        "concepto": "pago",
        "numero": "RI-SEEDC08-000001",
        "monto": Decimal("65000.00"),
        "moneda": "ARS",
        "cae": None,
        "emitida_at": _nov(3, 12, 5),
        "simulado": True,
        "payload_json": {
            "concepto": "pago",
            "paciente_nombre": "Ana",
            "paciente_apellido": "Ficticio/a",
            "odontologo": f"odonto1@{DOMINIO}",
            "fecha_turno": SEED_INICIO_APROBADO.isoformat(),
            "porcentaje": None,
            "monto": "65000.00",
        },
    },
    {
        "id": ID_COMPROBANTE_DEVOLUCION,
        "pago_id": ID_PAGO_DEVUELTO,
        "devolucion_id": ID_DEVOLUCION_EJECUTADA,
        "turno_id": ID_TURNO_DEVUELTO,
        "tipo": "recibo_interno",
        "concepto": "devolucion",
        "numero": "RI-SEEDC08-000002",
        "monto": Decimal("39000.00"),
        "moneda": "ARS",
        "cae": None,
        "emitida_at": _nov(4, 10, 6),
        "simulado": True,
        "payload_json": {
            "concepto": "devolucion",
            "paciente_nombre": "Bruno",
            "paciente_apellido": "Ficticio/a",
            "odontologo": f"odonto1@{DOMINIO}",
            "fecha_turno": SEED_INICIO_DEVUELTO.isoformat(),
            "porcentaje": 60,
            "monto": "39000.00",
        },
    },
]

EVENTOS_PAGO: list[dict[str, Any]] = [
    {
        "id": ID_EVENTO_PAGO_APROBADO_CREADO,
        "pago_id": ID_PAGO_APROBADO,
        "tipo_evento": "creado",
        "payload_json": {"monto": "65000.00", "moneda": "ARS"},
        "actor": "sistema",
        "created_at": _nov(3, 9, 0),
    },
    {
        "id": ID_EVENTO_PAGO_APROBADO_WEBHOOK,
        "pago_id": ID_PAGO_APROBADO,
        "tipo_evento": "webhook_recibido",
        "payload_json": {"kind": "pago", "status": "aprobado"},
        "actor": "sistema",
        "created_at": _nov(3, 9, 1),
    },
    {
        "id": ID_EVENTO_PAGO_DEVUELTO_CREADO,
        "pago_id": ID_PAGO_DEVUELTO,
        "tipo_evento": "creado",
        "payload_json": {"monto": "65000.00", "moneda": "ARS"},
        "actor": "sistema",
        "created_at": _nov(4, 9, 0),
    },
    {
        "id": ID_EVENTO_PAGO_DEVUELTO_WEBHOOK,
        "pago_id": ID_PAGO_DEVUELTO,
        "tipo_evento": "webhook_recibido",
        "payload_json": {"kind": "pago", "status": "aprobado"},
        "actor": "sistema",
        "created_at": _nov(4, 9, 1),
    },
    {
        "id": ID_EVENTO_DEV_SOLICITADA,
        "pago_id": ID_PAGO_DEVUELTO,
        "tipo_evento": "devolucion_solicitada",
        "payload_json": {"porcentaje": 60, "monto": "39000.00", "actor_id": str(ID_RECEP)},
        "actor": "recepcionista",
        "created_at": _nov(4, 9, 55),
    },
    {
        "id": ID_EVENTO_DEV_APROBADA,
        "pago_id": ID_PAGO_DEVUELTO,
        "tipo_evento": "devolucion_aprobada",
        "payload_json": {"porcentaje": 60, "monto": "39000.00", "actor_id": str(ID_RECEP)},
        "actor": "recepcionista",
        "created_at": _nov(4, 10, 0),
    },
    {
        "id": ID_EVENTO_DEV_EJECUTADA,
        "pago_id": ID_PAGO_DEVUELTO,
        "tipo_evento": "devolucion_ejecutada",
        "payload_json": {
            "porcentaje": 60,
            "monto": "39000.00",
            "mp_refund_id": "sim_refund_seed_c08_60",
            "solicitado_por": str(ID_RECEP),
        },
        "actor": "sistema",
        "created_at": _nov(4, 10, 5),
    },
]

TURNOS_HISTORIAL: list[dict[str, Any]] = [
    {
        "id": ID_HIST_APROBADO_CREADO,
        "turno_id": ID_TURNO_PAGO_APROBADO,
        "estado_anterior": "creado",
        "estado_nuevo": "creado",
        "actor_tipo": "paciente",
        "actor_id": "seed-c08",
        "fecha": _nov(3, 9, 0),
        "motivo": "reserva seed C-08",
    },
    {
        "id": ID_HIST_APROBADO_CONFIRMADO,
        "turno_id": ID_TURNO_PAGO_APROBADO,
        "estado_anterior": "creado",
        "estado_nuevo": "confirmado",
        "actor_tipo": "sistema",
        "actor_id": "sistema",
        "fecha": _nov(3, 9, 1),
        "motivo": "pago aprobado via webhook (seed C-08)",
    },
    {
        "id": ID_HIST_DEVUELTO_CREADO,
        "turno_id": ID_TURNO_DEVUELTO,
        "estado_anterior": "creado",
        "estado_nuevo": "creado",
        "actor_tipo": "paciente",
        "actor_id": "seed-c08",
        "fecha": _nov(4, 9, 0),
        "motivo": "reserva seed C-08",
    },
    {
        "id": ID_HIST_DEVUELTO_CONFIRMADO,
        "turno_id": ID_TURNO_DEVUELTO,
        "estado_anterior": "creado",
        "estado_nuevo": "confirmado",
        "actor_tipo": "sistema",
        "actor_id": "sistema",
        "fecha": _nov(4, 9, 1),
        "motivo": "pago aprobado via webhook (seed C-08)",
    },
    {
        "id": ID_HIST_DEVUELTO_CANCELADO,
        "turno_id": ID_TURNO_DEVUELTO,
        "estado_anterior": "confirmado",
        "estado_nuevo": "cancelado",
        "actor_tipo": "recepcionista",
        "actor_id": str(ID_RECEP),
        "fecha": _nov(4, 9, 55),
        "motivo": "cancelacion fuera de termino (seed C-08)",
    },
    {
        "id": ID_HIST_DEVUELTO_DEVUELTO,
        "turno_id": ID_TURNO_DEVUELTO,
        "estado_anterior": "cancelado",
        "estado_nuevo": "devuelto",
        "actor_tipo": "sistema",
        "actor_id": "sistema",
        "fecha": _nov(4, 10, 5),
        "motivo": "devolucion sim_refund_seed_c08_60 ejecutada (seed C-08)",
    },
    {
        "id": ID_HIST_CREADO_CREADO,
        "turno_id": ID_TURNO_CREADO,
        "estado_anterior": "creado",
        "estado_nuevo": "creado",
        "actor_tipo": "paciente",
        "actor_id": str(PACIENTES[2]["id"]),
        "fecha": _nov(5, 9, 0),
        "motivo": "reserva seed C-13",
    },
    {
        "id": ID_HIST_ATENDIDO_CREADO,
        "turno_id": ID_TURNO_ATENDIDO,
        "estado_anterior": "creado",
        "estado_nuevo": "creado",
        "actor_tipo": "paciente",
        "actor_id": str(PACIENTES[3]["id"]),
        "fecha": _nov(6, 9, 0),
        "motivo": "reserva seed C-13",
    },
    {
        "id": ID_HIST_ATENDIDO_ATENDIDO,
        "turno_id": ID_TURNO_ATENDIDO,
        "estado_anterior": "creado",
        "estado_nuevo": "atendido",
        "actor_tipo": "odontologo",
        "actor_id": str(ID_ODONTO_1),
        "fecha": _nov(6, 10, 30),
        "motivo": "atendido en consulta (seed C-13)",
    },
    {
        "id": ID_HIST_CANCELADO_CREADO,
        "turno_id": ID_TURNO_CANCELADO,
        "estado_anterior": "creado",
        "estado_nuevo": "creado",
        "actor_tipo": "paciente",
        "actor_id": str(PACIENTES[4]["id"]),
        "fecha": _nov(7, 9, 0),
        "motivo": "reserva seed C-13",
    },
    {
        "id": ID_HIST_CANCELADO_CANCELADO,
        "turno_id": ID_TURNO_CANCELADO,
        "estado_anterior": "creado",
        "estado_nuevo": "cancelado",
        "actor_tipo": "recepcionista",
        "actor_id": str(ID_RECEP),
        "fecha": _nov(7, 10, 0),
        "motivo": "cancelacion por paciente (seed C-13)",
    },
    {
        "id": ID_HIST_REPROGRAMADO_CREADO,
        "turno_id": ID_TURNO_REPROGRAMADO,
        "estado_anterior": "creado",
        "estado_nuevo": "creado",
        "actor_tipo": "paciente",
        "actor_id": str(PACIENTES[0]["id"]),
        "fecha": _nov(8, 9, 0),
        "motivo": "reserva seed C-13",
    },
    {
        "id": ID_HIST_REPROGRAMADO_REPROGRAMADO,
        "turno_id": ID_TURNO_REPROGRAMADO,
        "estado_anterior": "creado",
        "estado_nuevo": "reprogramado",
        "actor_tipo": "recepcionista",
        "actor_id": str(ID_RECEP),
        "fecha": _nov(8, 11, 0),
        "motivo": "reprogramacion a las 12:00 (seed C-13)",
    },
    {
        "id": ID_HIST_NO_SHOW_CREADO,
        "turno_id": ID_TURNO_NO_SHOW,
        "estado_anterior": "creado",
        "estado_nuevo": "creado",
        "actor_tipo": "paciente",
        "actor_id": str(PACIENTES[1]["id"]),
        "fecha": _nov(9, 9, 0),
        "motivo": "reserva seed C-13",
    },
    {
        "id": ID_HIST_NO_SHOW_NO_SHOW,
        "turno_id": ID_TURNO_NO_SHOW,
        "estado_anterior": "creado",
        "estado_nuevo": "no_show",
        "actor_tipo": "sistema",
        "actor_id": "sistema",
        "fecha": _nov(9, 13, 30),
        "motivo": "no show (seed C-13)",
    },
    {
        "id": ID_HIST_CREADO_2_CREADO,
        "turno_id": ID_TURNO_CREADO_2,
        "estado_anterior": "creado",
        "estado_nuevo": "creado",
        "actor_tipo": "paciente",
        "actor_id": str(PACIENTES[2]["id"]),
        "fecha": _nov(10, 9, 0),
        "motivo": "reserva seed C-13",
    },
    {
        "id": ID_HIST_CONFIRMADO_2_CREADO,
        "turno_id": ID_TURNO_CONFIRMADO_2,
        "estado_anterior": "creado",
        "estado_nuevo": "creado",
        "actor_tipo": "paciente",
        "actor_id": str(PACIENTES[3]["id"]),
        "fecha": _nov(11, 9, 0),
        "motivo": "reserva seed C-13",
    },
    {
        "id": ID_HIST_CONFIRMADO_2_CONFIRMADO,
        "turno_id": ID_TURNO_CONFIRMADO_2,
        "estado_anterior": "creado",
        "estado_nuevo": "confirmado",
        "actor_tipo": "sistema",
        "actor_id": "sistema",
        "fecha": _nov(11, 9, 1),
        "motivo": "pago aprobado via webhook (seed C-13)",
    },
    {
        "id": ID_HIST_ATENDIDO_2_CREADO,
        "turno_id": ID_TURNO_ATENDIDO_2,
        "estado_anterior": "creado",
        "estado_nuevo": "creado",
        "actor_tipo": "paciente",
        "actor_id": str(PACIENTES[4]["id"]),
        "fecha": _nov(12, 9, 0),
        "motivo": "reserva seed C-13",
    },
    {
        "id": ID_HIST_ATENDIDO_2_ATENDIDO,
        "turno_id": ID_TURNO_ATENDIDO_2,
        "estado_anterior": "creado",
        "estado_nuevo": "atendido",
        "actor_tipo": "odontologo",
        "actor_id": str(ID_ODONTO_1),
        "fecha": _nov(12, 16, 30),
        "motivo": "atendido en consulta (seed C-13)",
    },
]

RECORDATORIOS_MAIL: list[dict[str, Any]] = [
    {
        "id": ID_RECORDATORIO_AVISO_DEVOLUCION,
        "turno_id": ID_TURNO_DEVUELTO,
        "tipo": "aviso_devolucion",
        "destinatario": "",
        "plantilla_version": "v2",
        "estado": "fallido",
        "intentos": 0,
        "ultimo_error": "paciente sin email (seed C-08)",
        "proximo_intento_at": None,
        "enviado_at": None,
        "publicado_at": None,
        "token_accion_hash": None,
        "token_expira_at": None,
        "token_usado_at": None,
        "contexto_json": {
            "porcentaje": 60,
            "resultado": "ejecutada",
            "monto": "39000.00",
            "comprobante_id": str(ID_COMPROBANTE_DEVOLUCION),
        },
        "is_active": True,
    },
]


def _insert_do_nothing(
    session: Session,
    model: type[
        Usuario
        | Odontologo
        | Paciente
        | Disponibilidad
        | Bloqueo
        | Turno
        | Pago
        | Devolucion
        | Comprobante
        | EventoPago
        | TurnoHistorial
        | RecordatorioMail
    ],
    rows: list[dict[str, Any]],
) -> None:
    """`INSERT … ON CONFLICT DO NOTHING` portable (PG prod, SQLite tests)."""
    bind = session.get_bind()
    dialecto = bind.dialect.name if bind is not None else "postgresql"
    if dialecto == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        session.execute(pg_insert(model).values(rows).on_conflict_do_nothing())
    else:
        from sqlalchemy.dialects.sqlite import insert as lite_insert

        session.execute(lite_insert(model).values(rows).on_conflict_do_nothing())


def seed(session: Session) -> None:
    """Aplica el seed dev; re-corridas no duplican (natural keys, IDs deterministas)."""
    _insert_do_nothing(session, Usuario, USUARIOS)
    _insert_do_nothing(session, Odontologo, PERFILES)
    _insert_do_nothing(session, Paciente, PACIENTES)
    _insert_do_nothing(session, Disponibilidad, DISPONIBILIDAD)
    _insert_do_nothing(session, Bloqueo, BLOQUEOS)
    _insert_do_nothing(session, Turno, TURNOS)
    _insert_do_nothing(session, Pago, PAGOS)
    _insert_do_nothing(session, Devolucion, DEVOLUCIONES)
    _insert_do_nothing(session, Comprobante, COMPROBANTES)
    _insert_do_nothing(session, EventoPago, EVENTOS_PAGO)
    _insert_do_nothing(session, TurnoHistorial, TURNOS_HISTORIAL)
    _insert_do_nothing(session, RecordatorioMail, RECORDATORIOS_MAIL)
    session.commit()


def main() -> None:
    """Punto de entrada manual: `python -m app.infra.db.seed_dev` (asume 001 aplicada)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.settings import get_settings

    engine = create_engine(get_settings().database_url, future=True)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    with factory() as session:
        seed(session)
    print("seed dev C-02 aplicado (idempotente, ON CONFLICT DO NOTHING).")


if __name__ == "__main__":
    main()
