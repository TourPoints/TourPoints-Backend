from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html

from app.core.exception_handlers import register_exception_handlers
from app.core.middleware import JWTMiddleware
from app.routers import auth, catalogos, poi, recompensas, social, usuarios, visitas
from os import getenv

try:
    from app.scripts.seed_roles import seed_roles
except Exception:
    seed_roles = None

app = FastAPI(title="TourPoints API", redoc_url=None)

app.add_middleware(JWTMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth.router, prefix="/auth", tags=["auth"])
api_v1.include_router(catalogos.router)
api_v1.include_router(poi.router, prefix="/poi", tags=["poi"])
api_v1.include_router(social.router)
api_v1.include_router(usuarios.router, prefix="/users", tags=["users"])
api_v1.include_router(visitas.router, prefix="/visits", tags=["visits"])
api_v1.include_router(recompensas.router, prefix="/rewards", tags=["rewards"])

app.include_router(api_v1)


@app.get("/redoc", include_in_schema=False)
def redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2.5.3/bundles/redoc.standalone.js",
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.on_event("startup")
def maybe_seed_roles_on_startup():
    """Siembra los roles base si SEED_ROLES=true (útil en entornos nuevos sin la tabla poblada)."""
    if getenv("SEED_ROLES", "false").lower() in ("1", "true", "yes"):
        if callable(seed_roles):
            try:
                seed_roles()
            except Exception:
                pass
