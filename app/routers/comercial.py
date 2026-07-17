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
    """Registra un establecimiento sobre un POI propio ya APROBADO. Nace en estado PENDIENTE
    (requiere aprobación de un ADMIN) y te registra automáticamente como dueño."""
    current_user, es_admin = user_admin
    return service.crear_establecimiento(data, current_user, es_admin)


@router.get("/businesses/me", response_model=PaginatedEstablecimientosResponse)
def list_my_businesses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: ComercialService = Depends(get_comercial_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Lista los establecimientos que administras (incluye tu `cargo` en cada uno)."""
    skip = (page - 1) * page_size
    return service.listar_mis_establecimientos(str(current_user.id), skip=skip, limit=page_size, page=page)


@router.patch("/businesses/{business_id}/moderation", response_model=EstablecimientoOut)
def moderate_business(
    business_id: UUID,
    data: EstablecimientoModeracion,
    service: ComercialService = Depends(get_comercial_service),
    admin_user: Usuario = Depends(get_admin_user),
):
    """Aprueba/rechaza/activa un establecimiento. Solo ADMIN."""
    return service.moderar_establecimiento(str(business_id), data.estado)


# --- Compras ---


@router.post("/businesses/{business_id}/purchases", response_model=CompraOut, status_code=status.HTTP_201_CREATED)
def create_purchase(
    business_id: UUID,
    data: CompraCreate,
    service: ComercialService = Depends(get_comercial_service),
    user_admin: tuple[Usuario, bool] = Depends(get_current_user_con_flag_admin),
):
    """Registra la compra de un cliente en el punto de venta. Solo staff del
    establecimiento (`establecimiento_usuarios`) o ADMIN. Acredita puntos según `reglas_puntos`."""
    current_user, es_admin = user_admin
    return service.registrar_compra(str(business_id), data, current_user, es_admin)


@router.patch("/purchases/{purchase_id}/cancel", response_model=CompraOut)
def cancel_purchase(
    purchase_id: UUID,
    service: ComercialService = Depends(get_comercial_service),
    user_admin: tuple[Usuario, bool] = Depends(get_current_user_con_flag_admin),
):
    """Cancela una compra registrada. Revierte los puntos otorgados con un
    movimiento negativo compensatorio (el ledger nunca se edita/borra)."""
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
    """Crea una promoción del establecimiento. Nace PENDIENTE, requiere aprobación de ADMIN
    para aparecer en GET /poi/{id}/promotions. Solo staff del establecimiento o ADMIN."""
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
    """Aprueba/rechaza/activa una promoción. Solo ADMIN. *(no estaba en el diseño original,
    pero sin esto una promoción se queda PENDIENTE para siempre y nunca aparece en público)*."""
    current_user, es_admin = user_admin
    return service.moderar_promocion(str(business_id), str(promotion_id), data.estado, current_user, es_admin)


@router.get("/poi/{poi_id}/promotions", response_model=PaginatedPromocionesResponse)
def list_poi_promotions(
    poi_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: ComercialService = Depends(get_comercial_service),
):
    """Público — promociones vigentes (APROBADO y dentro de inicio/fin) del establecimiento asociado a ese POI."""
    skip = (page - 1) * page_size
    return service.list_promociones_poi(str(poi_id), skip=skip, limit=page_size, page=page)
