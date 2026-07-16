from app.core.exceptions import DBError
from app.repositories.catalogo_repository import CatalogoRepository
from app.schemas.catalogos import CiudadListItem, PaginatedCategoriasResponse, PaginatedCiudadesResponse
from app.schemas.poi import CategoriaPoiOut


class CatalogoService:
    def __init__(self, repository: CatalogoRepository):
        self.repository = repository

    def list_ciudades(self, skip: int, limit: int, page: int, **filters) -> PaginatedCiudadesResponse:
        try:
            rows = self.repository.list_ciudades(skip=skip, limit=limit, **filters)
            total = self.repository.count_ciudades(**filters)
            items = [
                CiudadListItem(
                    id=ciudad.id,
                    nombre=ciudad.nombre,
                    departamento_id=ciudad.departamento_id,
                    departamento=departamento,
                )
                for ciudad, departamento in rows
            ]
            return PaginatedCiudadesResponse(items=items, total=total, page=page, page_size=limit)
        except Exception as exc:
            raise DBError(f"List ciudades failed: {str(exc)}") from exc

    def list_categorias(self, skip: int, limit: int, page: int) -> PaginatedCategoriasResponse:
        try:
            categorias = self.repository.list_categorias(skip=skip, limit=limit)
            total = self.repository.count_categorias()
            items = [CategoriaPoiOut.model_validate(categoria) for categoria in categorias]
            return PaginatedCategoriasResponse(items=items, total=total, page=page, page_size=limit)
        except Exception as exc:
            raise DBError(f"List categorias failed: {str(exc)}") from exc
