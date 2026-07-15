from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from app.config import settings

# Contexto de hash de contraseñas usando bcrypt (recomendado para almacenamiento seguro)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Genera un hash seguro de la contraseña usando bcrypt"""
    # bcrypt has a 72 byte limit
    if len(password.encode('utf-8')) > 72:
        password = password[:72]
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica que una contraseña en texto plano coincida con su hash"""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """
    Crea un token JWT firmado

    Args:
        data: Diccionario con los datos a incluir en el token (sub, exp, etc.)
        expires_delta: Tiempo de expiración opcional

    Returns:
        String JWT codificado
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt

def verify_token(token: str):
    """
    Verifica y decodifica un token JWT

    Args:
        token: Token JWT a verificar

    Returns:
        Diccionario con los datos del token si es válido

    Raises:
        JWTError: Si el token es inválido o expirado
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        raise