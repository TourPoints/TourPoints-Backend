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
    ImagenPoiOut,
    ImagenPoiUpdate,
    PaginatedPoiResponse,
    PoiCreate,
    PoiDetail,
    PoiModeracion,
    PoiModeracionLogOut,
    PoiQrCodeOut,
    PoiUpdate,
)
from app.services.poi_service import PoiService

router = APIRouter(tags=["poi"])


def get_poi_service(db: Session = Depends(get_db)) -> PoiService:
    return PoiService(PoiRepository(db))


@router.get("", response_model=PaginatedPoiResponse)
def list_pois(
    nombre: Optional[str] = Query(None, description="Search by name"),
    categoria_id: Optional[int] = Query(None),
    ciudad_id: Optional[int] = Query(None),
    estado: Optional[str] = Query(None, description="Only ADMIN can filter by status"),
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None),
    radio_metros: Optional[float] = Query(None, gt=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: PoiService = Depends(get_poi_service),
    current_user: Optional[Usuario] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Lists POIs. Public: only sees `estado=APROBADO`. ADMIN can filter by any status."""
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
    """POI detail. If not APROBADO, only the owner or an ADMIN can see it."""
    return service.get_poi(str(poi_id), current_user, is_admin_user(current_user, db))


@router.post("", response_model=PoiDetail, status_code=status.HTTP_201_CREATED)
def create_poi(
    poi_data: PoiCreate,
    service: PoiService = Depends(get_poi_service),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Creates a POI in BORRADOR status. `fuente` is resolved from the token's role, not sent by the frontend."""
    return service.create_poi(poi_data, current_user, get_role_nombre(current_user, db))


@router.patch("/{poi_id}", response_model=PoiDetail)
def update_poi(
    poi_id: UUID,
    poi_data: PoiUpdate,
    service: PoiService = Depends(get_poi_service),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Updates a POI (partial). Owner or ADMIN only."""
    return service.update_poi(str(poi_id), poi_data, current_user, is_admin_user(current_user, db))


@router.post("/{poi_id}/submit-for-review", response_model=EnviarRevisionResponse)
def enviar_revision(
    poi_id: UUID,
    service: PoiService = Depends(get_poi_service),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Transitions BORRADOR -> PENDIENTE. Owner or ADMIN only."""
    return service.enviar_revision(str(poi_id), current_user, is_admin_user(current_user, db))


@router.patch("/{poi_id}/moderation", response_model=PoiDetail)
def moderar_poi(
    poi_id: UUID,
    data: PoiModeracion,
    service: PoiService = Depends(get_poi_service),
    admin_user: Usuario = Depends(get_admin_user),
):
    """Approves/rejects/activates a POI. ADMIN only. Every transition is recorded in the audit log."""
    return service.moderar(str(poi_id), data, admin_user)


@router.post("/{poi_id}/retry", response_model=PoiDetail)
def reintentar_poi(
    poi_id: UUID,
    service: PoiService = Depends(get_poi_service),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Transitions RECHAZADO -> BORRADOR, to fix and resubmit for review. Owner or ADMIN only."""
    return service.reintentar(str(poi_id), current_user, is_admin_user(current_user, db))


@router.get("/{poi_id}/moderation-log", response_model=List[PoiModeracionLogOut])
def get_poi_moderaciones(
    poi_id: UUID,
    service: PoiService = Depends(get_poi_service),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Audit history of the POI's status changes. Owner or ADMIN only."""
    return service.get_moderacion_historial(str(poi_id), current_user, is_admin_user(current_user, db))


@router.get("/{poi_id}/qr-code", response_model=PoiQrCodeOut)
def get_poi_qr_code(
    poi_id: UUID,
    service: PoiService = Depends(get_poi_service),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """POI check-in QR code, to print/display on-site and use
    in POST /visits with metodo_validacion=QR or MIXTA. Owner or ADMIN only."""
    return service.get_qr_code(str(poi_id), current_user, is_admin_user(current_user, db))


@router.delete("/{poi_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_poi(
    poi_id: UUID,
    service: PoiService = Depends(get_poi_service),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deletes (soft delete) a POI. Owner or ADMIN only."""
    service.delete_poi(str(poi_id), current_user, is_admin_user(current_user, db))
    return None


@router.post("/{poi_id}/images", response_model=ImagenPoiCreateOut, status_code=status.HTTP_201_CREATED)
def add_poi_imagen(
    poi_id: UUID,
    file: UploadFile = File(...),
    principal: bool = Form(False),
    service: PoiService = Depends(get_poi_service),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Uploads an image to Cloudinary and links it to the POI. Owner or ADMIN only."""
    return service.add_imagen(str(poi_id), file, principal, current_user, is_admin_user(current_user, db))


@router.patch("/{poi_id}/images/{imagen_id}", response_model=ImagenPoiOut)
def update_poi_imagen(
    poi_id: UUID,
    imagen_id: int,
    data: ImagenPoiUpdate,
    service: PoiService = Depends(get_poi_service),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Changes `principal` and/or `orden` of an already-uploaded image, without re-uploading the file. Owner or ADMIN only."""
    return service.update_imagen(str(poi_id), imagen_id, data, current_user, is_admin_user(current_user, db))


@router.delete("/{poi_id}/images/{imagen_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_poi_imagen(
    poi_id: UUID,
    imagen_id: int,
    service: PoiService = Depends(get_poi_service),
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deletes an image from the POI (row + Cloudinary asset). If it was the
    principal image, automatically promotes the one with the lowest `orden`. Owner or ADMIN only."""
    service.delete_imagen(str(poi_id), imagen_id, current_user, is_admin_user(current_user, db))
    return None
