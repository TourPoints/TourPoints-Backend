from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from typing import Tuple

from app.auth.security import JWTError, verify_token
from app.core.exceptions import CredentialsException
from app.database import get_db
from app.models.usuario import Rol, Usuario

security = HTTPBearer()


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


def get_admin_user(
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Permite el acceso solo a usuarios con rol administrador."""
    role = db.query(Rol).filter(Rol.id == current_user.rol_id).first()
    if role is None or (role.nombre or "").lower() != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Se requieren permisos de administrador")
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