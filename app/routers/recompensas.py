from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_admin_user, get_current_user, get_current_user_con_flag_admin
from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.gamificacion import CanjeOut, RecompensaCreate, RecompensaOut, RecompensaUpdate
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
    """Crea una recompensa (solo admin). Estado fijo APROBADO."""
    return service.crear(datos)


@router.get("", response_model=List[RecompensaOut])
def listar_recompensas(
    poi_id: Optional[str] = Query(None, description="Filtrar por POI (aliado)"),
    estado: Optional[str] = Query(None, description="Filtrar por estado (solo admin ve no-APROBADO)"),
    limit: int = Query(100, ge=1, le=100, description="Limite de resultados"),
    offset: int = Query(0, ge=0, description="Offset para paginacion"),
    service: RecompensasService = Depends(get_recompensas_service),
    user_admin: Tuple[Usuario, bool] = Depends(get_current_user_con_flag_admin),
):
    """Lista recompensas. Usuario comun ve solo APROBADO; admin ve todo con filtro."""
    _, es_admin = user_admin
    solo_aprobado = not es_admin
    return service.listar(
        poi_id=poi_id, estado=estado, solo_aprobado=solo_aprobado, limit=limit, offset=offset
    )


@router.get("/{recompensa_id}", response_model=RecompensaOut)
def obtener_recompensa(
    recompensa_id: str,
    service: RecompensasService = Depends(get_recompensas_service),
    user_admin: Tuple[Usuario, bool] = Depends(get_current_user_con_flag_admin),
):
    """Detalle de una recompensa. Usuario comun solo ve APROBADO."""
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
    """Actualiza una recompensa (solo admin). PATCH parcial."""
    return service.actualizar(recompensa_id, datos)


@router.post("/{recompensa_id}/canjear", response_model=CanjeOut, status_code=status.HTTP_201_CREATED)
def canjear_recompensa(
    recompensa_id: str,
    service: RecompensasService = Depends(get_recompensas_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Canjea una recompensa por puntos (usuario autenticado). Origen=PUNTOS."""
    return service.canjear(current_user.id, recompensa_id)