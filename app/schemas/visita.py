import re
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import MetodoValidacion, VisitaEstado


_POINT_RE = re.compile(
    r"^POINT\s*\(\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s*\)$",
    re.IGNORECASE,
)


class VisitaCreate(BaseModel):
    """Solicitud de check-in. Las coordenadas usan el orden WKT: longitud latitud.

    Qué campos son obligatorios depende de `metodo_validacion`:
    - GPS: `ubicacion_usuario` + `precision_metros`.
    - QR: `codigo_qr` (el código físico del POI, ver GET /poi/{id}/qr-code).
    - MIXTA: los tres, se valida GPS y QR a la vez.
    """

    poi_id: UUID
    metodo_validacion: MetodoValidacion = MetodoValidacion.GPS
    ubicacion_usuario: Optional[str] = Field(
        None, examples=["POINT(-74.08175 4.60971)"], description="WKT POINT(longitud latitud)"
    )
    precision_metros: Optional[float] = Field(None, ge=0, le=1_000)
    codigo_qr: Optional[str] = Field(None, description="Código QR físico del POI")

    @field_validator("ubicacion_usuario")
    @classmethod
    def validar_punto_wkt(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        match = _POINT_RE.fullmatch(value.strip())
        if match is None:
            raise ValueError("ubicacion_usuario debe usar el formato POINT(longitud latitud)")

        longitud, latitud = map(float, match.groups())
        if not -180 <= longitud <= 180 or not -90 <= latitud <= 90:
            raise ValueError("las coordenadas están fuera del rango geográfico válido")
        return f"POINT({longitud} {latitud})"

    @model_validator(mode="after")
    def validar_campos_requeridos_por_metodo(self) -> "VisitaCreate":
        necesita_gps = self.metodo_validacion in (MetodoValidacion.GPS, MetodoValidacion.MIXTA)
        necesita_qr = self.metodo_validacion in (MetodoValidacion.QR, MetodoValidacion.MIXTA)

        if necesita_gps and (self.ubicacion_usuario is None or self.precision_metros is None):
            raise ValueError(
                "ubicacion_usuario y precision_metros son obligatorios para metodo_validacion GPS o MIXTA"
            )
        if necesita_qr and not self.codigo_qr:
            raise ValueError("codigo_qr es obligatorio para metodo_validacion QR o MIXTA")
        return self


class VisitaOut(BaseModel):
    id: UUID
    poi_id: UUID
    estado: VisitaEstado
    distancia_metros: Optional[float] = None
    puntos_otorgados: int
    created_at: datetime


class SaldoPuntosOut(BaseModel):
    saldo: int


class VisitaPoiMini(BaseModel):
    id: UUID
    nombre: str
    slug: str

    class Config:
        from_attributes = True


class VisitaHistorialItem(BaseModel):
    id: UUID
    poi: VisitaPoiMini
    estado: VisitaEstado
    metodo_validacion: MetodoValidacion
    distancia_metros: Optional[float] = None
    puntos_otorgados: int
    created_at: datetime


class PaginatedVisitasResponse(BaseModel):
    items: List[VisitaHistorialItem]
    total: int
    page: int
    page_size: int
