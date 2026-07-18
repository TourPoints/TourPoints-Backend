from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_admin_user, get_current_user, get_current_user_con_flag_admin
from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.comercial import (
    CompraCreate,
    CompraOut,
    EstablecimientoCreate,
    EstablecimientoModeracion,
    EstablecimientoOut,
    PaginatedEstablecimientosResponse,
    PaginatedPromocionesResponse,
    PromocionCreate,
    PromocionModeracion,
    PromocionOut,
)
from app.services.comercial_service import ComercialService

router = APIRouter(tags=["businesses"])


def get_comercial_service(db: Session = Depends(get_db)) -> ComercialService:
    return ComercialService(db)


# --- Establecimientos ---


@router.post("/businesses", response_model=EstablecimientoOut, status_code=status.HTTP_201_CREATED)
def create_business(
    data: EstablecimientoCreate,
    service: ComercialService = Depends(get_comercial_service),
    user_admin: tuple[Usuario, bool] = Depends(get_current_user_con_flag_admin),
):
    """Registers a business on top of your own, already-APROBADO POI. Starts out PENDIENTE
    (requires ADMIN approval) and automatically registers you as its owner."""
    current_user, es_admin = user_admin
    return service.crear_establecimiento(data, current_user, es_admin)


@router.get("/businesses/me", response_model=PaginatedEstablecimientosResponse)
def list_my_businesses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: ComercialService = Depends(get_comercial_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Lists the businesses you manage (includes your `cargo` in each one)."""
    skip = (page - 1) * page_size
    return service.listar_mis_establecimientos(str(current_user.id), skip=skip, limit=page_size, page=page)


@router.patch("/businesses/{business_id}/moderation", response_model=EstablecimientoOut)
def moderate_business(
    business_id: UUID,
    data: EstablecimientoModeracion,
    service: ComercialService = Depends(get_comercial_service),
    admin_user: Usuario = Depends(get_admin_user),
):
    """Approves/rejects/activates a business. ADMIN only."""
    return service.moderar_establecimiento(str(business_id), data.estado)


# --- Compras ---


@router.post("/businesses/{business_id}/purchases", response_model=CompraOut, status_code=status.HTTP_201_CREATED)
def create_purchase(
    business_id: UUID,
    data: CompraCreate,
    service: ComercialService = Depends(get_comercial_service),
    user_admin: tuple[Usuario, bool] = Depends(get_current_user_con_flag_admin),
):
    """Registers a customer's purchase at the point of sale. Only business staff
    (`establecimiento_usuarios`) or ADMIN. Credits points according to `reglas_puntos`."""
    current_user, es_admin = user_admin
    return service.registrar_compra(str(business_id), data, current_user, es_admin)


@router.patch("/purchases/{purchase_id}/cancel", response_model=CompraOut)
def cancel_purchase(
    purchase_id: UUID,
    service: ComercialService = Depends(get_comercial_service),
    user_admin: tuple[Usuario, bool] = Depends(get_current_user_con_flag_admin),
):
    """Cancels a registered purchase. Reverses the points awarded with a
    compensating negative entry (the ledger is never edited/deleted)."""
    current_user, es_admin = user_admin
    return service.cancelar_compra(str(purchase_id), current_user, es_admin)


# --- Promociones ---


@router.post(
    "/businesses/{business_id}/promotions", response_model=PromocionOut, status_code=status.HTTP_201_CREATED
)
def create_promotion(
    business_id: UUID,
    data: PromocionCreate,
    service: ComercialService = Depends(get_comercial_service),
    user_admin: tuple[Usuario, bool] = Depends(get_current_user_con_flag_admin),
):
    """Creates a business promotion. Starts out PENDIENTE, requires ADMIN approval
    to appear in GET /poi/{id}/promotions. Only business staff or ADMIN."""
    current_user, es_admin = user_admin
    return service.crear_promocion(str(business_id), data, current_user, es_admin)


@router.patch("/businesses/{business_id}/promotions/{promotion_id}/moderation", response_model=PromocionOut)
def moderate_promotion(
    business_id: UUID,
    promotion_id: UUID,
    data: PromocionModeracion,
    service: ComercialService = Depends(get_comercial_service),
    user_admin: tuple[Usuario, bool] = Depends(get_current_user_con_flag_admin),
):
    """Approves/rejects/activates a promotion. ADMIN only. *(not in the original design,
    but without this a promotion stays PENDIENTE forever and never becomes public)*."""
    current_user, es_admin = user_admin
    return service.moderar_promocion(str(business_id), str(promotion_id), data.estado, current_user, es_admin)


@router.get("/poi/{poi_id}/promotions", response_model=PaginatedPromocionesResponse)
def list_poi_promotions(
    poi_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: ComercialService = Depends(get_comercial_service),
):
    """Public — active promotions (APROBADO and within start/end dates) of the business associated with that POI."""
    skip = (page - 1) * page_size
    return service.list_promociones_poi(str(poi_id), skip=skip, limit=page_size, page=page)
