from fastapi import APIRouter, FastAPI
from fastapi.openapi.docs import get_redoc_html
from fastapi.middleware.cors import CORSMiddleware
from app.core.exceptions import KoreansavageError, RecordNotFoundError, DBError
from app.core.middleware import JWTMiddleware
from app.core.exception_handlers import register_exception_handlers

# Import routers
from app.routers import auth, poi, usuarios, recompensas, visitas

app = FastAPI(title="TourPoints API", redoc_url=None)

# Middlewares
app.add_middleware(
    JWTMiddleware,
    # JWT config will be added here if needed
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register exception handlers
register_exception_handlers(app)

# API Routers
api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth.router, prefix="/auth", tags=["auth"])
api_v1.include_router(poi.router, prefix="/poi", tags=["poi"])
api_v1.include_router(usuarios.router, prefix="/usuarios", tags=["usuarios"])
api_v1.include_router(visitas.router, prefix="/visitas", tags=["visitas"])
api_v1.include_router(recompensas.router, prefix="/recompensas", tags=["recompensas"])

app.include_router(api_v1)

# Redoc endpoint
@app.get("/redoc", include_in_schema=False)
def redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2.5.3/bundles/redoc.standalone.js",
    )

# Health check
@app.get("/health")
def health_check():
    return {"status": "ok"}