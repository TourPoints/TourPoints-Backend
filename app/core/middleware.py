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


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Headers de respuesta estándar de hardening. No afectan el request/response
    de la API en sí (paths, body, status codes) — son metadata adicional que los
    clientes normales (frontend, apps) ignoran; solo endurecen el comportamiento
    de navegadores ante escenarios de abuso (clickjacking, MIME sniffing, etc.)."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers.setdefault("Permissions-Policy", "geolocation=(), camera=(), microphone=()")
        return response