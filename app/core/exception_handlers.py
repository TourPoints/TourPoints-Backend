#️ Manejadores de excepciones personalizados para la API
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from app.core.exceptions import InternalServiceError, RecordNotFoundError, DBError
import logging

class BaseExceptionHandler:
    def handle(self, request: Request, exc: Exception) -> JSONResponse:
        raise NotImplementedError

class InternalServiceErrorHandler(BaseExceptionHandler):
    def handle(self, request: Request, exc: InternalServiceError) -> JSONResponse:
        logging.exception("InternalServiceError: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Error interno del servicio"
            }
        )

class RecordNotFoundErrorHandler(BaseExceptionHandler):
    def handle(self, request: Request, exc: RecordNotFoundError) -> JSONResponse:
        logging.error(f"RecordNotFoundError: {exc}")
        return JSONResponse(
            status_code=404,
            content={
                "detail": exc.detail
            }
        )

class DBErrorHandler(BaseExceptionHandler):
    def handle(self, request: Request, exc: DBError) -> JSONResponse:
        # exc.detail suele incluir el texto crudo de la excepción de SQLAlchemy
        # (nombres de tabla/columna, fragmentos de la query) — se loguea acá
        # para diagnóstico, pero nunca se devuelve al cliente.
        logging.error(f"DBError: {exc.detail}")
        return JSONResponse(
            status_code=500,
            content={
                "details": "Database error occurred",
                "error": "Ocurrió un error interno al procesar la solicitud"
            }
        )

def register_exception_handlers(router: APIRouter):
    router.add_exception_handler(InternalServiceError, InternalServiceErrorHandler().handle)
    router.add_exception_handler(RecordNotFoundError, RecordNotFoundErrorHandler().handle)
    router.add_exception_handler(DBError, DBErrorHandler().handle)
