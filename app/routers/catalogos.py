from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.catalogo_repository import CatalogoRepository
from app.schemas.catalogos import (
    PaginatedCategoriasResponse,
    PaginatedCiudadesResponse,
    PaginatedDepartamentosResponse,
    PaginatedPaisesResponse,
)
from app.services.catalogo_service import CatalogoService

router = APIRouter(tags=["catalogs"])


def get_catalogo_service(db: Session = Depends(get_db)) -> CatalogoService:
    return CatalogoService(CatalogoRepository(db))


@router.get("/countries", response_model=PaginatedPaisesResponse)
def list_paises(
    q: Optional[str] = Query(None, description="Búsqueda por nombre de país"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: CatalogoService = Depends(get_catalogo_service),
):
    """Catálogo de países. Público, de solo lectura."""
    filters = {"q": q} if q else {}
    skip = (page - 1) * page_size
    return service.list_paises(skip=skip, limit=page_size, page=page, **filters)


@router.get("/departments", response_model=PaginatedDepartamentosResponse)
def list_departamentos(
    pais_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None, description="Búsqueda por nombre de departamento"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: CatalogoService = Depends(get_catalogo_service),
):
    """Catálogo de departamentos. Público, de solo lectura. Filtra por `pais_id` para el combo país→departamento→ciudad."""
    filters = {"pais_id": pais_id, "q": q}
    filters = {k: v for k, v in filters.items() if v is not None}
    skip = (page - 1) * page_size
    return service.list_departamentos(skip=skip, limit=page_size, page=page, **filters)


@router.get("/cities", response_model=PaginatedCiudadesResponse)
def list_ciudades(
    departamento_id: Optional[int] = Query(None),
    pais_id: Optional[int] = Query(None),
    q: Optional[str] = Query(None, description="Búsqueda por nombre de ciudad"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: CatalogoService = Depends(get_catalogo_service),
):
    """Catálogo de ciudades. Público, de solo lectura."""
    filters = {"departamento_id": departamento_id, "pais_id": pais_id, "q": q}
    filters = {k: v for k, v in filters.items() if v is not None}
    skip = (page - 1) * page_size
    return service.list_ciudades(skip=skip, limit=page_size, page=page, **filters)


@router.get("/poi-categories", response_model=PaginatedCategoriasResponse)
def list_categorias_poi(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: CatalogoService = Depends(get_catalogo_service),
):
    """Catálogo de categorías de POI. Público, de solo lectura."""
    skip = (page - 1) * page_size
    return service.list_categorias(skip=skip, limit=page_size, page=page)
