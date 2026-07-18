from typing import Optional, Tuple

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_admin_user, get_current_user, get_current_user_con_flag_admin
from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.gamificacion import (
    CanjeOut,
    PaginatedRecompensasResponse,
    RecompensaCreate,
    RecompensaOut,
    RecompensaUpdate,
)
from app.services.recompensas_service import RecompensasService

router = APIRouter(tags=["rewards"])


def get_recompensas_service(db: Session = Depends(get_db)) -> RecompensasService:
    # RecompensasService inyecta una Session (construye sus propios repos
    # internamente) — no un repo suelto. Pasarle `repo` rompe el __init__.
    return RecompensasService(db)


@router.post("", response_model=RecompensaOut, status_code=status.HTTP_201_CREATED)
def crear_recompensa(
    datos: RecompensaCreate,
    service: RecompensasService = Depends(get_recompensas_service),
    admin_user: Usuario = Depends(get_admin_user),
):
    """Creates a reward (admin only). Status is always APROBADO."""
    return service.crear(datos)


@router.get("", response_model=PaginatedRecompensasResponse)
def listar_recompensas(
    poi_id: Optional[str] = Query(None, description="Filter by POI (partner)"),
    estado: Optional[str] = Query(None, description="Filter by status (only admin sees non-APROBADO)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: RecompensasService = Depends(get_recompensas_service),
    user_admin: Tuple[Usuario, bool] = Depends(get_current_user_con_flag_admin),
):
    """Lists rewards. Regular users only see APROBADO; admin sees everything, filterable."""
    _, es_admin = user_admin
    solo_aprobado = not es_admin
    skip = (page - 1) * page_size
    return service.listar(
        skip=skip, limit=page_size, page=page, poi_id=poi_id, estado=estado, solo_aprobado=solo_aprobado
    )


@router.get("/{recompensa_id}", response_model=RecompensaOut)
def obtener_recompensa(
    recompensa_id: str,
    service: RecompensasService = Depends(get_recompensas_service),
    user_admin: Tuple[Usuario, bool] = Depends(get_current_user_con_flag_admin),
):
    """Reward detail. Regular users only see APROBADO."""
    _, es_admin = user_admin
    solo_aprobado = not es_admin
    return service.obtener(recompensa_id, solo_aprobado=solo_aprobado)


@router.patch("/{recompensa_id}", response_model=RecompensaOut)
def actualizar_recompensa(
    recompensa_id: str,
    datos: RecompensaUpdate,
    service: RecompensasService = Depends(get_recompensas_service),
    admin_user: Usuario = Depends(get_admin_user),
):
    """Updates a reward (admin only). Partial PATCH."""
    return service.actualizar(recompensa_id, datos)


@router.post("/{recompensa_id}/redeem", response_model=CanjeOut, status_code=status.HTTP_201_CREATED)
def canjear_recompensa(
    recompensa_id: str,
    service: RecompensasService = Depends(get_recompensas_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Redeems a reward with points (authenticated user). Origen=PUNTOS."""
    return service.canjear(current_user.id, recompensa_id)