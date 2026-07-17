from typing import Optional, Tuple
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import (
    get_admin_user,
    get_current_user,
    get_current_user_con_flag_admin,
    get_optional_user,
    is_admin_user,
)
from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.retos import (
    PaginatedInsigniasResponse,
    PaginatedRetosResponse,
    PaginatedUsuarioRetosResponse,
    RachaOut,
    RetoCreate,
    RetoDetail,
    RetoModeracion,
    RetoProgressUpdate,
    SesionRetoCreate,
    SesionRetoFinalizar,
    SesionRetoOut,
    UsuarioRetoOut,
)
from app.services.reto_service import RetoService

router = APIRouter(tags=["challenges"])


def get_reto_service(db: Session = Depends(get_db)) -> RetoService:
    return RetoService(db)


# --- Retos (plantillas) ---


@router.get("/challenges", response_model=PaginatedRetosResponse)
def list_challenges(
    tipo: Optional[str] = Query(None, description="VISITA|COMPRA|RECORRIDO"),
    estado: Optional[str] = Query(None, description="Solo ADMIN puede filtrar por estado"),
    establecimiento_id: Optional[UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: RetoService = Depends(get_reto_service),
    current_user: Optional[Usuario] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Lista retos. Público: solo ve `estado=ACTIVO`. ADMIN puede filtrar por cualquier estado."""
    filters = {"tipo": tipo, "estado": estado, "establecimiento_id": establecimiento_id}
    filters = {k: v for k, v in filters.items() if v is not None}
    skip = (page - 1) * page_size
    return service.list_retos(skip=skip, limit=page_size, page=page, is_admin=is_admin_user(current_user, db), **filters)


@router.get("/challenges/me", response_model=PaginatedUsuarioRetosResponse)
def list_my_challenge_attempts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: RetoService = Depends(get_reto_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Todos tus intentos (`usuario_retos`), todos los periodos, más reciente primero."""
    skip = (page - 1) * page_size
    return service.listar_mis_intentos(str(current_user.id), skip=skip, limit=page_size, page=page)


@router.get("/challenges/{challenge_id}", response_model=RetoDetail)
def get_challenge(
    challenge_id: UUID,
    service: RetoService = Depends(get_reto_service),
):
    """Detalle completo de un reto, incluida `configuracion` (JSONB libre)."""
    return service.get_reto(str(challenge_id))


@router.post("/challenges", response_model=RetoDetail, status_code=status.HTTP_201_CREATED)
def create_challenge(
    data: RetoCreate,
    service: RetoService = Depends(get_reto_service),
    user_admin: Tuple[Usuario, bool] = Depends(get_current_user_con_flag_admin),
):
    """Crea un reto. ADMIN nace ACTIVO; staff de un establecimiento nace BORRADOR
    (requiere `PATCH .../moderation` de un ADMIN para activarse)."""
    current_user, es_admin = user_admin
    return service.crear_reto(data, current_user, es_admin)


@router.patch("/challenges/{challenge_id}/moderation", response_model=RetoDetail)
def moderate_challenge(
    challenge_id: UUID,
    data: RetoModeracion,
    service: RetoService = Depends(get_reto_service),
    admin_user: Usuario = Depends(get_admin_user),
):
    """Aprueba (ACTIVO) o cancela (CANCELADO) un reto. Solo ADMIN."""
    return service.moderar_reto(str(challenge_id), data.estado)


# --- Inscripción / progreso ---


@router.post("/challenges/{challenge_id}/join", response_model=UsuarioRetoOut, status_code=status.HTTP_201_CREATED)
def join_challenge(
    challenge_id: UUID,
    service: RetoService = Depends(get_reto_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Te inscribe en el periodo vigente del reto. Si el reto es GARANTIZADA,
    reserva stock de la recompensa de inmediato o responde 409 si no hay."""
    return service.inscribirme(str(challenge_id), current_user)


@router.post("/challenges/{challenge_id}/abandon", response_model=UsuarioRetoOut)
def abandon_challenge(
    challenge_id: UUID,
    service: RetoService = Depends(get_reto_service),
    current_user: Usuario = Depends(get_current_user),
):
    """*(no estaba en el diseño original)* Cancela tu intento ACTIVO. Si el
    reto es GARANTIZADA, libera automáticamente el stock reservado (vía
    trigger) — sin este endpoint esa unidad quedaría atrapada para siempre."""
    return service.abandonar(str(challenge_id), current_user)


@router.get("/challenges/{challenge_id}/my-progress", response_model=UsuarioRetoOut)
def get_my_challenge_progress(
    challenge_id: UUID,
    service: RetoService = Depends(get_reto_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Tu intento ACTIVO actual para ese reto (404 si no tienes uno)."""
    return service.obtener_mi_progreso(str(challenge_id), current_user)


@router.post("/challenges/{challenge_id}/progress", response_model=UsuarioRetoOut)
def report_challenge_progress(
    challenge_id: UUID,
    data: RetoProgressUpdate,
    service: RetoService = Depends(get_reto_service),
    current_user: Usuario = Depends(get_current_user),
):
    """*(no estaba en el diseño original)* Reporta avance sobre tu intento
    ACTIVO. Al llegar a `cantidad_requerida`, el intento pasa a FINALIZADO:
    se acreditan puntos, se actualiza tu racha, se otorgan hitos y se emite
    el canje de la recompensa si el reto tiene una."""
    return service.reportar_progreso(str(challenge_id), data, current_user)


@router.get("/challenges/{challenge_id}/my-streak", response_model=RachaOut)
def get_my_challenge_streak(
    challenge_id: UUID,
    service: RetoService = Depends(get_reto_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Racha actual/máxima del usuario en ese reto (0/0 si nunca participó)."""
    return service.obtener_racha(str(challenge_id), current_user)


# --- Sesiones (solo tipo RECORRIDO) ---


@router.post("/challenges/{challenge_id}/sessions", response_model=SesionRetoOut, status_code=status.HTTP_201_CREATED)
def start_challenge_session(
    challenge_id: UUID,
    data: SesionRetoCreate,
    service: RetoService = Depends(get_reto_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Inicia el marco de una sesión de tracking en vivo (el stream GPS punto-a-punto
    vive en Redis, fuera de esta API — aquí solo se persiste inicio/fin/estado)."""
    return service.crear_sesion(str(challenge_id), data, current_user)


@router.patch("/challenges/{challenge_id}/sessions/{session_id}/finish", response_model=SesionRetoOut)
def finish_challenge_session(
    challenge_id: UUID,
    session_id: UUID,
    data: SesionRetoFinalizar,
    service: RetoService = Depends(get_reto_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Cierra una sesión de tracking."""
    return service.finalizar_sesion(str(challenge_id), str(session_id), data, current_user)


# --- Insignias ---


@router.get("/users/me/badges", response_model=PaginatedInsigniasResponse)
def list_my_badges(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: RetoService = Depends(get_reto_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Insignias que alcanzaste vía hitos de racha en cualquier reto."""
    skip = (page - 1) * page_size
    return service.listar_mis_insignias(str(current_user.id), skip=skip, limit=page_size, page=page)
