from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.catalogo_repository import CatalogoRepository
from app.schemas.catalogos import PaginatedCategoriasResponse, PaginatedCiudadesResponse
from app.services.catalogo_service import CatalogoService

router = APIRouter(tags=["catalogos"])


def get_catalogo_service(db: Session = Depends(get_db)) -> CatalogoService:
    return CatalogoService(CatalogoRepository(db))


@router.get("/ciudades", response_model=PaginatedCiudadesResponse)
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


@router.get("/categorias-poi", response_model=PaginatedCategoriasResponse)
def list_categorias_poi(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: CatalogoService = Depends(get_catalogo_service),
):
    """Catálogo de categorías de POI. Público, de solo lectura."""
    skip = (page - 1) * page_size
    return service.list_categorias(skip=skip, limit=page_size, page=page)
