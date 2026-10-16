"""Servicio de ficha mínima C-06 — gate RN-CONSENTIMIENTO + DNI normalizado (design D1).

- `normalizar_dni`: quita puntos/espacios/guiones antes de validar (design Riesgo 3).
- `PacienteService.create`: valida consentimiento true + timestamp ANTES de
  persistir; sin consentimiento levanta `ConsentimientoRequerido` (→ 422
  `CONSENTIMIENTO_REQUERIDO`, UoW aborta sin fila). Duplicado → `PacienteDuplicado`
  (→ 409); `UNIQUE(dni)` DB arbitra la carrera (design Riesgo 4).
"""

import re
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infra.db.models import Paciente


def normalizar_dni(dni: str) -> str:
    """Normaliza DNI AR: quita puntos, espacios y guiones (un único helper)."""
    return re.sub(r"[\s.\-]", "", dni.strip())


def validar_formato_dni(normalizado: str) -> None:
    """7–8 dígitos exactos; letras o longitud errónea → ValueError (→ 422)."""
    if not re.fullmatch(r"[0-9]{7,8}", normalizado):
        raise ValueError("DNI debe tener 7–8 dígitos")


class ConsentimientoRequerido(Exception):
    """Sin `consentimiento_datos=true` + fecha no se persiste nada (RN-CONSENTIMIENTO)."""


class PacienteDuplicado(Exception):
    """DNI ya registrado (tras normalizar) — sin segunda fila."""


class PacienteService:
    """Gate de consentimiento + alta mínima (reutilizable por C-05 vía `resolve_or_create`)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        dni: str,
        nombre: str,
        apellido: str,
        email: str | None = None,
        telefono: str | None = None,
        consentimiento_datos: bool = False,
        consentimiento_fecha: datetime | None = None,
    ) -> Paciente:
        """Crea la ficha solo con consentimiento explícito + timestamp."""
        if consentimiento_datos is not True or consentimiento_fecha is None:
            raise ConsentimientoRequerido("se requiere consentimiento_datos=true con fecha")
        normalizado = normalizar_dni(dni)
        validar_formato_dni(normalizado)
        existente = (
            self._session.query(Paciente).filter(Paciente.dni == normalizado).first()
        )
        if existente is not None:
            raise PacienteDuplicado("DNI ya registrado")
        fila = Paciente(
            dni=normalizado,
            nombre=nombre.strip(),
            apellido=apellido.strip(),
            email=email.strip() if email else None,
            telefono=telefono.strip() if telefono else None,
            consentimiento_datos=True,
            consentimiento_fecha=consentimiento_fecha,
        )
        self._session.add(fila)
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise PacienteDuplicado("DNI ya registrado") from exc
        self._session.refresh(fila)
        return fila

    def resolve_or_create(
        self,
        *,
        dni: str,
        nombre: str,
        apellido: str,
        email: str | None = None,
        telefono: str | None = None,
        consentimiento_datos: bool = False,
        consentimiento_fecha: datetime | None = None,
    ) -> tuple[Paciente, bool]:
        """Contrato hacia C-05: reutiliza por DNI o crea con el mismo gate.

        Retorna `(paciente, creado)`. Sin consentimiento levanta
        `ConsentimientoRequerido` ANTES de persistir (la UoW de reserva debe
        abortar sin paciente ni turno — C-05 honra el 422).
        """
        normalizado = normalizar_dni(dni)
        validar_formato_dni(normalizado)
        existente = (
            self._session.query(Paciente).filter(Paciente.dni == normalizado).first()
        )
        if existente is not None:
            if not bool(existente.is_active):
                raise PacienteDuplicado("DNI ya registrado")
            return existente, False
        creado = self.create(
            dni=normalizado,
            nombre=nombre,
            apellido=apellido,
            email=email,
            telefono=telefono,
            consentimiento_datos=consentimiento_datos,
            consentimiento_fecha=consentimiento_fecha,
        )
        return creado, True
