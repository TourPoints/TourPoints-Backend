#️ Servicio de usuarios manejando lógica de negocio
from typing import Optional, List
from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.usuario import UsuarioCreate, UsuarioResponse
from app.schemas.usuarios import UsuarioUpdate
from app.core.exceptions import RecordNotFoundError, KoreansavageError, DBError
from datetime import datetime
import bcrypt


class UsuarioService:
    def __init__(self, repository: UsuarioRepository):
        self.repository = repository

    def create_user(self, data: UsuarioCreate) -> UsuarioResponse:
        try:
            # Check for existing email
            if self.repository.search_by_email(data.email):
                raise KoreansavageError(f"Email {data.email} already exists")

            # Hash password
            hashed_password = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()

            # Create user with hashed password
            user_data = data.model_dump()
            user_data['password'] = hashed_password

            user = self.repository.create(user_data)
            return UsuarioResponse.model_validate(user)
        except Exception as e:
            raise DBError(f"User creation failed: {str(e)}") from e

    def get_user(self, user_id: str) -> UsuarioResponse:
        try:
            user = self.repository.get_by_id(user_id)
            if not user:
                raise RecordNotFoundError(f"User with id {user_id} not found")
            return UsuarioResponse.model_validate(user)
        except Exception as e:
            raise DBError(f"Get user failed: {str(e)}") from e

    def update_user(self, user_id: str, data: UsuarioUpdate) -> UsuarioResponse:
        try:
            user = self.repository.get_by_id(user_id)
            if not user:
                raise RecordNotFoundError(f"User with id {user_id} not found")

            update_data = data.model_dump(exclude_unset=True)

            # Hash password if provided
            if 'password' in update_data:
                update_data['password_hash'] = bcrypt.hashpw(
                    update_data['password'].encode(),
                    bcrypt.gensalt()
                ).decode()
                del update_data['password']

            # Update user
            updated_user = self.repository.update(user_id, update_data)
            return UsuarioResponse.model_validate(updated_user)
        except Exception as e:
            raise DBError(f"User update failed: {str(e)}") from e

    def delete_user(self, user_id: str, soft: bool = True) -> None:
        try:
            user = self.repository.get_by_id(user_id)
            if not user:
                raise RecordNotFoundError(f"User with id {user_id} not found")

            if soft:
                self.repository.delete(user_id)
            else:
                self.repository.hard_delete(user_id)
        except Exception as e:
            raise DBError(f"User delete failed: {str(e)}") from e

    def list_users(self, skip: int = 0, limit: int = 100, **filters) -> List[UsuarioResponse]:
        try:
            users = self.repository.list(skip=skip, limit=limit, **filters)
            return [UsuarioResponse.model_validate(u) for u in users]
        except Exception as e:
            raise DBError(f"List users failed: {str(e)}") from e

    def count_users(self, **filters) -> int:
        try:
            return self.repository.count(**filters)
        except Exception as e:
            raise DBError(f"Count users failed: {str(e)}") from e

    def login_user(self, email: str, password: str) -> dict:
        try:
            user = self.repository.search_by_email(email)
            if not user or not bcrypt.checkpw(password.encode(), user.password_hash.encode()):
                raise KoreansavageError("Invalid credentials")

            if user.estado != 'ACTIVO':
                raise KoreansavageError("User account is suspended")

            # Generate access token - this will be done by the auth service
            from app.auth.security import create_access_token
            access_token = create_access_token(data={"sub": str(user.id)})

            return {
                'access_token': access_token,
                'token_type': 'bearer',
                'expires_in': 3600,
                'usuario': UsuarioResponse.model_validate(user).model_dump()
            }
        except Exception as e:
            raise DBError(f"Login failed: {str(e)}") from e

    def activate_user(self, user_id: str) -> UsuarioResponse:
        try:
            user = self.repository.activate(user_id)
            return UsuarioResponse.model_validate(user)
        except Exception as e:
            raise DBError(f"Activate user failed: {str(e)}") from e

    def suspend_user(self, user_id: str) -> UsuarioResponse:
        try:
            user = self.repository.suspend(user_id)
            return UsuarioResponse.model_validate(user)
        except Exception as e:
            raise DBError(f"Suspend user failed: {str(e)}") from e