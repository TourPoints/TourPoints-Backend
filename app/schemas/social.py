from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class UsuarioMini(BaseModel):
    id: UUID
    nombre: str

    class Config:
        from_attributes = True


class CalificacionCreate(BaseModel):
    calificacion: int = Field(..., ge=1, le=5)


class CalificacionOut(BaseModel):
    id: int
    poi_id: UUID
    usuario_id: UUID
    calificacion: int
    created_at: datetime

    class Config:
        from_attributes = True


class CalificacionListItem(BaseModel):
    id: int
    usuario: UsuarioMini
    calificacion: int
    created_at: datetime


class PaginatedCalificacionesResponse(BaseModel):
    items: List[CalificacionListItem]
    total: int
    page: int
    page_size: int


class CalificacionResumen(BaseModel):
    promedio: float
    total: int
    distribucion: Dict[str, int]


class ComentarioCreate(BaseModel):
    contenido: str = Field(..., min_length=1)


class ComentarioModeracion(BaseModel):
    estado: str


class ComentarioOut(BaseModel):
    id: int
    poi_id: UUID
    usuario: UsuarioMini
    contenido: str
    estado: str
    created_at: datetime


class PaginatedComentariosResponse(BaseModel):
    items: List[ComentarioOut]
    total: int
    page: int
    page_size: int


class FavoritoCreate(BaseModel):
    poi_id: UUID


class FavoritoOut(BaseModel):
    usuario_id: UUID
    poi_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True
