from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.visita import SaldoPuntosOut, VisitaCreate, VisitaOut
from app.services.visitas_service import VisitasService

router = APIRouter()


def get_visitas_service(db: Session = Depends(get_db)) -> VisitasService:
    return VisitasService(db)


@router.post("", response_model=VisitaOut, status_code=status.HTTP_201_CREATED)
def registrar_visita(
    datos: VisitaCreate,
    service: VisitasService = Depends(get_visitas_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Registra una visita GPS cercana al POI y acredita sus puntos."""
    return service.registrar(str(current_user.id), datos)


@router.get("/me/saldo", response_model=SaldoPuntosOut)
def obtener_mi_saldo(
    service: VisitasService = Depends(get_visitas_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Devuelve el saldo de puntos calculado desde el libro mayor."""
    return SaldoPuntosOut(saldo=service.obtener_saldo(str(current_user.id)))
