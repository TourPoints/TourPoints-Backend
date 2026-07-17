from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from typing import Tuple

from app.auth.security import JWTError, verify_token
from app.core.exceptions import CredentialsException
from app.database import get_db
from app.models.usuario import Rol, Usuario

security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """Extrae y valida el usuario actual desde el token JWT."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = verify_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if user is None:
        raise credentials_exception

    if user.deleted_at is not None or user.estado != "ACTIVO":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario no activo")

    return user


def get_role_nombre(user: Usuario, db: Session) -> str:
    """Nombre del rol (en minúsculas) de un usuario ya autenticado."""
    role = db.query(Rol).filter(Rol.id == user.rol_id).first()
    return (role.nombre or "").lower() if role else ""


def is_admin_user(user: Optional[Usuario], db: Session) -> bool:
    """True si `user` existe y tiene rol admin. No lanza excepción (para chequeos opcionales)."""
    if user is None:
        return False
    return get_role_nombre(user, db) == "admin"


def get_admin_user(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Permite el acceso solo a usuarios con rol administrador."""
    if not is_admin_user(current_user, db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Se requieren permisos de administrador")
    return current_user


def get_admin_or_establecimiento_user(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Permite ADMIN o rol establecimiento (ej. staff validando un QR en el
    punto de canje). No valida pertenencia a un establecimiento específico
    (establecimiento_usuarios) — el módulo Comercial aún no expone esa
    relación vía endpoint; cuando exista, este chequeo debería restringirse
    al establecimiento dueño de la recompensa/POI involucrado."""
    rol = get_role_nombre(current_user, db)
    if rol not in ("admin", "establecimiento"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Se requieren permisos de administrador o establecimiento")
    return current_user


def get_current_user_con_flag_admin(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Tuple[Usuario, bool]:
    """Deja pasar a cualquier usuario autenticado (admin o no) y devuelve el
    usuario junto con un flag indicando si es admin. A diferencia de
    get_admin_user, NUNCA levanta 403 por rol — el acceso lo decide el router
    con el flag (p. ej. solo_admin para filtrar estados no publicadas). Patron
    "todos entran, el admin ve mas", reusable en Retos etc."""
    role = db.query(Rol).filter(Rol.id == current_user.rol_id).first()
    es_admin = role is not None and (role.nombre or "").lower() == "admin"
    return (current_user, es_admin)
  
def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security),
    db: Session = Depends(get_db),
) -> Optional[Usuario]:
    """Devuelve el usuario autenticado si hay un token válido, o None en rutas públicas sin token."""
    if credentials is None:
        return None
    try:
        payload = verify_token(credentials.credentials)
    except JWTError:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if user is None or user.deleted_at is not None or user.estado != "ACTIVO":
        return None
    return user
