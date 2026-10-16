"""`Disponibilidad` C-04 — franja semanal por odontólogo (spec § disponibilidad CRUD).

- `odontologo_id`: FK → `odontologo.id` `ON DELETE RESTRICT` + scope P8
  (`BaseRepository` la exige en constructor, fail-closed).
- `dia_semana`: 0=lunes..6=domingo (CHECK).
- `hora_inicio/hora_fin`: TIME con CHECK `hora_fin > hora_inicio` (P6).
- `duracion_min/tope_dia`: INT positivos (CHECK P6, RN-DURACION/RN-TOPE).
- `vigente_desde/hasta`: DATE nullables; CHECK vigencia no invertida.
- No-solape por (odontologo, día, rango): `EXCLUDE USING gist` vive en la
  migración 002 (PG, btree_gist); SQLite de tests no lo soporta, por eso el
  modelo solo declara los CHECKs portables y documenta la exclusión.
"""

import datetime as dt
import uuid

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Integer, Time, text
from sqlalchemy import Uuid as SAUuid
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db.base import Base
from app.infra.db.mixins import AuditMixin


class Disponibilidad(AuditMixin, Base):
    __tablename__ = "disponibilidad"

    odontologo_id: Mapped[uuid.UUID] = mapped_column(
        SAUuid,
        ForeignKey("odontologo.id", ondelete="RESTRICT"),
        nullable=False,
    )
    dia_semana: Mapped[int] = mapped_column(Integer, nullable=False)
    hora_inicio: Mapped[dt.time] = mapped_column(Time, nullable=False)
    hora_fin: Mapped[dt.time] = mapped_column(Time, nullable=False)
    duracion_min: Mapped[int] = mapped_column(Integer, nullable=False)
    tope_dia: Mapped[int] = mapped_column(Integer, nullable=False)
    vigente_desde: Mapped[dt.date | None] = mapped_column(Date, nullable=True, default=None)
    vigente_hasta: Mapped[dt.date | None] = mapped_column(Date, nullable=True, default=None)

    __table_args__ = (
        CheckConstraint("dia_semana >= 0 AND dia_semana <= 6", name="ck_disponibilidad_dia_rango"),
        CheckConstraint("hora_fin > hora_inicio", name="ck_disponibilidad_horas_orden"),
        CheckConstraint("duracion_min > 0", name="ck_disponibilidad_duracion_positiva"),
        CheckConstraint("tope_dia > 0", name="ck_disponibilidad_tope_positivo"),
        CheckConstraint(
            "vigente_desde IS NULL OR vigente_hasta IS NULL OR vigente_desde <= vigente_hasta",
            name="ck_disponibilidad_vigencia_orden",
        ),
    )


Index(
    "ix_disponibilidad_od_dia",
    Disponibilidad.odontologo_id,
    Disponibilidad.dia_semana,
    postgresql_where=text("is_active"),
)
