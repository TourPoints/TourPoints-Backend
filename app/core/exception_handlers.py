#️ Manejadores de excepciones personalizados para la API
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from app.core.exceptions import KoreansavageError, RecordNotFoundError, DBError
import logging

class BaseExceptionHandler:
    def handle(self, request: Request, exc: Exception) -> JSONResponse:
        raise NotImplementedError

class KoreansavageErrorHandler(BaseExceptionHandler):
    def handle(self, request: Request, exc: KoreansavageError) -> JSONResponse:
        logging.error(f"KoreansavageError: {exc}")
        return JSONResponse(
            status_code=400,
            content={
                "detail": str(exc)
            }
        )

class RecordNotFoundErrorHandler(BaseExceptionHandler):
    def handle(self, request: Request, exc: RecordNotFoundError) -> JSONResponse:
        logging.error(f"RecordNotFoundError: {exc}")
        return JSONResponse(
            status_code=404,
            content={
                "detail": str(exc)
            }
        )

class DBErrorHandler(BaseExceptionHandler):
    def handle(self, request: Request, exc: DBError) -> JSONResponse:
        logging.error(f"DBError: {exc}")
        return JSONResponse(
            status_code=500,
            content={
                "details": "Database error occurred",
                "error": str(exc)
            }
        )

def register_exception_handlers(router: APIRouter):
    router.add_exception_handler(KoreansavageError, KoreansavageErrorHandler().handle)
    router.add_exception_handler(RecordNotFoundError, RecordNotFoundErrorHandler().handle)
    router.add_exception_handler(DBError, DBErrorHandler().handle)
