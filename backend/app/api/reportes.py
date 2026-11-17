"""Reportes y exportaciones C-12 (épica F2–F3, RN-AUDIT).

Solo staff (`odontologo|recepcionista|admin`, matriz `03 §2`). El
`odontologo_id` se resuelve en el servidor: un odontólogo SIEMPRE ve lo suyo
(se ignora el parámetro, P8); recepción/admin pueden filtrar. Solo lectura
sobre tablas append-only. Ruta NO pública (P12). Los schemas son
`extra='forbid'` (P2) y la caja lleva `marca` (P15).
"""

import uuid
from datetime import UTC, date, datetime, time
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.security.dependencies import (
    Identity,
    require_role,
    scoped_odontologo_id,
)
from app.domain.notificaciones.metricas import contar_por_estado
from app.domain.pagos.service import marca_pago_actual
from app.domain.reportes.consultas import (
    PeriodoInvalido,
    ResumenCaja,
    conteo_por_estado,
    filas_auditoria,
    listar_turnos,
    resumen_caja,
    validar_periodo,
)
from app.domain.reportes.csv_export import csv_auditoria, csv_caja, csv_turnos
from app.domain.reportes.pdf_export import generar_pdf_tabla
from app.infra.db.session import get_db

router = APIRouter(prefix="/reportes", tags=["reportes"])

STAFF = require_role("odontologo", "recepcionista", "admin")


class Periodo:
    """Período inclusivo en UTC resuelto desde `desde`/`hasta` (días completos)."""

    def __init__(
        self,
        desde: date = Query(...),
        hasta: date = Query(...),
        odontologo_id: uuid.UUID | None = Query(default=None),
        ident: Identity = Depends(STAFF),
    ) -> None:
        self.desde = datetime.combine(desde, time.min, tzinfo=UTC)
        self.hasta = datetime.combine(hasta, time.max, tzinfo=UTC)
        try:
            validar_periodo(self.desde, self.hasta)
        except PeriodoInvalido as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
        # P8: el odontólogo no elige profesional; falla cerrado sin vínculo.
        self.odontologo_id: uuid.UUID | None = (
            scoped_odontologo_id(ident) if ident.rol == "odontologo" else odontologo_id
        )


class AsistenciaOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    desde: datetime
    hasta: datetime
    odontologo_id: uuid.UUID | None
    conteos: dict[str, int]


class MailOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    desde: datetime
    hasta: datetime
    conteos: dict[str, int]


class FilaCajaOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concepto: str
    fecha: datetime
    monto: Decimal
    turno_id: uuid.UUID
    pago_id: uuid.UUID
    devolucion_id: uuid.UUID | None
    odontologo_id: uuid.UUID


class CajaOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    desde: datetime
    hasta: datetime
    odontologo_id: uuid.UUID | None
    marca: str
    total_aprobado: Decimal
    total_devuelto: Decimal
    neto: Decimal
    filas: list[FilaCajaOut]


def _caja_out(p: Periodo, resumen: ResumenCaja) -> CajaOut:
    return CajaOut(
        desde=p.desde,
        hasta=p.hasta,
        odontologo_id=p.odontologo_id,
        marca=marca_pago_actual(),
        total_aprobado=resumen.total_aprobado,
        total_devuelto=resumen.total_devuelto,
        neto=resumen.neto,
        filas=[FilaCajaOut(**vars(f)) for f in resumen.filas],
    )


def _adjunto(contenido: bytes, tipo: str, nombre: str) -> Response:
    return Response(
        content=contenido,
        media_type=tipo,
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get("/asistencia", response_model=AsistenciaOut)
def asistencia(p: Periodo = Depends(), db: Session = Depends(get_db)) -> AsistenciaOut:
    return AsistenciaOut(
        desde=p.desde,
        hasta=p.hasta,
        odontologo_id=p.odontologo_id,
        conteos=conteo_por_estado(db, p.desde, p.hasta, p.odontologo_id),
    )


@router.get("/caja", response_model=CajaOut)
def caja(p: Periodo = Depends(), db: Session = Depends(get_db)) -> CajaOut:
    return _caja_out(p, resumen_caja(db, p.desde, p.hasta, p.odontologo_id))


@router.get("/mail", response_model=MailOut)
def mail(p: Periodo = Depends(), db: Session = Depends(get_db)) -> MailOut:
    """Métricas de entrega C-09 (agregadas, sin datos de pacientes)."""
    return MailOut(desde=p.desde, hasta=p.hasta, conteos=contar_por_estado(db, p.desde, p.hasta))


@router.get("/turnos.csv")
def turnos_csv(p: Periodo = Depends(), db: Session = Depends(get_db)) -> Response:
    turnos = listar_turnos(db, p.desde, p.hasta, p.odontologo_id)
    return _adjunto(csv_turnos(turnos), "text/csv; charset=utf-8", "turnos.csv")


@router.get("/turnos.pdf")
def turnos_pdf(p: Periodo = Depends(), db: Session = Depends(get_db)) -> Response:
    turnos = listar_turnos(db, p.desde, p.hasta, p.odontologo_id)
    filas = [[t.inicio.strftime("%Y-%m-%d %H:%M"), t.estado, t.canal, str(t.odontologo_id)]
             for t in turnos]
    pdf = generar_pdf_tabla(
        "Turnos", ["inicio", "estado", "canal", "odontologo"], filas, marca=""
    )
    return _adjunto(pdf, "application/pdf", "turnos.pdf")


@router.get("/caja.csv")
def caja_csv(p: Periodo = Depends(), db: Session = Depends(get_db)) -> Response:
    resumen = resumen_caja(db, p.desde, p.hasta, p.odontologo_id)
    return _adjunto(
        csv_caja(resumen, marca=marca_pago_actual()), "text/csv; charset=utf-8", "caja.csv"
    )


@router.get("/caja.pdf")
def caja_pdf(p: Periodo = Depends(), db: Session = Depends(get_db)) -> Response:
    resumen = resumen_caja(db, p.desde, p.hasta, p.odontologo_id)
    filas = [[f.concepto, f.fecha.strftime("%Y-%m-%d"), str(f.monto), str(f.pago_id)]
             for f in resumen.filas]
    filas.append(["NETO", "", str(resumen.neto), ""])
    pdf = generar_pdf_tabla(
        "Caja", ["concepto", "fecha", "monto", "pago"], filas, marca=marca_pago_actual()
    )
    return _adjunto(pdf, "application/pdf", "caja.pdf")


@router.get("/auditoria.csv")
def auditoria_csv(p: Periodo = Depends(), db: Session = Depends(get_db)) -> Response:
    filas = filas_auditoria(db, p.desde, p.hasta, p.odontologo_id)
    return _adjunto(csv_auditoria(filas), "text/csv; charset=utf-8", "auditoria.csv")
