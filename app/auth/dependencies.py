from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.auth.security import verify_token, JWTError
from app.database import get_db
from app.models.usuario import Usuario
from app.core.exceptions import CredentialsException

# Esquema de seguridad Bearer Token
security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Dependencia que extrae y valida el usuario actual desde el token JWT

    Flujo:
    1. Extrae el token del header Authorization: Bearer <token>
    2. Verifica la firma y expiración del token
    3. Obtiene el subject (user_id) del token
    4. Busca el usuario en la base de datos
    5. Retorna el objeto Usuario si todo es válido

    Raises:
        HTTPException 401: Si el token es inválido, expirado o el usuario no existe
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Verificar token y obtener payload
        payload = verify_token(credentials.credentials)
        user_id: str = payload.get("sub")

        if user_id is None:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    # Buscar usuario en base de datos
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if user is None:
        raise credentials_exception

    return user

def get_current_active_user(current_user: Usuario = Depends(get_current_user)):
    """
    Dependencia que verifica que el usuario esté activo
    Puede extenderse para verificar otros estados (bloqueado, verificado, etc.)
    """
    # Aquí podrías agregar verificaciones adicionales como:
    # if not current_user.is_active:
    #     raise HTTPException(status_code=400, detail="Usuario inactivo")
    return current_user