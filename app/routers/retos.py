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
    estado: Optional[str] = Query(None, description="Only ADMIN can filter by status"),
    establecimiento_id: Optional[UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: RetoService = Depends(get_reto_service),
    current_user: Optional[Usuario] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Lists challenges. Public: only sees `estado=ACTIVO`. ADMIN can filter by any status."""
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
    """All of your attempts (`usuario_retos`), across all periods, most recent first."""
    skip = (page - 1) * page_size
    return service.listar_mis_intentos(str(current_user.id), skip=skip, limit=page_size, page=page)


@router.get("/challenges/{challenge_id}", response_model=RetoDetail)
def get_challenge(
    challenge_id: UUID,
    service: RetoService = Depends(get_reto_service),
):
    """Full challenge detail, including `configuracion` (free-form JSONB)."""
    return service.get_reto(str(challenge_id))


@router.post("/challenges", response_model=RetoDetail, status_code=status.HTTP_201_CREATED)
def create_challenge(
    data: RetoCreate,
    service: RetoService = Depends(get_reto_service),
    user_admin: Tuple[Usuario, bool] = Depends(get_current_user_con_flag_admin),
):
    """Creates a challenge. ADMIN-created ones start ACTIVO; business-staff-created ones start BORRADOR
    (requires an ADMIN's `PATCH .../moderation` to be activated)."""
    current_user, es_admin = user_admin
    return service.crear_reto(data, current_user, es_admin)


@router.patch("/challenges/{challenge_id}/moderation", response_model=RetoDetail)
def moderate_challenge(
    challenge_id: UUID,
    data: RetoModeracion,
    service: RetoService = Depends(get_reto_service),
    admin_user: Usuario = Depends(get_admin_user),
):
    """Approves (ACTIVO) or cancels (CANCELADO) a challenge. ADMIN only."""
    return service.moderar_reto(str(challenge_id), data.estado)


# --- Inscripción / progreso ---


@router.post("/challenges/{challenge_id}/join", response_model=UsuarioRetoOut, status_code=status.HTTP_201_CREATED)
def join_challenge(
    challenge_id: UUID,
    service: RetoService = Depends(get_reto_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Enrolls you in the challenge's current period. If the challenge is GARANTIZADA,
    immediately reserves reward stock, or responds 409 if there is none."""
    return service.inscribirme(str(challenge_id), current_user)


@router.post("/challenges/{challenge_id}/abandon", response_model=UsuarioRetoOut)
def abandon_challenge(
    challenge_id: UUID,
    service: RetoService = Depends(get_reto_service),
    current_user: Usuario = Depends(get_current_user),
):
    """*(not in the original design)* Cancels your ACTIVO attempt. If the
    challenge is GARANTIZADA, automatically releases the reserved stock (via
    trigger) — without this endpoint that unit would stay locked forever."""
    return service.abandonar(str(challenge_id), current_user)


@router.get("/challenges/{challenge_id}/my-progress", response_model=UsuarioRetoOut)
def get_my_challenge_progress(
    challenge_id: UUID,
    service: RetoService = Depends(get_reto_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Your current ACTIVO attempt for that challenge (404 if you don't have one)."""
    return service.obtener_mi_progreso(str(challenge_id), current_user)


@router.post("/challenges/{challenge_id}/progress", response_model=UsuarioRetoOut)
def report_challenge_progress(
    challenge_id: UUID,
    data: RetoProgressUpdate,
    service: RetoService = Depends(get_reto_service),
    current_user: Usuario = Depends(get_current_user),
):
    """*(not in the original design)* Reports progress on your ACTIVO
    attempt. Once `cantidad_requerida` is reached, the attempt moves to FINALIZADO:
    points are credited, your streak is updated, milestones are awarded, and
    the reward redemption is issued if the challenge has one."""
    return service.reportar_progreso(str(challenge_id), data, current_user)


@router.get("/challenges/{challenge_id}/my-streak", response_model=RachaOut)
def get_my_challenge_streak(
    challenge_id: UUID,
    service: RetoService = Depends(get_reto_service),
    current_user: Usuario = Depends(get_current_user),
):
    """User's current/best streak on that challenge (0/0 if they never participated)."""
    return service.obtener_racha(str(challenge_id), current_user)


# --- Sesiones (solo tipo RECORRIDO) ---


@router.post("/challenges/{challenge_id}/sessions", response_model=SesionRetoOut, status_code=status.HTTP_201_CREATED)
def start_challenge_session(
    challenge_id: UUID,
    data: SesionRetoCreate,
    service: RetoService = Depends(get_reto_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Starts the frame for a live tracking session (the point-by-point GPS stream
    lives in Redis, outside this API — only start/end/status are persisted here)."""
    return service.crear_sesion(str(challenge_id), data, current_user)


@router.patch("/challenges/{challenge_id}/sessions/{session_id}/finish", response_model=SesionRetoOut)
def finish_challenge_session(
    challenge_id: UUID,
    session_id: UUID,
    data: SesionRetoFinalizar,
    service: RetoService = Depends(get_reto_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Closes a tracking session."""
    return service.finalizar_sesion(str(challenge_id), str(session_id), data, current_user)


# --- Insignias ---


@router.get("/users/me/badges", response_model=PaginatedInsigniasResponse)
def list_my_badges(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: RetoService = Depends(get_reto_service),
    current_user: Usuario = Depends(get_current_user),
):
    """Badges you earned via streak milestones on any challenge."""
    skip = (page - 1) * page_size
    return service.listar_mis_insignias(str(current_user.id), skip=skip, limit=page_size, page=page)
