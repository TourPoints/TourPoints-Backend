from typing import List

from app.auth.security import hash_password
from app.core.exceptions import DBError, KoreansavageError, RecordNotFoundError
from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.usuario import UsuarioCreate, UsuarioResponse
from app.schemas.usuarios import UsuarioUpdate


class UsuarioService:
    def __init__(self, repository: UsuarioRepository):
        self.repository = repository

    def create_user(self, data: UsuarioCreate) -> UsuarioResponse:
        try:
            if self.repository.search_by_email(data.email):
                raise KoreansavageError(f"Email {data.email} already exists")

            user_data = data.model_dump(exclude={"password"})
            user_data["password_hash"] = hash_password(data.password)

            user = self.repository.create(user_data)
            return UsuarioResponse.model_validate(user)
        except KoreansavageError:
            raise
        except Exception as exc:
            raise DBError(f"User creation failed: {str(exc)}") from exc

    def get_user(self, user_id: str) -> UsuarioResponse:
        try:
            user = self.repository.get_by_id(user_id)
            if not user:
                raise RecordNotFoundError(f"User with id {user_id} not found")
            return UsuarioResponse.model_validate(user)
        except RecordNotFoundError:
            raise
        except Exception as exc:
            raise DBError(f"Get user failed: {str(exc)}") from exc

    def update_user(self, user_id: str, data: UsuarioUpdate) -> UsuarioResponse:
        try:
            user = self.repository.get_by_id(user_id)
            if not user:
                raise RecordNotFoundError(f"User with id {user_id} not found")

            update_data = data.model_dump(exclude_unset=True)
            if "email" in update_data and self.repository.search_by_email(update_data["email"]):
                raise KoreansavageError(f"Email {update_data['email']} already exists")

            if "password" in update_data:
                update_data["password_hash"] = hash_password(update_data["password"])
                del update_data["password"]

            updated_user = self.repository.update(user_id, update_data)
            return UsuarioResponse.model_validate(updated_user)
        except KoreansavageError:
            raise
        except RecordNotFoundError:
            raise
        except Exception as exc:
            raise DBError(f"User update failed: {str(exc)}") from exc

    def delete_user(self, user_id: str, soft: bool = True) -> None:
        try:
            user = self.repository.get_by_id(user_id)
            if not user:
                raise RecordNotFoundError(f"User with id {user_id} not found")

            if soft:
                self.repository.delete(user_id)
            else:
                self.repository.hard_delete(user_id)
        except RecordNotFoundError:
            raise
        except Exception as exc:
            raise DBError(f"User delete failed: {str(exc)}") from exc

    def list_users(self, skip: int = 0, limit: int = 100, **filters) -> List[UsuarioResponse]:
        try:
            users = self.repository.list(skip=skip, limit=limit, **filters)
            return [UsuarioResponse.model_validate(u) for u in users]
        except Exception as exc:
            raise DBError(f"List users failed: {str(exc)}") from exc

    def count_users(self, **filters) -> int:
        try:
            return self.repository.count(**filters)
        except Exception as exc:
            raise DBError(f"Count users failed: {str(exc)}") from exc

    def activate_user(self, user_id: str) -> UsuarioResponse:
        try:
            if not self.repository.get_by_id(user_id):
                raise RecordNotFoundError(f"User with id {user_id} not found")
            user = self.repository.activate(user_id)
            return UsuarioResponse.model_validate(user)
        except RecordNotFoundError:
            raise
        except Exception as exc:
            raise DBError(f"Activate user failed: {str(exc)}") from exc

    def suspend_user(self, user_id: str) -> UsuarioResponse:
        try:
            if not self.repository.get_by_id(user_id):
                raise RecordNotFoundError(f"User with id {user_id} not found")
            user = self.repository.suspend(user_id)
            return UsuarioResponse.model_validate(user)
        except RecordNotFoundError:
            raise
        except Exception as exc:
            raise DBError(f"Suspend user failed: {str(exc)}") from exc