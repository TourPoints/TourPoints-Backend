from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_current_user_con_flag_admin
from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.gamificacion import CanjeValidacionOut, CanjeValidateQR, PaginatedCanjesResponse
from app.services.recompensas_service import RecompensasService

router = APIRouter(tags=["redemptions"])


def get_recompensas_service(db: Session = Depends(get_db)) -> RecompensasService:
    return RecompensasService(db)


@router.get("/me", response_model=PaginatedCanjesResponse)
def list_mis_canjes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: RecompensasService = Depends(get_recompensas_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Historial paginado de canjes del usuario autenticado."""
    skip = (page - 1) * page_size
    return service.listar_mis_canjes(str(current_user.id), skip=skip, limit=page_size, page=page)


@router.get("/{id}", response_model=CanjeValidacionOut)
def get_canje(
    id: str,
    service: RecompensasService = Depends(get_recompensas_service),
    user_admin: tuple[Usuario, bool] = Depends(get_current_user_con_flag_admin),
):
    """Detalle de un canje. Solo el dueño o un ADMIN."""
    current_user, es_admin = user_admin
    return service.obtener_canje(id, current_user, es_admin)


@router.post("/validate-qr", response_model=CanjeValidacionOut)
def validate_qr(
    data: CanjeValidateQR,
    service: RecompensasService = Depends(get_recompensas_service),
    user_admin: tuple[Usuario, bool] = Depends(get_current_user_con_flag_admin),
):
    """Redime un canje presentado físicamente por su código QR. Solo ADMIN o
    staff del establecimiento dueño de la recompensa (quien escanea el QR
    en el punto de canje) — autorización por pertenencia real, no por rol global."""
    current_user, es_admin = user_admin
    return service.validar_qr(data.codigo_qr, current_user, es_admin)
