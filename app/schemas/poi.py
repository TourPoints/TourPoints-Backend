from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class Coordenadas(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class CategoriaPoiOut(BaseModel):
    id: int
    nombre: str
    icono: Optional[str] = None
    color: Optional[str] = None

    class Config:
        from_attributes = True


class CiudadOut(BaseModel):
    id: int
    nombre: str

    class Config:
        from_attributes = True


class ImagenPoiOut(BaseModel):
    id: int
    url: str
    orden: int
    principal: bool

    class Config:
        from_attributes = True


class ImagenPoiCreateOut(ImagenPoiOut):
    poi_id: UUID


class PoiBase(BaseModel):
    categoria_id: int
    ciudad_id: int
    nombre: str = Field(..., min_length=1, max_length=200)
    descripcion: Optional[str] = None
    direccion: Optional[str] = None
    ubicacion: Coordenadas
    radio_validacion: int = Field(50, gt=0)
    telefono: Optional[str] = Field(None, max_length=30)
    correo: Optional[str] = Field(None, max_length=120)
    sitio_web: Optional[str] = None
    horarios: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class PoiCreate(PoiBase):
    pass


class PoiUpdate(BaseModel):
    categoria_id: Optional[int] = None
    ciudad_id: Optional[int] = None
    nombre: Optional[str] = Field(None, min_length=1, max_length=200)
    descripcion: Optional[str] = None
    direccion: Optional[str] = None
    ubicacion: Optional[Coordenadas] = None
    radio_validacion: Optional[int] = Field(None, gt=0)
    telefono: Optional[str] = Field(None, max_length=30)
    correo: Optional[str] = None
    sitio_web: Optional[str] = None
    horarios: Optional[dict] = None
    metadata: Optional[dict] = None


class PoiModeracion(BaseModel):
    estado: str
    motivo: Optional[str] = None


class PoiListItem(BaseModel):
    id: UUID
    nombre: str
    slug: str
    categoria: CategoriaPoiOut
    ciudad: CiudadOut
    ubicacion: Coordenadas
    calificacion_promedio: float
    total_calificaciones: int
    imagen_principal: Optional[str] = None
    distancia_metros: Optional[float] = None


class PoiDetail(BaseModel):
    id: UUID
    nombre: str
    slug: str
    descripcion: Optional[str] = None
    direccion: Optional[str] = None
    ubicacion: Coordenadas
    radio_validacion: int
    telefono: Optional[str] = None
    correo: Optional[str] = None
    sitio_web: Optional[str] = None
    horarios: dict
    metadata: dict
    categoria: CategoriaPoiOut
    ciudad: CiudadOut
    estado: str
    fuente: str
    nivel: Optional[int] = None
    calificacion_promedio: float
    total_calificaciones: int
    imagenes: List[ImagenPoiOut]
    created_at: datetime


class PaginatedPoiResponse(BaseModel):
    items: List[PoiListItem]
    total: int
    page: int
    page_size: int


class EnviarRevisionResponse(BaseModel):
    id: UUID
    estado: str


class PoiModeracionLogOut(BaseModel):
    id: int
    usuario_id: UUID
    estado_anterior: str
    estado_nuevo: str
    motivo: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
