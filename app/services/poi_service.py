import logging
import re
import unicodedata
from typing import List, Optional

from fastapi import HTTPException, UploadFile, status

from app.core.exceptions import ConflictError, DBError, RecordNotFoundError
from app.models.enums import PoiEstado, PoiFuente
from app.models.poi import Poi
from app.models.usuario import Usuario
from app.repositories.poi_repository import PoiRepository
from app.schemas.poi import (
    CategoriaPoiOut,
    CiudadOut,
    Coordenadas,
    EnviarRevisionResponse,
    ImagenPoiCreateOut,
    ImagenPoiOut,
    ImagenPoiUpdate,
    PaginatedPoiResponse,
    PoiCreate,
    PoiDetail,
    PoiListItem,
    PoiModeracion,
    PoiModeracionLogOut,
    PoiQrCodeOut,
    PoiUpdate,
)
from app.services.cloudinary_service import extraer_public_id, upload_poi_imagen
from app.services.cloudinary_service import delete_imagen as cloudinary_delete_imagen
from app.utils.media import ALLOWED_IMAGE_CONTENT_TYPES
from app.utils.qr import generar_qr_checkin_poi

ROLE_TO_FUENTE = {
    "admin": PoiFuente.ADMIN,
    "usuario": PoiFuente.USUARIO,
    "establecimiento": PoiFuente.ESTABLECIMIENTO,
}

VALID_MODERATION_TRANSITIONS = {
    PoiEstado.PENDIENTE: {PoiEstado.APROBADO, PoiEstado.RECHAZADO},
    PoiEstado.APROBADO: {PoiEstado.INACTIVO},
    PoiEstado.INACTIVO: {PoiEstado.APROBADO},
}


def slugify(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-zA-Z0-9]+", "-", texto).strip("-").lower()
    return texto or "poi"


