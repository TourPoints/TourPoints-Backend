from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.puntos import PaginatedMovimientosResponse
from app.services.puntos_service import PuntosService

router = APIRouter()


def get_puntos_service(db: Session = Depends(get_db)) -> PuntosService:
    return PuntosService(db)


@router.get("/me/movements", response_model=PaginatedMovimientosResponse)
def list_my_points_movements(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: PuntosService = Depends(get_puntos_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Historial paginado del libro mayor de puntos (append-only), más reciente primero.
    El saldo agregado vive en GET /visits/me/balance, no se duplica aquí."""
    skip = (page - 1) * page_size
    return service.listar_mis_movimientos(str(current_user.id), skip=skip, limit=page_size, page=page)
