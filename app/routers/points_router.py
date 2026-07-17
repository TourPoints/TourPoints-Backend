from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.puntos import SaldoOut, MovimientoOut
from app.services.puntos_service import PuntosService

router = APIRouter(tags=["points"])


def get_puntos_service(db: Session = Depends(get_db)) -> PuntosService:
    # PuntosService inyecta una Session (construye sus propios repos
    # internamente), mismo molde que get_recompensas_service.
    return PuntosService(db)


@router.get("/me/saldo", response_model=SaldoOut)
def obtener_saldo(
    service: PuntosService = Depends(get_puntos_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Saldo actual de puntos del usuario autenticado."""
    return service.obtener_saldo(str(current_user.id))


@router.get("/me/movimientos", response_model=List[MovimientoOut])
def listar_movimientos(
    limit: int = Query(20, ge=1, le=100, description="Limite de resultados"),
    offset: int = Query(0, ge=0, description="Offset para paginacion"),
    service: PuntosService = Depends(get_puntos_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Historial de movimientos de puntos del usuario autenticado, ordenado DESC."""
    return service.listar_movimientos(str(current_user.id), limit=limit, offset=offset)