class PoiService:
    def __init__(self, repository: PoiRepository):
        self.repository = repository

    def _generate_unique_slug(self, nombre: str, exclude_poi_id: Optional[str] = None) -> str:
        base = slugify(nombre)
        slug = base
        suffix = 2
        while True:
            existing = self.repository.get_by_slug(slug)
            if not existing or (exclude_poi_id and str(existing.id) == str(exclude_poi_id)):
                return slug
            slug = f"{base}-{suffix}"
            suffix += 1

    def _resolve_fuente(self, role_nombre: str) -> PoiFuente:
        return ROLE_TO_FUENTE.get((role_nombre or "").lower(), PoiFuente.USUARIO)

    def _ensure_owner_or_admin(self, poi: Poi, current_user: Usuario, is_admin: bool) -> None:
        if is_admin:
            return
        if current_user is None or str(poi.creado_por_usuario_id) != str(current_user.id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permisos sobre este POI")

    def _to_list_item(self, row) -> PoiListItem:
        poi = row.Poi
        return PoiListItem(
            id=poi.id,
            nombre=poi.nombre,
            slug=poi.slug,
            categoria=CategoriaPoiOut.model_validate(row.CategoriaPoi),
            ciudad=CiudadOut.model_validate(row.Ciudad),
            ubicacion=Coordenadas(lat=row.lat, lng=row.lng),
            calificacion_promedio=round(float(row.calificacion_promedio), 2),
            total_calificaciones=int(row.total_calificaciones),
            imagen_principal=row.imagen_principal,
            distancia_metros=(
                round(float(row.distancia_metros), 1) if getattr(row, "distancia_metros", None) is not None else None
            ),
        )

    def _to_detail(self, row, imagenes) -> PoiDetail:
        poi = row.Poi
        return PoiDetail(
            id=poi.id,
            nombre=poi.nombre,
            slug=poi.slug,
            descripcion=poi.descripcion,
            direccion=poi.direccion,
            ubicacion=Coordenadas(lat=row.lat, lng=row.lng),
            radio_validacion=poi.radio_validacion,
            telefono=poi.telefono,
            correo=poi.correo,
            sitio_web=poi.sitio_web,
            horarios=poi.horarios or {},
            metadata=poi.metadata_ or {},
            categoria=CategoriaPoiOut.model_validate(row.CategoriaPoi),
            ciudad=CiudadOut.model_validate(row.Ciudad),
            estado=poi.estado.value if hasattr(poi.estado, "value") else poi.estado,
            fuente=poi.fuente.value if hasattr(poi.fuente, "value") else poi.fuente,
            nivel=poi.nivel,
            calificacion_promedio=round(float(row.calificacion_promedio), 2),
            total_calificaciones=int(row.total_calificaciones),
            imagenes=[ImagenPoiOut.model_validate(img) for img in imagenes],
            created_at=poi.created_at,
        )

    def create_poi(self, data: PoiCreate, current_user: Usuario, role_nombre: str) -> PoiDetail:
        try:
            slug = self._generate_unique_slug(data.nombre)
            fuente = self._resolve_fuente(role_nombre)

            poi_data = data.model_dump(exclude={"ubicacion"})
            poi_data["lat"] = data.ubicacion.lat
            poi_data["lng"] = data.ubicacion.lng
            poi_data["slug"] = slug
            poi_data["fuente"] = fuente.value
            poi_data["creado_por_usuario_id"] = current_user.id

            poi = self.repository.create(poi_data)
            return self.get_poi(str(poi.id), current_user, is_admin=True)
        except ConflictError:
            raise
        except Exception as exc:
            raise DBError(f"Poi creation failed: {str(exc)}") from exc

    def get_poi(self, poi_id: str, current_user: Optional[Usuario], is_admin: bool) -> PoiDetail:
        try:
            row = self.repository.get_detail(poi_id)
            if not row:
                raise RecordNotFoundError(f"Poi with id {poi_id} not found")

            poi = row.Poi
            if poi.estado != PoiEstado.APROBADO.value and not is_admin:
                is_owner = current_user is not None and str(poi.creado_por_usuario_id) == str(current_user.id)
                if not is_owner:
                    raise RecordNotFoundError(f"Poi with id {poi_id} not found")

            imagenes = self.repository.get_imagenes(poi_id)
            return self._to_detail(row, imagenes)
        except RecordNotFoundError:
            raise
        except Exception as exc:
            raise DBError(f"Get poi failed: {str(exc)}") from exc

    def exists(self, poi_id: str) -> bool:
        return self.repository.get_by_id(poi_id) is not None

    def list_by_ids(self, ids: List[str]) -> List[PoiListItem]:
        """Devuelve los POI de `ids` con el mismo shape resumido de GET /poi, preservando el orden de `ids`."""
        rows = self.repository.get_by_ids(ids)
        rows_by_id = {row.Poi.id: row for row in rows}
        return [self._to_list_item(rows_by_id[i]) for i in ids if i in rows_by_id]

    def list_pois(self, skip: int, limit: int, page: int, is_admin: bool, **filters) -> PaginatedPoiResponse:
        try:
            if not is_admin:
                filters.pop("estado", None)

            rows = self.repository.list(skip=skip, limit=limit, **filters)
            total = self.repository.count(**filters)
            items = [self._to_list_item(row) for row in rows]
            return PaginatedPoiResponse(items=items, total=total, page=page, page_size=limit)
        except Exception as exc:
            raise DBError(f"List pois failed: {str(exc)}") from exc

    def update_poi(self, poi_id: str, data: PoiUpdate, current_user: Usuario, is_admin: bool) -> PoiDetail:
        try:
            poi = self.repository.get_by_id(poi_id)
            if not poi:
                raise RecordNotFoundError(f"Poi with id {poi_id} not found")
            self._ensure_owner_or_admin(poi, current_user, is_admin)

            update_data = data.model_dump(exclude_unset=True)
            if "ubicacion" in update_data:
                coords = update_data.pop("ubicacion")
                update_data["lat"] = coords["lat"]
                update_data["lng"] = coords["lng"]
            if "nombre" in update_data:
                update_data["slug"] = self._generate_unique_slug(update_data["nombre"], exclude_poi_id=poi_id)

            self.repository.update(poi_id, update_data)
            return self.get_poi(poi_id, current_user, is_admin)
        except HTTPException:
            raise
        except Exception as exc:
            raise DBError(f"Poi update failed: {str(exc)}") from exc

    def enviar_revision(self, poi_id: str, current_user: Usuario, is_admin: bool) -> EnviarRevisionResponse:
        try:
            poi = self.repository.get_by_id(poi_id)
            if not poi:
                raise RecordNotFoundError(f"Poi with id {poi_id} not found")
            self._ensure_owner_or_admin(poi, current_user, is_admin)

            if poi.estado != PoiEstado.BORRADOR.value:
                raise ConflictError(
                    f"Solo un POI en estado BORRADOR puede enviarse a revisión (estado actual: {poi.estado})"
                )

            updated = self.repository.update(poi_id, {"estado": PoiEstado.PENDIENTE.value})
            self.repository.log_transition(
                poi_id, current_user.id, PoiEstado.BORRADOR.value, PoiEstado.PENDIENTE.value
            )
            return EnviarRevisionResponse(id=updated.id, estado=updated.estado)
        except HTTPException:
            raise
        except Exception as exc:
            raise DBError(f"Poi enviar-revision failed: {str(exc)}") from exc

    def moderar(self, poi_id: str, data: PoiModeracion, admin_user: Usuario) -> PoiDetail:
        try:
            poi = self.repository.get_by_id(poi_id)
            if not poi:
                raise RecordNotFoundError(f"Poi with id {poi_id} not found")

            try:
                nuevo_estado = PoiEstado(data.estado)
            except ValueError as exc:
                raise ConflictError(f"Estado inválido: {data.estado}") from exc

            actual_estado = PoiEstado(poi.estado)
            permitidos = VALID_MODERATION_TRANSITIONS.get(actual_estado, set())
            if nuevo_estado not in permitidos:
                raise ConflictError(f"Transición no permitida: {actual_estado.value} -> {nuevo_estado.value}")

            self.repository.update(poi_id, {"estado": nuevo_estado.value})
            self.repository.log_transition(
                poi_id, admin_user.id, actual_estado.value, nuevo_estado.value, motivo=data.motivo
            )
            return self.get_poi(poi_id, admin_user, is_admin=True)
        except HTTPException:
            raise
        except Exception as exc:
            raise DBError(f"Poi moderacion failed: {str(exc)}") from exc

    def reintentar(self, poi_id: str, current_user: Usuario, is_admin: bool) -> PoiDetail:
        """Reabre un POI rechazado para que su dueño lo corrija y lo reenvíe a revisión.

        Completa la transición RECHAZADO -> BORRADOR del diagrama de estados
        (doc/logica_negocio.md) que no tenía endpoint propio.
        """
        try:
            poi = self.repository.get_by_id(poi_id)
            if not poi:
                raise RecordNotFoundError(f"Poi with id {poi_id} not found")
            self._ensure_owner_or_admin(poi, current_user, is_admin)

            if poi.estado != PoiEstado.RECHAZADO.value:
                raise ConflictError(
                    f"Solo un POI RECHAZADO puede reabrirse a BORRADOR (estado actual: {poi.estado})"
                )

            self.repository.update(poi_id, {"estado": PoiEstado.BORRADOR.value})
            self.repository.log_transition(
                poi_id, current_user.id, PoiEstado.RECHAZADO.value, PoiEstado.BORRADOR.value
            )
            return self.get_poi(poi_id, current_user, is_admin)
        except HTTPException:
            raise
        except Exception as exc:
            raise DBError(f"Poi reintentar failed: {str(exc)}") from exc

    def get_moderacion_historial(
        self, poi_id: str, current_user: Usuario, is_admin: bool
    ) -> List[PoiModeracionLogOut]:
        try:
            poi = self.repository.get_by_id(poi_id)
            if not poi:
                raise RecordNotFoundError(f"Poi with id {poi_id} not found")
            self._ensure_owner_or_admin(poi, current_user, is_admin)

            logs = self.repository.get_moderacion_historial(poi_id)
            return [PoiModeracionLogOut.model_validate(log) for log in logs]
        except HTTPException:
            raise
        except Exception as exc:
            raise DBError(f"Poi moderacion historial failed: {str(exc)}") from exc

    def get_qr_code(self, poi_id: str, current_user: Usuario, is_admin: bool) -> PoiQrCodeOut:
        """Código QR de check-in del POI, para imprimir/mostrar en el sitio.
        Determinístico (HMAC sobre poi_id): no se guarda en la base de datos,
        se recalcula igual cada vez. Solo el dueño o un ADMIN pueden verlo."""
        poi = self.repository.get_by_id(poi_id)
        if not poi:
            raise RecordNotFoundError(f"Poi with id {poi_id} not found")
        self._ensure_owner_or_admin(poi, current_user, is_admin)
        return PoiQrCodeOut(codigo_qr=generar_qr_checkin_poi(str(poi.id)))

    def delete_poi(self, poi_id: str, current_user: Usuario, is_admin: bool) -> None:
        try:
            poi = self.repository.get_by_id(poi_id)
            if not poi:
                raise RecordNotFoundError(f"Poi with id {poi_id} not found")
            self._ensure_owner_or_admin(poi, current_user, is_admin)

            self.repository.soft_delete(poi_id)
        except HTTPException:
            raise
        except Exception as exc:
            raise DBError(f"Poi delete failed: {str(exc)}") from exc

    def add_imagen(
        self, poi_id: str, file: UploadFile, principal: bool, current_user: Usuario, is_admin: bool
    ) -> ImagenPoiCreateOut:
        try:
            poi = self.repository.get_by_id(poi_id)
            if not poi:
                raise RecordNotFoundError(f"Poi with id {poi_id} not found")
            self._ensure_owner_or_admin(poi, current_user, is_admin)

            if file.content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
                raise HTTPException(status_code=422, detail="Formato de imagen no soportado (usa JPEG, PNG o WEBP)")

            upload_result = upload_poi_imagen(file.file, poi_id=str(poi_id))
            orden = self.repository.next_imagen_orden(poi_id)
            imagen = self.repository.add_imagen(poi_id, upload_result["secure_url"], principal, orden)
            return ImagenPoiCreateOut.model_validate(imagen)
        except HTTPException:
            raise
        except Exception as exc:
            raise DBError(f"Poi image upload failed: {str(exc)}") from exc

    def update_imagen(
        self, poi_id: str, imagen_id: int, data: ImagenPoiUpdate, current_user: Usuario, is_admin: bool
    ) -> ImagenPoiOut:
        """PATCH parcial: cambiar `principal` y/o `orden` sin resubir el archivo."""
        try:
            poi = self.repository.get_by_id(poi_id)
            if not poi:
                raise RecordNotFoundError(f"Poi with id {poi_id} not found")
            self._ensure_owner_or_admin(poi, current_user, is_admin)

            imagen = self.repository.get_imagen(poi_id, imagen_id)
            if imagen is None:
                raise RecordNotFoundError(f"Imagen with id {imagen_id} not found for this POI")

            cambios = data.model_dump(exclude_unset=True)
            imagen = self.repository.update_imagen(imagen, cambios)
            return ImagenPoiOut.model_validate(imagen)
        except HTTPException:
            raise
        except Exception as exc:
            raise DBError(f"Poi image update failed: {str(exc)}") from exc

    def delete_imagen(self, poi_id: str, imagen_id: int, current_user: Usuario, is_admin: bool) -> None:
        """Borra la imagen (fila + asset en Cloudinary). Si era la principal y
        quedan otras, promueve la de menor `orden` automáticamente."""
        try:
            poi = self.repository.get_by_id(poi_id)
            if not poi:
                raise RecordNotFoundError(f"Poi with id {poi_id} not found")
            self._ensure_owner_or_admin(poi, current_user, is_admin)

            imagen = self.repository.get_imagen(poi_id, imagen_id)
            if imagen is None:
                raise RecordNotFoundError(f"Imagen with id {imagen_id} not found for this POI")

            public_id = extraer_public_id(imagen.url)
            if public_id:
                try:
                    cloudinary_delete_imagen(public_id)
                except Exception:
                    # No bloquear el borrado en BD por un fallo transitorio de
                    # Cloudinary: peor caso es un asset huérfano en el storage,
                    # no una referencia rota en la API.
                    logging.exception("No se pudo borrar el asset en Cloudinary: %s", public_id)

            self.repository.delete_imagen(imagen)
        except HTTPException:
            raise
        except Exception as exc:
            raise DBError(f"Poi image delete failed: {str(exc)}") from exc
