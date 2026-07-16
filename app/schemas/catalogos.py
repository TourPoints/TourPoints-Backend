from typing import List

from pydantic import BaseModel

from app.schemas.poi import CategoriaPoiOut


class CiudadListItem(BaseModel):
    id: int
    nombre: str
    departamento_id: int
    departamento: str


class PaginatedCiudadesResponse(BaseModel):
    items: List[CiudadListItem]
    total: int
    page: int
    page_size: int


class PaginatedCategoriasResponse(BaseModel):
    items: List[CategoriaPoiOut]
    total: int
    page: int
    page_size: int
