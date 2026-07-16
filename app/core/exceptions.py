from fastapi import HTTPException, status


class CredentialsException(HTTPException):
    """Excepción personalizada para credenciales inválidas."""

    def __init__(self, detail: str = "Credenciales inválidas", status_code: int = status.HTTP_401_UNAUTHORIZED):
        super().__init__(
            status_code=status_code,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class InternalServiceError(HTTPException):
    """Error inesperado durante la ejecución de un servicio."""

    def __init__(
        self,
        detail: str = "Error interno del servicio",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ):
        super().__init__(status_code=status_code, detail=detail)


class ConflictError(HTTPException):
    """El recurso solicitado entra en conflicto con el estado actual."""

    def __init__(self, detail: str = "Conflicto con el estado actual"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class RecordNotFoundError(HTTPException):
    """Excepción para registros no encontrados."""

    def __init__(self, detail: str = "Registro no encontrado"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class DBError(HTTPException):
    """Excepción para errores de base de datos."""

    def __init__(self, detail: str = "Error de base de datos"):
        super().__init__(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)


class PuntosInsuficientesError(HTTPException):
    """El usuario no tiene saldo suficiente para canjear (409)."""

    def __init__(self, detail: str = "Puntos insuficientes para canjear esta recompensa"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class SinStockError(HTTPException):
    """La recompensa no tiene stock disponible (409)."""

    def __init__(self, detail: str = "La recompensa no tiene stock disponible"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)
