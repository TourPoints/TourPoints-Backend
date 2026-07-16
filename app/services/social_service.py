from typing import Optional

from fastapi import HTTPException, status

from app.core.exceptions import DBError, KoreansavageError, RecordNotFoundError
from app.models.usuario import Usuario
from app.repositories.social_repository import SocialRepository
from app.schemas.poi import PaginatedPoiResponse
from app.schemas.social import (
    CalificacionCreate,
    CalificacionListItem,
    CalificacionOut,
    CalificacionResumen,
    ComentarioCreate,
    ComentarioModeracion,
    ComentarioOut,
    FavoritoOut,
    PaginatedCalificacionesResponse,
    PaginatedComentariosResponse,
    UsuarioMini,
)
from app.services.poi_service import PoiService

VALID_COMENTARIO_ESTADOS = {"APROBADO", "RECHAZADO"}


class SocialService:
    def __init__(self, repository: SocialRepository, poi_service: PoiService):
        self.repository = repository
        self.poi_service = poi_service

    def _to_comentario_out(self, comentario, usuario: Usuario) -> ComentarioOut:
        return ComentarioOut(
            id=comentario.id,
            poi_id=comentario.poi_id,
            usuario=UsuarioMini.model_validate(usuario),
            contenido=comentario.contenido,
            estado=comentario.estado.value if hasattr(comentario.estado, "value") else comentario.estado,
            created_at=comentario.created_at,
        )

    # --- Calificaciones ---

    def set_mi_calificacion(self, poi_id: str, current_user: Usuario, data: CalificacionCreate) -> CalificacionOut:
        try:
            if not self.poi_service.exists(poi_id):
                raise RecordNotFoundError(f"Poi with id {poi_id} not found")
            calificacion = self.repository.upsert_calificacion(current_user.id, poi_id, data.calificacion)
            return CalificacionOut.model_validate(calificacion)
        except RecordNotFoundError:
            raise
        except Exception as exc:
            raise DBError(f"Set calificacion failed: {str(exc)}") from exc

    def delete_mi_calificacion(self, poi_id: str, current_user: Usuario) -> None:
        try:
            deleted = self.repository.delete_calificacion(current_user.id, poi_id)
            if not deleted:
                raise RecordNotFoundError("No tienes una calificación registrada para este POI")
        except RecordNotFoundError:
            raise
        except Exception as exc:
            raise DBError(f"Delete calificacion failed: {str(exc)}") from exc

    def list_calificaciones(self, poi_id: str, skip: int, limit: int, page: int) -> PaginatedCalificacionesResponse:
        try:
            rows = self.repository.list_calificaciones(poi_id, skip, limit)
            total = self.repository.count_calificaciones(poi_id)
            items = [
                CalificacionListItem(
                    id=calif.id,
                    usuario=UsuarioMini.model_validate(usuario),
                    calificacion=calif.calificacion,
                    created_at=calif.created_at,
                )
                for calif, usuario in rows
            ]
            return PaginatedCalificacionesResponse(items=items, total=total, page=page, page_size=limit)
        except Exception as exc:
            raise DBError(f"List calificaciones failed: {str(exc)}") from exc

    def resumen_calificaciones(self, poi_id: str) -> CalificacionResumen:
        try:
            promedio, total, distribucion = self.repository.resumen_calificaciones(poi_id)
            return CalificacionResumen(promedio=round(promedio, 2), total=total, distribucion=distribucion)
        except Exception as exc:
            raise DBError(f"Resumen calificaciones failed: {str(exc)}") from exc

    # --- Comentarios ---

    def create_comentario(self, poi_id: str, current_user: Usuario, data: ComentarioCreate) -> ComentarioOut:
        try:
            if not self.poi_service.exists(poi_id):
                raise RecordNotFoundError(f"Poi with id {poi_id} not found")
            comentario = self.repository.create_comentario(current_user.id, poi_id, data.contenido)
            return self._to_comentario_out(comentario, current_user)
        except RecordNotFoundError:
            raise
        except Exception as exc:
            raise DBError(f"Create comentario failed: {str(exc)}") from exc

    def list_comentarios(
        self, poi_id: str, skip: int, limit: int, page: int, estado: Optional[str], is_admin: bool
    ) -> PaginatedComentariosResponse:
        try:
            estado_filtro = estado if (estado and is_admin) else "APROBADO"
            rows = self.repository.list_comentarios(poi_id, skip, limit, estado=estado_filtro)
            total = self.repository.count_comentarios(poi_id, estado=estado_filtro)
            items = [self._to_comentario_out(comentario, usuario) for comentario, usuario in rows]
            return PaginatedComentariosResponse(items=items, total=total, page=page, page_size=limit)
        except Exception as exc:
            raise DBError(f"List comentarios failed: {str(exc)}") from exc

    def moderar_comentario(self, comentario_id: str, data: ComentarioModeracion) -> ComentarioOut:
        try:
            comentario = self.repository.get_comentario(comentario_id)
            if not comentario:
                raise RecordNotFoundError(f"Comentario with id {comentario_id} not found")
            if data.estado not in VALID_COMENTARIO_ESTADOS:
                raise KoreansavageError(f"Estado inválido: {data.estado} (usa APROBADO o RECHAZADO)")

            updated = self.repository.moderar_comentario(comentario_id, data.estado)
            usuario = self.repository.get_usuario(updated.usuario_id)
            return self._to_comentario_out(updated, usuario)
        except (KoreansavageError, RecordNotFoundError):
            raise
        except Exception as exc:
            raise DBError(f"Moderar comentario failed: {str(exc)}") from exc

    def delete_comentario(self, comentario_id: str, current_user: Usuario, is_admin: bool) -> None:
        try:
            comentario = self.repository.get_comentario(comentario_id)
            if not comentario:
                raise RecordNotFoundError(f"Comentario with id {comentario_id} not found")
            if not is_admin and str(comentario.usuario_id) != str(current_user.id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos sobre este comentario"
                )
            self.repository.delete_comentario(comentario_id)
        except HTTPException:
            raise
        except RecordNotFoundError:
            raise
        except Exception as exc:
            raise DBError(f"Delete comentario failed: {str(exc)}") from exc

    # --- Favoritos ---

    def add_favorito(self, current_user: Usuario, poi_id: str) -> FavoritoOut:
        try:
            if not self.poi_service.exists(poi_id):
                raise RecordNotFoundError(f"Poi with id {poi_id} not found")
            if self.repository.is_favorito(current_user.id, poi_id):
                raise KoreansavageError("Este POI ya está en tus favoritos")

            favorito = self.repository.add_favorito(current_user.id, poi_id)
            return FavoritoOut.model_validate(favorito)
        except (KoreansavageError, RecordNotFoundError):
            raise
        except Exception as exc:
            raise DBError(f"Add favorito failed: {str(exc)}") from exc

    def remove_favorito(self, current_user: Usuario, poi_id: str) -> None:
        try:
            deleted = self.repository.remove_favorito(current_user.id, poi_id)
            if not deleted:
                raise RecordNotFoundError("Este POI no está en tus favoritos")
        except RecordNotFoundError:
            raise
        except Exception as exc:
            raise DBError(f"Remove favorito failed: {str(exc)}") from exc

    def list_mis_favoritos(self, current_user: Usuario, skip: int, limit: int, page: int) -> PaginatedPoiResponse:
        try:
            poi_ids = self.repository.list_favoritos_poi_ids(current_user.id, skip, limit)
            total = self.repository.count_favoritos(current_user.id)
            items = self.poi_service.list_by_ids(poi_ids)
            return PaginatedPoiResponse(items=items, total=total, page=page, page_size=limit)
        except Exception as exc:
            raise DBError(f"List favoritos failed: {str(exc)}") from exc
