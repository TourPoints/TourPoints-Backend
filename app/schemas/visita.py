import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import MetodoValidacion, VisitaEstado


_POINT_RE = re.compile(
    r"^POINT\s*\(\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s*\)$",
    re.IGNORECASE,
)


class VisitaCreate(BaseModel):
    """Solicitud de visita GPS. Las coordenadas usan el orden WKT: longitud latitud."""

    poi_id: UUID
    ubicacion_usuario: str = Field(
        ..., examples=["POINT(-74.08175 4.60971)"], description="WKT POINT(longitud latitud)"
    )
    precision_metros: float = Field(..., ge=0, le=1_000)
    metodo_validacion: MetodoValidacion = MetodoValidacion.GPS

    @field_validator("ubicacion_usuario")
    @classmethod
    def validar_punto_wkt(cls, value: str) -> str:
        match = _POINT_RE.fullmatch(value.strip())
        if match is None:
            raise ValueError("ubicacion_usuario debe usar el formato POINT(longitud latitud)")

        longitud, latitud = map(float, match.groups())
        if not -180 <= longitud <= 180 or not -90 <= latitud <= 90:
            raise ValueError("las coordenadas están fuera del rango geográfico válido")
        return f"POINT({longitud} {latitud})"


class VisitaOut(BaseModel):
    id: UUID
    poi_id: UUID
    estado: VisitaEstado
    distancia_metros: float
    puntos_otorgados: int
    created_at: datetime


class SaldoPuntosOut(BaseModel):
    saldo: int
