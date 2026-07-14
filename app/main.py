from fastapi import APIRouter, FastAPI
from fastapi.openapi.docs import get_redoc_html

from app.routers import auth, poi, recompensas, usuarios, visitas

app = FastAPI(title="TourPoints API", redoc_url=None)

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth.router, prefix="/auth", tags=["auth"])
api_v1.include_router(usuarios.router, prefix="/usuarios", tags=["usuarios"])
api_v1.include_router(poi.router, prefix="/poi", tags=["poi"])
api_v1.include_router(visitas.router, prefix="/visitas", tags=["visitas"])
api_v1.include_router(recompensas.router, prefix="/recompensas", tags=["recompensas"])

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
