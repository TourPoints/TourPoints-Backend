from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.enums import CompraEstado, Moneda, PoiEstado


class EstablecimientoCreate(BaseModel):
    """Body for POST /businesses. Requires an already-created POI you own."""

    poi_id: UUID
    nit: Optional[str] = Field(None, max_length=30)
    razon_social: str = Field(..., min_length=1, max_length=200)
    tipo_negocio: Optional[str] = Field(None, max_length=80)


class EstablecimientoOut(BaseModel):
    id: UUID
    poi_id: UUID
    nit: Optional[str] = None
    razon_social: str
    tipo_negocio: Optional[str] = None
    fecha_afiliacion: date
    estado: PoiEstado

    class Config:
        from_attributes = True


class EstablecimientoMeItem(BaseModel):
    """Same as EstablecimientoOut, plus `cargo` (comes from establecimiento_usuarios)."""

    id: UUID
    poi_id: UUID
    nit: Optional[str] = None
    razon_social: str
    tipo_negocio: Optional[str] = None
    fecha_afiliacion: date
    estado: PoiEstado
    cargo: Optional[str] = None


class PaginatedEstablecimientosResponse(BaseModel):
    items: List[EstablecimientoMeItem]
    total: int
    page: int
    page_size: int


class EstablecimientoModeracion(BaseModel):
    estado: str


class CompraCreate(BaseModel):
    """Body for POST /businesses/{id}/purchases."""

    usuario_id: UUID
    valor: Decimal = Field(..., gt=0)
    moneda: Moneda = Moneda.COP
    codigo_transaccion: Optional[str] = Field(None, max_length=60)


class CompraOut(BaseModel):
    id: UUID
    establecimiento_id: UUID
    usuario_id: UUID
    valor: Decimal
    moneda: Moneda
    codigo_transaccion: Optional[str] = None
    estado: CompraEstado
    puntos_otorgados: int
    created_at: datetime


class PromocionCreate(BaseModel):
    """Body for POST /businesses/{id}/promotions. `CHECK (fin > inicio)` in the DB, also validated here."""

    titulo: str = Field(..., min_length=1, max_length=200)
    descripcion: Optional[str] = None
    inicio: datetime
    fin: datetime

    @model_validator(mode="after")
    def validar_vigencia(self) -> "PromocionCreate":
        if self.fin <= self.inicio:
            raise ValueError("fin debe ser posterior a inicio")
        return self


class PromocionModeracion(BaseModel):
    estado: str


class PromocionOut(BaseModel):
    id: UUID
    establecimiento_id: UUID
    titulo: str
    descripcion: Optional[str] = None
    inicio: datetime
    fin: datetime
    estado: PoiEstado

    class Config:
        from_attributes = True


class PaginatedPromocionesResponse(BaseModel):
    items: List[PromocionOut]
    total: int
    page: int
    page_size: int
