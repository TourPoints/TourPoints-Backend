from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_admin_user, get_current_user, get_optional_user, get_role_nombre, is_admin_user
from app.database import get_db
from app.models.usuario import Usuario
from app.repositories.poi_repository import PoiRepository
from app.schemas.poi import (
    EnviarRevisionResponse,
    ImagenPoiCreateOut,
    PaginatedPoiResponse,
    PoiCreate,
    PoiDetail,
    PoiModeracion,
    PoiModeracionLogOut,
    PoiUpdate,
)
from app.services.poi_service import PoiService

router = APIRouter(tags=["poi"])


def get_poi_service(db: Session = Depends(get_db)) -> PoiService:
    return PoiService(PoiRepository(db))


@router.get("", response_model=PaginatedPoiResponse)
def list_pois(
    nombre: Optional[str] = Query(None, description="Búsqueda por nombre"),
    categoria_id: Optional[int] = Query(None),
    ciudad_id: Optional[int] = Query(None),
    estado: Optional[str] = Query(None, description="Solo ADMIN puede filtrar por estado"),
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None),
    radio_metros: Optional[float] = Query(None, gt=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: PoiService = Depends(get_poi_service),
    current_user: Optional[Usuario] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Lista POI. Público: solo ve `estado=APROBADO`. ADMIN puede filtrar por cualquier estado."""
    filters = {
        "nombre": nombre,
        "categoria_id": categoria_id,
        "ciudad_id": ciudad_id,
        "estado": estado,
        "lat": lat,
        "lng": lng,
        "radio_metros": radio_metros,
    }
    filters = {k: v for k, v in filters.items() if v is not None}

    skip = (page - 1) * page_size
    return service.list_pois(
        skip=skip, limit=page_size, page=page, is_admin=is_admin_user(current_user, db), **filters
    )


@router.get("/{poi_id}", response_model=PoiDetail)
def get_poi(
    poi_id: UUID,
    service: PoiService = Depends(get_poi_service),
    current_user: Optional[Usuario] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Detalle de un POI. Si no está APROBADO, solo lo ve el dueño o un ADMIN."""
    return service.get_poi(str(poi_id), current_user, is_admin_user(current_user, db))


@router.post("", response_model=PoiDetail, status_code=status.HTTP_201_CREATED)
def create_poi(
    poi_data: PoiCreate,
    service: PoiService = Depends(get_poi_service),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crea un POI en estado BORRADOR. La `fuente` se resuelve por el rol del token, no la envía el front."""
    return service.create_poi(poi_data, current_user, get_role_nombre(current_user, db))


@router.patch("/{poi_id}", response_model=PoiDetail)
def update_poi(
    poi_id: UUID,
    poi_data: PoiUpdate,
    service: PoiService = Depends(get_poi_service),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Actualiza un POI (parcial). Solo el dueño o un ADMIN."""
    return service.update_poi(str(poi_id), poi_data, current_user, is_admin_user(current_user, db))


@router.post("/{poi_id}/enviar-revision", response_model=EnviarRevisionResponse)
def enviar_revision(
    poi_id: UUID,
    service: PoiService = Depends(get_poi_service),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Transición BORRADOR -> PENDIENTE. Solo el dueño o un ADMIN."""
    return service.enviar_revision(str(poi_id), current_user, is_admin_user(current_user, db))


@router.patch("/{poi_id}/moderacion", response_model=PoiDetail)
def moderar_poi(
    poi_id: UUID,
    data: PoiModeracion,
    service: PoiService = Depends(get_poi_service),
    admin_user: Usuario = Depends(get_admin_user),
):
    """Aprueba/rechaza/activa un POI. Solo ADMIN. Cada transición queda en el historial de auditoría."""
    return service.moderar(str(poi_id), data, admin_user)


@router.post("/{poi_id}/reintentar", response_model=PoiDetail)
def reintentar_poi(
    poi_id: UUID,
    service: PoiService = Depends(get_poi_service),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Transición RECHAZADO -> BORRADOR, para corregir y reenviar a revisión. Solo el dueño o un ADMIN."""
    return service.reintentar(str(poi_id), current_user, is_admin_user(current_user, db))


@router.get("/{poi_id}/moderaciones", response_model=List[PoiModeracionLogOut])
def get_poi_moderaciones(
    poi_id: UUID,
    service: PoiService = Depends(get_poi_service),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Historial de auditoría de cambios de estado del POI. Solo el dueño o un ADMIN."""
    return service.get_moderacion_historial(str(poi_id), current_user, is_admin_user(current_user, db))


@router.delete("/{poi_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_poi(
    poi_id: UUID,
    service: PoiService = Depends(get_poi_service),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Elimina (soft delete) un POI. Solo el dueño o un ADMIN."""
    service.delete_poi(str(poi_id), current_user, is_admin_user(current_user, db))
    return None


@router.post("/{poi_id}/imagenes", response_model=ImagenPoiCreateOut, status_code=status.HTTP_201_CREATED)
def add_poi_imagen(
    poi_id: UUID,
    file: UploadFile = File(...),
    principal: bool = Form(False),
    service: PoiService = Depends(get_poi_service),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Sube una imagen a Cloudinary y la asocia al POI. Solo el dueño o un ADMIN."""
    return service.add_imagen(str(poi_id), file, principal, current_user, is_admin_user(current_user, db))
