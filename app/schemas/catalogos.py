from typing import List

from pydantic import BaseModel

from app.schemas.poi import CategoriaPoiOut


class PaisOut(BaseModel):
    id: int
    nombre: str
    codigo_iso: str

    class Config:
        from_attributes = True


class PaginatedPaisesResponse(BaseModel):
    items: List[PaisOut]
    total: int
    page: int
    page_size: int


class DepartamentoListItem(BaseModel):
    id: int
    nombre: str
    pais_id: int
    pais: str


class PaginatedDepartamentosResponse(BaseModel):
    items: List[DepartamentoListItem]
    total: int
    page: int
    page_size: int


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
