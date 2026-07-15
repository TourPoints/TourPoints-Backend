#️ Repositorio de usuarios con operaciones CRUD
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.repositories.base_repository import BaseRepository
from app.models.usuario import Usuario, Rol
from app.schemas.usuario import UsuarioCreate, UsuarioResponse


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

    def get_by_rol(self, rol_nombre: str) -> List[Usuario]:
        rol = self.db.query(Rol).filter(Rol.nombre == rol_nombre).first()
        if not rol:
            return []
        return self.db.query(Usuario).filter(Usuario.rol_id == rol.id).all()

    def list(self, skip: int = 0, limit: int = 100, **filters) -> List[Usuario]:
        query = self.db.query(Usuario)

        # Apply filters
        if filters.get('nombre'):
            query = query.filter(Usuario.nombre.ilike(f"%{filters['nombre']}%"))
        if filters.get('apellido'):
            query = query.filter(Usuario.apellido.ilike(f"%{filters['apellido']}%"))
        if filters.get('email'):
            query = query.filter(Usuario.email.ilike(f"%{filters['email']}%"))
        if filters.get('estado'):
            query = query.filter(Usuario.estado == filters['estado'])
        if filters.get('rol_id'):
            query = query.filter(Usuario.rol_id == filters['rol_id'])

        # Filter out soft deleted users by default
        if not filters.get('include_deleted', False):
            query = query.filter(Usuario.deleted_at.is_(None))

        return query.offset(skip).limit(limit).all()

    def create(self, data: UsuarioCreate) -> Usuario:
        hashed_password = data.password  # Password will be hashed by the service
        db_usuario = Usuario(
            nombre=data.nombre,
            apellido=data.apellido,
            email=data.email,
            password_hash=hashed_password,
            telefono=data.telefono,
            rol_id=2  # Default to 'usuario' role
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
        """Soft delete - marks user as deleted"""
        from datetime import datetime
        from sqlalchemy import text
        user = self._get_by_id(id)
        user.deleted_at = datetime.utcnow()
        user.estado = text("'ELIMINADO'")
        self.db.commit()

    def hard_delete(self, id: str) -> None:
        """Hard delete - permanently removes user from database"""
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

        if filters.get('nombre'):
            query = query.filter(Usuario.nombre.ilike(f"%{filters['nombre']}%"))
        if filters.get('apellido'):
            query = query.filter(Usuario.apellido.ilike(f"%{filters['apellido']}%"))
        if filters.get('email'):
            query = query.filter(Usuario.email.ilike(f"%{filters['email']}%"))
        if filters.get('estado'):
            query = query.filter(Usuario.estado == filters['estado'])
        if filters.get('rol_id'):
            query = query.filter(Usuario.rol_id == filters['rol_id'])
        if not filters.get('include_deleted', False):
            query = query.filter(Usuario.deleted_at.is_(None))

        return query.count()