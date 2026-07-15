from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.repositories.usuario_repository import UsuarioRepository
from app.services.usuario_service import UsuarioService
from app.schemas.usuario import UsuarioCreate, UsuarioResponse, UsuarioLogin, Token
from app.schemas.usuarios import UsuarioUpdate
from app.auth.dependencies import get_current_user
from app.models.usuario import Usuario

router = APIRouter()

def get_usuario_service(db: Session = Depends(get_db)) -> UsuarioService:
    repository = UsuarioRepository(db)
    return UsuarioService(repository)


@router.post("", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
def crear_usuario(
    usuario_data: UsuarioCreate,
    service: UsuarioService = Depends(get_usuario_service)
):
    """
    Crear un nuevo usuario

    - **nombre**: Nombre del usuario (1-50 caracteres)
    - **apellido**: Apellido del usuario (1-50 caracteres)
    - **email**: Email válido y único
    - **telefono**: Teléfono opcional (máx 20 caracteres)
    - **password**: Contraseña (mínimo 8 caracteres)
    """
    return service.create_user(usuario_data)


@router.get("", response_model=List[UsuarioResponse])
def listar_usuarios(
    skip: int = Query(0, ge=0, description="Número de registros a saltar"),
    limit: int = Query(100, ge=1, le=100, description="Límite de registros por página"),
    nombre: Optional[str] = Query(None, description="Filtrar por nombre"),
    apellido: Optional[str] = Query(None, description="Filtrar por apellido"),
    email: Optional[str] = Query(None, description="Filtrar por email"),
    estado: Optional[str] = Query(None, description="Filtrar por estado"),
    rol_id: Optional[int] = Query(None, description="Filtrar por rol"),
    include_deleted: bool = Query(False, description="Incluir usuarios eliminados"),
    service: UsuarioService = Depends(get_usuario_service)
):
    """
    Listar usuarios con paginación y filtros opcionales

    - **skip**: Número de registros a saltar (paginación)
    - **limit**: Límite de registros por página (máx 100)
    - **nombre**: Filtrar por nombre (búsqueda parcial)
    - **apellido**: Filtrar por apellido (búsqueda parcial)
    - **email**: Filtrar por email (búsqueda parcial)
    - **estado**: Filtrar por estado (ACTIVO, SUSPENDIDO, ELIMINADO)
    - **rol_id**: Filtrar por ID de rol
    - **include_deleted**: Incluir usuarios eliminados (soft delete)
    """
    filters = {}
    if nombre:
        filters['nombre'] = nombre
    if apellido:
        filters['apellido'] = apellido
    if email:
        filters['email'] = email
    if estado:
        filters['estado'] = estado
    if rol_id:
        filters['rol_id'] = rol_id
    if include_deleted:
        filters['include_deleted'] = True

    return service.list_users(skip=skip, limit=limit, **filters)


@router.get("/count", response_model=int)
def contar_usuarios(
    nombre: Optional[str] = Query(None),
    apellido: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    estado: Optional[str] = Query(None),
    rol_id: Optional[int] = Query(None),
    include_deleted: bool = Query(False),
    service: UsuarioService = Depends(get_usuario_service)
):
    """
    Contar total de usuarios con filtros opcionales
    """
    filters = {}
    if nombre:
        filters['nombre'] = nombre
    if apellido:
        filters['apellido'] = apellido
    if email:
        filters['email'] = email
    if estado:
        filters['estado'] = estado
    if rol_id:
        filters['rol_id'] = rol_id
    if include_deleted:
        filters['include_deleted'] = True

    return service.count_users(**filters)


@router.get("/{usuario_id}", response_model=UsuarioResponse)
def obtener_usuario(
    usuario_id: str,
    service: UsuarioService = Depends(get_usuario_service)
):
    """
    Obtener un usuario por su ID
    """
    return service.get_user(usuario_id)


@router.patch("/{usuario_id}", response_model=UsuarioResponse)
def actualizar_usuario(
    usuario_id: str,
    usuario_data: UsuarioUpdate,
    service: UsuarioService = Depends(get_usuario_service)
):
    """
    Actualizar un usuario existente (actualización parcial)

    Todos los campos son opcionales. Solo se actualizarán los campos proporcionados.
    """
    return service.update_user(usuario_id, usuario_data)


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_usuario(
    usuario_id: str,
    soft: bool = Query(True, description="Eliminación suave (true) o permanente (false)"),
    service: UsuarioService = Depends(get_usuario_service)
):
    """
    Eliminar un usuario

    - **soft=true** (por defecto): Marca el usuario como eliminado (soft delete)
    - **soft=false**: Elimina permanentemente el usuario de la base de datos
    """
    service.delete_user(usuario_id, soft=soft)
    return None


@router.post("/{usuario_id}/activar", response_model=UsuarioResponse)
def activar_usuario(
    usuario_id: str,
    service: UsuarioService = Depends(get_usuario_service)
):
    """
    Activar un usuario suspendido o eliminado
    """
    return service.activate_user(usuario_id)


@router.post("/{usuario_id}/suspender", response_model=UsuarioResponse)
def suspender_usuario(
    usuario_id: str,
    service: UsuarioService = Depends(get_usuario_service)
):
    """
    Suspender un usuario activo
    """
    return service.suspend_user(usuario_id)