from fastapi import HTTPException, status


class CredentialsException(HTTPException):
    """Excepción personalizada para credenciales inválidas."""

    def __init__(self, detail: str = "Credenciales inválidas", status_code: int = status.HTTP_401_UNAUTHORIZED):
        super().__init__(
            status_code=status_code,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class KoreansavageError(HTTPException):
    """Excepción personalizada para errores de negocio."""

    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=status_code, detail=detail)


class RecordNotFoundError(HTTPException):
    """Excepción para registros no encontrados."""

    def __init__(self, detail: str = "Registro no encontrado"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class DBError(HTTPException):
    """Excepción para errores de base de datos."""

    def __init__(self, detail: str = "Error de base de datos"):
        super().__init__(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)