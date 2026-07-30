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


@router.put("/poi/{poi_id}/my-rating", response_model=CalificacionOut)
def set_mi_calificacion(
    poi_id: UUID,
    data: CalificacionCreate,
    service: SocialService = Depends(get_social_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Rates a POI (1-5). If you already had a rating, it gets updated instead of duplicated."""
    return service.set_mi_calificacion(str(poi_id), current_user, data)


@router.delete("/poi/{poi_id}/my-rating", status_code=status.HTTP_204_NO_CONTENT)
def delete_mi_calificacion(
    poi_id: UUID,
    service: SocialService = Depends(get_social_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Deletes your rating on a POI."""
    service.delete_mi_calificacion(str(poi_id), current_user)
    return None


@router.get("/poi/{poi_id}/ratings", response_model=PaginatedCalificacionesResponse)
def list_calificaciones(
    poi_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: SocialService = Depends(get_social_service),
):
    """Public, paginated list of a POI's ratings."""
    skip = (page - 1) * page_size
    return service.list_calificaciones(str(poi_id), skip=skip, limit=page_size, page=page)


@router.get("/poi/{poi_id}/ratings/summary", response_model=CalificacionResumen)
def resumen_calificaciones(
    poi_id: UUID,
    service: SocialService = Depends(get_social_service),
):
    """Average, total, and distribution (1-5) of a POI's ratings."""
    return service.resumen_calificaciones(str(poi_id))


# --- Comentarios ---


@router.post("/poi/{poi_id}/comments", response_model=ComentarioOut, status_code=status.HTTP_201_CREATED)
def create_comentario(
    poi_id: UUID,
    data: ComentarioCreate,
    service: SocialService = Depends(get_social_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Creates a comment on a POI. Starts out PENDIENTE, requires moderation."""
    return service.create_comentario(str(poi_id), current_user, data)


@router.get("/poi/{poi_id}/comments", response_model=PaginatedComentariosResponse)
def list_comentarios(
    poi_id: UUID,
    estado: Optional[str] = Query(None, description="Only ADMIN can filter by status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: SocialService = Depends(get_social_service),
    current_user: Optional[Usuario] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Public list of a POI's comments. Defaults to only APROBADO; ADMIN can view other statuses."""
    skip = (page - 1) * page_size
    return service.list_comentarios(
        str(poi_id), skip=skip, limit=page_size, page=page, estado=estado, is_admin=is_admin_user(current_user, db)
    )


@router.patch("/comments/{comentario_id}/moderation", response_model=ComentarioOut)
def moderar_comentario(
    comentario_id: int,
    data: ComentarioModeracion,
    service: SocialService = Depends(get_social_service),
    admin_user: Usuario = Depends(get_admin_user),
):
    """Approves or rejects a comment. ADMIN only."""
    return service.moderar_comentario(comentario_id, data)


@router.delete("/comments/{comentario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comentario(
    comentario_id: int,
    service: SocialService = Depends(get_social_service),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deletes a comment. Owner or ADMIN only."""
    service.delete_comentario(comentario_id, current_user, is_admin_user(current_user, db))
    return None


# --- Favoritos ---


@router.post("/favorites", response_model=FavoritoOut, status_code=status.HTTP_201_CREATED)
def add_favorito(
    data: FavoritoCreate,
    service: SocialService = Depends(get_social_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Adds a POI to your favorites."""
    return service.add_favorito(current_user, str(data.poi_id))


@router.delete("/favorites/{poi_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorito(
    poi_id: UUID,
    service: SocialService = Depends(get_social_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Removes a POI from your favorites."""
    service.remove_favorito(current_user, str(poi_id))
    return None


@router.get("/favorites/me", response_model=PaginatedPoiResponse)
def list_mis_favoritos(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: SocialService = Depends(get_social_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Lists your favorite POIs, with the same summarized shape as GET /poi."""
    skip = (page - 1) * page_size
    return service.list_mis_favoritos(current_user, skip=skip, limit=page_size, page=page)
