from typing import List, Optional
from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import cast, func
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import Session

from app.models.poi import CategoriaPoi, Poi, PoiModeracionLog
from app.models.social import Calificacion, ImagenPoi
from app.models.ubicacion import Ciudad
from app.repositories.base_repository import BaseRepository
from app.utils.geo import point_from_coords


class PoiRepository(BaseRepository[Poi]):
    def __init__(self, db: Session):
        self.db = db
        super().__init__(Poi)

    def _get_by_id(self, id: str) -> Poi:
        poi = self.db.query(Poi).filter(Poi.id == id, Poi.deleted_at.is_(None)).first()
        if not poi:
            raise NoResultFound(f"Poi with id {id} not found")
        return poi

    def get_by_id(self, id: str) -> Optional[Poi]:
        return self.db.query(Poi).filter(Poi.id == id, Poi.deleted_at.is_(None)).first()

    def get_by_slug(self, slug: str) -> Optional[Poi]:
        return self.db.query(Poi).filter(Poi.slug == slug).first()

    def _filtered_query(self, **filters):
        query = self.db.query(Poi).filter(Poi.deleted_at.is_(None))

        if filters.get("nombre"):
            query = query.filter(Poi.nombre.ilike(f"%{filters['nombre']}%"))
        if filters.get("categoria_id"):
            query = query.filter(Poi.categoria_id == filters["categoria_id"])
        if filters.get("ciudad_id"):
            query = query.filter(Poi.ciudad_id == filters["ciudad_id"])
        if filters.get("estado"):
            query = query.filter(Poi.estado == filters["estado"])
        else:
            query = query.filter(Poi.estado == "APROBADO")

        lat, lng, radio = filters.get("lat"), filters.get("lng"), filters.get("radio_metros")
        if lat is not None and lng is not None and radio is not None:
            punto = point_from_coords(lat, lng)
            query = query.filter(func.ST_DWithin(Poi.ubicacion, punto, float(radio)))

        return query

    def count(self, **filters) -> int:
        return self._filtered_query(**filters).count()

    def _with_aggregates(self, lat: Optional[float] = None, lng: Optional[float] = None):
        avg_sub = (
            self.db.query(
                Calificacion.poi_id.label("poi_id"),
                func.avg(Calificacion.calificacion).label("promedio"),
                func.count(Calificacion.id).label("total"),
            )
            .group_by(Calificacion.poi_id)
            .subquery()
        )
        principal_sub = (
            self.db.query(ImagenPoi.poi_id.label("poi_id"), ImagenPoi.url.label("url"))
            .filter(ImagenPoi.principal.is_(True))
            .subquery()
        )

        columns = [
            Poi,
            CategoriaPoi,
            Ciudad,
            func.ST_Y(cast(Poi.ubicacion, Geometry)).label("lat"),
            func.ST_X(cast(Poi.ubicacion, Geometry)).label("lng"),
            func.coalesce(avg_sub.c.promedio, 0.0).label("calificacion_promedio"),
            func.coalesce(avg_sub.c.total, 0).label("total_calificaciones"),
            principal_sub.c.url.label("imagen_principal"),
        ]
        if lat is not None and lng is not None:
            punto = point_from_coords(lat, lng)
            columns.append(func.ST_Distance(Poi.ubicacion, punto).label("distancia_metros"))

        return (
            self.db.query(*columns)
            .join(CategoriaPoi, CategoriaPoi.id == Poi.categoria_id)
            .join(Ciudad, Ciudad.id == Poi.ciudad_id)
            .outerjoin(avg_sub, avg_sub.c.poi_id == Poi.id)
            .outerjoin(principal_sub, principal_sub.c.poi_id == Poi.id)
        )

    def list(self, skip: int = 0, limit: int = 20, **filters):
        base = self._filtered_query(**filters)
        lat, lng = filters.get("lat"), filters.get("lng")

        if lat is not None and lng is not None:
            punto = point_from_coords(lat, lng)
            base = base.order_by(func.ST_Distance(Poi.ubicacion, punto))
        else:
            base = base.order_by(Poi.created_at.desc())

        pois = base.offset(skip).limit(limit).all()
        ids = [poi.id for poi in pois]
        if not ids:
            return []

        rows = self._with_aggregates(lat=lat, lng=lng).filter(Poi.id.in_(ids)).all()
        rows_by_id = {row.Poi.id: row for row in rows}
        return [rows_by_id[poi_id] for poi_id in ids if poi_id in rows_by_id]

    def get_detail(self, id: str):
        return self._with_aggregates().filter(Poi.id == id, Poi.deleted_at.is_(None)).first()

    def get_by_ids(self, ids: List[str]):
        if not ids:
            return []
        return self._with_aggregates().filter(Poi.id.in_(ids), Poi.deleted_at.is_(None)).all()

    def create(self, data: dict) -> Poi:
        lat = data.pop("lat")
        lng = data.pop("lng")
        metadata = data.pop("metadata", {})

        poi = Poi(
            categoria_id=data["categoria_id"],
            ciudad_id=data["ciudad_id"],
            creado_por_usuario_id=data.get("creado_por_usuario_id"),
            fuente=data.get("fuente", "ADMIN"),
            nombre=data["nombre"],
            slug=data["slug"],
            descripcion=data.get("descripcion"),
            direccion=data.get("direccion"),
            radio_validacion=data.get("radio_validacion", 50),
            telefono=data.get("telefono"),
            correo=data.get("correo"),
            sitio_web=data.get("sitio_web"),
            horarios=data.get("horarios") or {},
            metadata_=metadata,
        )
        poi.ubicacion = point_from_coords(lat, lng)
        self.db.add(poi)
        self.db.commit()
        self.db.refresh(poi)
        return poi

    def update(self, id: str, data: dict) -> Poi:
        poi = self._get_by_id(id)

        lat = data.pop("lat", None)
        lng = data.pop("lng", None)
        if "metadata" in data:
            poi.metadata_ = data.pop("metadata")

        for field, value in data.items():
            if hasattr(poi, field):
                setattr(poi, field, value)

        if lat is not None and lng is not None:
            poi.ubicacion = point_from_coords(lat, lng)

        self.db.commit()
        self.db.refresh(poi)
        return poi

    def soft_delete(self, id: str) -> None:
        poi = self._get_by_id(id)
        poi.deleted_at = datetime.utcnow()
        self.db.commit()

    def get_imagenes(self, poi_id: str) -> List[ImagenPoi]:
        return self.db.query(ImagenPoi).filter(ImagenPoi.poi_id == poi_id).order_by(ImagenPoi.orden).all()

    def next_imagen_orden(self, poi_id: str) -> int:
        max_orden = self.db.query(func.max(ImagenPoi.orden)).filter(ImagenPoi.poi_id == poi_id).scalar()
        return (max_orden + 1) if max_orden is not None else 0

    def add_imagen(self, poi_id: str, url: str, principal: bool, orden: int) -> ImagenPoi:
        if principal:
            self.db.query(ImagenPoi).filter(
                ImagenPoi.poi_id == poi_id, ImagenPoi.principal.is_(True)
            ).update({"principal": False})

        imagen = ImagenPoi(poi_id=poi_id, url=url, orden=orden, principal=principal)
        self.db.add(imagen)
        self.db.commit()
        self.db.refresh(imagen)
        return imagen

    def get_imagen(self, poi_id: str, imagen_id: int) -> Optional[ImagenPoi]:
        """Escopado por poi_id a propósito: que el id de la imagen exista no
        alcanza, tiene que pertenecer a ESTE POI (evita IDOR entre POIs)."""
        return (
            self.db.query(ImagenPoi)
            .filter(ImagenPoi.id == imagen_id, ImagenPoi.poi_id == poi_id)
            .first()
        )

    def update_imagen(self, imagen: ImagenPoi, cambios: dict) -> ImagenPoi:
        if cambios.get("principal") is True:
            self.db.query(ImagenPoi).filter(
                ImagenPoi.poi_id == imagen.poi_id,
                ImagenPoi.principal.is_(True),
                ImagenPoi.id != imagen.id,
            ).update({"principal": False})

        for field, value in cambios.items():
            if value is not None and hasattr(imagen, field):
                setattr(imagen, field, value)

        self.db.commit()
        self.db.refresh(imagen)
        return imagen

    def delete_imagen(self, imagen: ImagenPoi) -> None:
        era_principal = imagen.principal
        poi_id = imagen.poi_id
        self.db.delete(imagen)
        self.db.commit()

        if era_principal:
            siguiente = (
                self.db.query(ImagenPoi)
                .filter(ImagenPoi.poi_id == poi_id)
                .order_by(ImagenPoi.orden)
                .first()
            )
            if siguiente is not None:
                siguiente.principal = True
                self.db.commit()

    def log_transition(
        self, poi_id: str, usuario_id: str, estado_anterior: str, estado_nuevo: str, motivo: Optional[str] = None
    ) -> PoiModeracionLog:
        log = PoiModeracionLog(
            poi_id=poi_id,
            usuario_id=usuario_id,
            estado_anterior=estado_anterior,
            estado_nuevo=estado_nuevo,
            motivo=motivo,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def get_moderacion_historial(self, poi_id: str) -> List[PoiModeracionLog]:
        return (
            self.db.query(PoiModeracionLog)
            .filter(PoiModeracionLog.poi_id == poi_id)
            .order_by(PoiModeracionLog.created_at.desc())
            .all()
        )
