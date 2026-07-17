from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.visita import PaginatedVisitasResponse, SaldoPuntosOut, VisitaCreate, VisitaOut
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
    """Registra un check-in (GPS, QR o MIXTA) y acredita sus puntos."""
    return service.registrar(str(current_user.id), datos)


@router.get("/me", response_model=PaginatedVisitasResponse)
def list_mis_visitas(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: VisitasService = Depends(get_visitas_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Historial paginado de check-ins del usuario autenticado."""
    skip = (page - 1) * page_size
    return service.listar_mis_visitas(str(current_user.id), skip=skip, limit=page_size, page=page)


@router.get("/me/balance", response_model=SaldoPuntosOut)
def obtener_mi_saldo(
    service: VisitasService = Depends(get_visitas_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Devuelve el saldo de puntos calculado desde el libro mayor."""
    return SaldoPuntosOut(saldo=service.obtener_saldo(str(current_user.id)))
