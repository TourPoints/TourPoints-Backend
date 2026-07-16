from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.usuario import Usuario
from app.repositories.base_repository import BaseRepository


class UsuarioRepository(BaseRepository[Usuario]):
    def __init__(self, db: Session):
        self.db = db
        super().__init__(Usuario)

    def _get_by_id(self, id: str) -> Usuario:
        user = self.db.query(Usuario).filter(Usuario.id == id).first()
        if not user:
            from sqlalchemy.exc import NoResultFound

            raise NoResultFound(f"Usuario with id {id} not found")
        return user

    def get_by_id(self, id: str) -> Optional[Usuario]:
        return self.db.query(Usuario).filter(Usuario.id == id).first()

    def search_by_email(self, email: str) -> Optional[Usuario]:
        return self.db.query(Usuario).filter(Usuario.email == email).first()

    def list(self, skip: int = 0, limit: int = 100, **filters) -> List[Usuario]:
        query = self.db.query(Usuario)

        if filters.get("nombre"):
            query = query.filter(Usuario.nombre.ilike(f"%{filters['nombre']}%"))
        if filters.get("apellido"):
            query = query.filter(Usuario.apellido.ilike(f"%{filters['apellido']}%"))
        if filters.get("email"):
            query = query.filter(Usuario.email.ilike(f"%{filters['email']}%"))
        if filters.get("estado"):
            query = query.filter(Usuario.estado == filters["estado"])
        if filters.get("rol_id"):
            query = query.filter(Usuario.rol_id == filters["rol_id"])

        if not filters.get("include_deleted", False):
            query = query.filter(Usuario.deleted_at.is_(None))

        return query.offset(skip).limit(limit).all()

    def create(self, data: dict) -> Usuario:
        password_hash = data.get("password_hash") or data.get("password")
        db_usuario = Usuario(
            nombre=data.get("nombre"),
            apellido=data.get("apellido"),
            email=data.get("email"),
            password_hash=password_hash,
            telefono=data.get("telefono"),
            rol_id=data.get("rol_id", 2),
            estado=data.get("estado", "ACTIVO"),
        )
        self.db.add(db_usuario)
        self.db.commit()
        self.db.refresh(db_usuario)
        return db_usuario

    def update(self, id: str, data: dict) -> Usuario:
        user = self._get_by_id(id)
        for field, value in data.items():
            if hasattr(user, field):
                setattr(user, field, value)
        self.db.commit()
        self.db.refresh(user)
        return user

    def delete(self, id: str) -> None:
        """Soft delete: marca el usuario como eliminado sin borrar el registro."""
        user = self._get_by_id(id)
        user.deleted_at = datetime.utcnow()
        user.estado = "ELIMINADO"
        self.db.commit()

    def hard_delete(self, id: str) -> None:
        """Elimina el registro de forma permanente."""
        user = self._get_by_id(id)
        self.db.delete(user)
        self.db.commit()

    def activate(self, id: str) -> Usuario:
        user = self._get_by_id(id)
        user.estado = "ACTIVO"
        user.deleted_at = None
        self.db.commit()
        self.db.refresh(user)
        return user

    def suspend(self, id: str) -> Usuario:
        user = self._get_by_id(id)
        user.estado = "SUSPENDIDO"
        self.db.commit()
        self.db.refresh(user)
        return user

    def count(self, **filters) -> int:
        query = self.db.query(Usuario)

        if filters.get("nombre"):
            query = query.filter(Usuario.nombre.ilike(f"%{filters['nombre']}%"))
        if filters.get("apellido"):
            query = query.filter(Usuario.apellido.ilike(f"%{filters['apellido']}%"))
        if filters.get("email"):
            query = query.filter(Usuario.email.ilike(f"%{filters['email']}%"))
        if filters.get("estado"):
            query = query.filter(Usuario.estado == filters["estado"])
        if filters.get("rol_id"):
            query = query.filter(Usuario.rol_id == filters["rol_id"])
        if not filters.get("include_deleted", False):
            query = query.filter(Usuario.deleted_at.is_(None))

        return query.count()