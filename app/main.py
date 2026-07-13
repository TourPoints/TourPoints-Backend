from fastapi import APIRouter, FastAPI

from app.routers import auth, poi, recompensas, usuarios, visitas

app = FastAPI(title="TourPoints API")

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth.router, prefix="/auth", tags=["auth"])
api_v1.include_router(usuarios.router, prefix="/usuarios", tags=["usuarios"])
api_v1.include_router(poi.router, prefix="/poi", tags=["poi"])
api_v1.include_router(visitas.router, prefix="/visitas", tags=["visitas"])
api_v1.include_router(recompensas.router, prefix="/recompensas", tags=["recompensas"])

app.include_router(api_v1)


@app.get("/health")
def health_check():
    return {"status": "ok"}
