from typing import List

from sqlalchemy.orm import Session

from app.models.poi import CategoriaPoi
from app.models.ubicacion import Ciudad, Departamento


class CatalogoRepository:
    def __init__(self, db: Session):
        self.db = db

    def _filtered_ciudades_query(self, **filters):
        query = self.db.query(Ciudad, Departamento.nombre.label("departamento")).join(
            Departamento, Departamento.id == Ciudad.departamento_id
        )
        if filters.get("departamento_id"):
            query = query.filter(Ciudad.departamento_id == filters["departamento_id"])
        if filters.get("pais_id"):
            query = query.filter(Departamento.pais_id == filters["pais_id"])
        if filters.get("q"):
            query = query.filter(Ciudad.nombre.ilike(f"%{filters['q']}%"))
        return query

    def list_ciudades(self, skip: int = 0, limit: int = 20, **filters):
        return self._filtered_ciudades_query(**filters).order_by(Ciudad.nombre).offset(skip).limit(limit).all()

    def count_ciudades(self, **filters) -> int:
        return self._filtered_ciudades_query(**filters).count()

    def list_categorias(self, skip: int = 0, limit: int = 20) -> List[CategoriaPoi]:
        return self.db.query(CategoriaPoi).order_by(CategoriaPoi.nombre).offset(skip).limit(limit).all()

    def count_categorias(self) -> int:
        return self.db.query(CategoriaPoi).count()
