from datetime import datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.core.exceptions import CredentialsException

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Genera un hash seguro de la contraseña usando bcrypt."""
    if len(password.encode("utf-8")) > 72:
        password = password[:72]  # bcrypt ignora bytes por encima de 72
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica que una contraseña en texto plano coincida con su hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """Crea un token JWT firmado con claims básicos de identidad."""
    to_encode = data.copy()
    issued_at = datetime.utcnow()
    expires_at = issued_at + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))

    to_encode.update({"iat": int(issued_at.timestamp()), "exp": expires_at})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def verify_token(token: str):
    """Verifica y decodifica un token JWT."""
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:
        raise exc


def authenticate_user(user, password: str) -> None:
    """Valida credenciales y reglas de estado del usuario."""
    if not user:
        raise CredentialsException("Credenciales inválidas")

    if getattr(user, "deleted_at", None) is not None:
        raise CredentialsException("La cuenta está inactiva")

    if getattr(user, "estado", None) != "ACTIVO":
        raise CredentialsException("La cuenta está suspendida o eliminada")

    if not verify_password(password, getattr(user, "password_hash", "")):
        raise CredentialsException("Credenciales inválidas")