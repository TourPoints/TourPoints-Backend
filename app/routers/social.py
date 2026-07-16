from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_admin_user, get_current_user, get_optional_user, is_admin_user
from app.database import get_db
from app.models.usuario import Usuario
from app.repositories.poi_repository import PoiRepository
from app.repositories.social_repository import SocialRepository
from app.schemas.poi import PaginatedPoiResponse
from app.schemas.social import (
    CalificacionCreate,
    CalificacionOut,
    CalificacionResumen,
    ComentarioCreate,
    ComentarioModeracion,
    ComentarioOut,
    FavoritoCreate,
    FavoritoOut,
    PaginatedCalificacionesResponse,
    PaginatedComentariosResponse,
)
from app.services.poi_service import PoiService
from app.services.social_service import SocialService

router = APIRouter(tags=["social"])


def get_social_service(db: Session = Depends(get_db)) -> SocialService:
    return SocialService(SocialRepository(db), PoiService(PoiRepository(db)))


# --- Calificaciones ---


@router.put("/poi/{poi_id}/mi-calificacion", response_model=CalificacionOut)
def set_mi_calificacion(
    poi_id: UUID,
    data: CalificacionCreate,
    service: SocialService = Depends(get_social_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Califica un POI (1-5). Si ya existía una calificación tuya, se actualiza en vez de duplicarse."""
    return service.set_mi_calificacion(str(poi_id), current_user, data)


@router.delete("/poi/{poi_id}/mi-calificacion", status_code=status.HTTP_204_NO_CONTENT)
def delete_mi_calificacion(
    poi_id: UUID,
    service: SocialService = Depends(get_social_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Elimina tu calificación sobre un POI."""
    service.delete_mi_calificacion(str(poi_id), current_user)
    return None


@router.get("/poi/{poi_id}/calificaciones", response_model=PaginatedCalificacionesResponse)
def list_calificaciones(
    poi_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: SocialService = Depends(get_social_service),
):
    """Lista pública y paginada de calificaciones de un POI."""
    skip = (page - 1) * page_size
    return service.list_calificaciones(str(poi_id), skip=skip, limit=page_size, page=page)


@router.get("/poi/{poi_id}/calificaciones/resumen", response_model=CalificacionResumen)
def resumen_calificaciones(
    poi_id: UUID,
    service: SocialService = Depends(get_social_service),
):
    """Promedio, total y distribución (1-5) de calificaciones de un POI."""
    return service.resumen_calificaciones(str(poi_id))


# --- Comentarios ---


@router.post("/poi/{poi_id}/comentarios", response_model=ComentarioOut, status_code=status.HTTP_201_CREATED)
def create_comentario(
    poi_id: UUID,
    data: ComentarioCreate,
    service: SocialService = Depends(get_social_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Crea un comentario sobre un POI. Nace en estado PENDIENTE, requiere moderación."""
    return service.create_comentario(str(poi_id), current_user, data)


@router.get("/poi/{poi_id}/comentarios", response_model=PaginatedComentariosResponse)
def list_comentarios(
    poi_id: UUID,
    estado: Optional[str] = Query(None, description="Solo ADMIN puede filtrar por estado"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: SocialService = Depends(get_social_service),
    current_user: Optional[Usuario] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Lista pública de comentarios de un POI. Por defecto solo APROBADO; ADMIN puede ver otros estados."""
    skip = (page - 1) * page_size
    return service.list_comentarios(
        str(poi_id), skip=skip, limit=page_size, page=page, estado=estado, is_admin=is_admin_user(current_user, db)
    )


@router.patch("/comentarios/{comentario_id}/moderacion", response_model=ComentarioOut)
def moderar_comentario(
    comentario_id: int,
    data: ComentarioModeracion,
    service: SocialService = Depends(get_social_service),
    admin_user: Usuario = Depends(get_admin_user),
):
    """Aprueba o rechaza un comentario. Solo ADMIN."""
    return service.moderar_comentario(comentario_id, data)


@router.delete("/comentarios/{comentario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comentario(
    comentario_id: int,
    service: SocialService = Depends(get_social_service),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Elimina un comentario. Solo el dueño o un ADMIN."""
    service.delete_comentario(comentario_id, current_user, is_admin_user(current_user, db))
    return None


# --- Favoritos ---


@router.post("/favoritos", response_model=FavoritoOut, status_code=status.HTTP_201_CREATED)
def add_favorito(
    data: FavoritoCreate,
    service: SocialService = Depends(get_social_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Agrega un POI a tus favoritos."""
    return service.add_favorito(current_user, str(data.poi_id))


@router.delete("/favoritos/{poi_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorito(
    poi_id: UUID,
    service: SocialService = Depends(get_social_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Quita un POI de tus favoritos."""
    service.remove_favorito(current_user, str(poi_id))
    return None


@router.get("/favoritos/me", response_model=PaginatedPoiResponse)
def list_mis_favoritos(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: SocialService = Depends(get_social_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Lista tus POI favoritos, con el mismo shape resumido que GET /poi."""
    skip = (page - 1) * page_size
    return service.list_mis_favoritos(current_user, skip=skip, limit=page_size, page=page)
