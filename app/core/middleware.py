#️ Middleware JWT para autenticación
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import logging

logger = logging.getLogger(__name__)

class JWTMiddleware(BaseHTTPMiddleware):
    """
    Middleware para manejar JWT tokens
    Este middleware es opcional y puede usarse para logging, rate limiting, etc.
    """
    async def dispatch(self, request: Request, call_next):
        # Log request
        logger.info(f"Request: {request.method} {request.url.path}")

        response = await call_next(request)
        return response