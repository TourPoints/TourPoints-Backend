from fastapi import HTTPException, status

class CredentialsException(HTTPException):
    """Excepción personalizada para credenciales inválidas"""
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )