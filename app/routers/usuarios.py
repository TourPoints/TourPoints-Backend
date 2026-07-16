from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_admin_user, get_current_user
from app.auth.security import hash_password, verify_password
from app.database import get_db
from app.models.usuario import Usuario
from app.repositories.usuario_repository import UsuarioRepository
from app.schemas.usuario import UsuarioCreate, UsuarioResponse
from app.schemas.usuarios import ChangePasswordRequest, UsuarioUpdate
from app.services.usuario_service import UsuarioService

router = APIRouter(tags=["users"])


def get_user_service(db: Session = Depends(get_db)) -> UsuarioService:
    repository = UsuarioRepository(db)
    return UsuarioService(repository)


@router.post("", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user_data: UsuarioCreate,
    service: UsuarioService = Depends(get_user_service),
    admin_user: Usuario = Depends(get_admin_user),
):
    """Crea un nuevo usuario (solo administradores)."""
    return service.create_user(user_data)


@router.get("", response_model=List[UsuarioResponse])
def list_users(
    skip: int = Query(0, ge=0, description="Número de registros a saltar"),
    limit: int = Query(100, ge=1, le=100, description="Límite de registros por página"),
    name: Optional[str] = Query(None, description="Filtrar por nombre"),
    surname: Optional[str] = Query(None, description="Filtrar por apellido"),
    email: Optional[str] = Query(None, description="Filtrar por email"),
    estado: Optional[str] = Query(None, description="Filtrar por estado"),
    rol_id: Optional[int] = Query(None, description="Filtrar por rol"),
    include_deleted: bool = Query(False, description="Incluir usuarios eliminados"),
    service: UsuarioService = Depends(get_user_service),
    admin_user: Usuario = Depends(get_admin_user),
):
    """Lista usuarios con paginación y filtros opcionales."""
    filters = {}
    if name:
        filters["nombre"] = name
    if surname:
        filters["apellido"] = surname
    if email:
        filters["email"] = email
    if estado:
        filters["estado"] = estado
    if rol_id:
        filters["rol_id"] = rol_id
    if include_deleted:
        filters["include_deleted"] = True

    return service.list_users(skip=skip, limit=limit, **filters)


@router.get("/count", response_model=int)
def count_users(
    name: Optional[str] = Query(None),
    surname: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    estado: Optional[str] = Query(None),
    rol_id: Optional[int] = Query(None),
    include_deleted: bool = Query(False),
    service: UsuarioService = Depends(get_user_service),
    admin_user: Usuario = Depends(get_admin_user),
):
    """Cuenta los usuarios con filtros opcionales."""
    filters = {}
    if name:
        filters["nombre"] = name
    if surname:
        filters["apellido"] = surname
    if email:
        filters["email"] = email
    if estado:
        filters["estado"] = estado
    if rol_id:
        filters["rol_id"] = rol_id
    if include_deleted:
        filters["include_deleted"] = True

    return service.count_users(**filters)


@router.get("/me", response_model=UsuarioResponse)
def get_current_user_profile(current_user: Usuario = Depends(get_current_user)):
    """Devuelve el perfil del usuario autenticado."""
    return current_user


@router.patch("/me", response_model=UsuarioResponse)
def update_current_user_profile(
    user_data: UsuarioUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Actualiza el perfil del usuario autenticado."""
    update_data = user_data.model_dump(exclude_unset=True)
    if "email" in update_data:
        existing_user = db.query(Usuario).filter(Usuario.email == update_data["email"]).first()
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El email ya está registrado")

    if "password" in update_data:
        update_data["password_hash"] = hash_password(update_data["password"])
        del update_data["password"]

    for field, value in update_data.items():
        if hasattr(current_user, field):
            setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)
    return current_user


@router.patch("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_current_user_password(
    password_data: ChangePasswordRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cambia la contraseña del usuario autenticado."""
    if not verify_password(password_data.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña actual es incorrecta")

    current_user.password_hash = hash_password(password_data.new_password)
    db.commit()
    return None


@router.post("/{user_id}/activate", response_model=UsuarioResponse)
def activate_user(
    user_id: str,
    service: UsuarioService = Depends(get_user_service),
    admin_user: Usuario = Depends(get_admin_user),
):
    """Activa un usuario suspendido o eliminado."""
    return service.activate_user(user_id)


@router.post("/{user_id}/suspend", response_model=UsuarioResponse)
def suspend_user(
    user_id: str,
    service: UsuarioService = Depends(get_user_service),
    admin_user: Usuario = Depends(get_admin_user),
):
    """Suspende un usuario activo."""
    return service.suspend_user(user_id)


@router.get("/{user_id}", response_model=UsuarioResponse)
def get_user(
    user_id: str,
    service: UsuarioService = Depends(get_user_service),
    admin_user: Usuario = Depends(get_admin_user),
):
    """Obtiene un usuario por su ID."""
    return service.get_user(user_id)


@router.patch("/{user_id}", response_model=UsuarioResponse)
def update_user(
    user_id: str,
    user_data: UsuarioUpdate,
    service: UsuarioService = Depends(get_user_service),
    admin_user: Usuario = Depends(get_admin_user),
):
    """Actualiza un usuario existente (actualización parcial)."""
    return service.update_user(user_id, user_data)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    soft: bool = Query(True, description="Eliminación suave (true) o permanente (false)"),
    service: UsuarioService = Depends(get_user_service),
    admin_user: Usuario = Depends(get_admin_user),
):
    """Elimina un usuario (soft delete por defecto)."""
    service.delete_user(user_id, soft=soft)
    return None