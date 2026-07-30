from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import DBError, RecordNotFoundError
from app.models.enums import MetodoValidacion, PoiEstado, VisitaEstado
from app.models.gamificacion import ReglaPuntos
from app.models.movimiento_puntos import MovimientoPuntos
from app.models.poi import CategoriaPoi, Poi
from app.models.visita import Visita
from app.repositories.movimiento_puntos_repository import MovimientoPuntosRepository
from app.repositories.puntos_repository import PuntosRepository
from app.schemas.visita import (
    PaginatedVisitasResponse,
    VisitaCreate,
    VisitaHistorialItem,
    VisitaOut,
    VisitaPoiMini,
)
from app.utils.qr import verificar_qr_checkin_poi

# Solo se usa si no se ejecutó el seed de reglas_puntos o este no contiene una
# regla aplicable a VISITA. En un entorno normal, la regla base sembrada gana.
PUNTOS_VISITA_POR_DEFECTO = 100


class VisitasService:
    def __init__(self, db: Session):
        self.db = db
        self.movimiento_repo = MovimientoPuntosRepository(db)
        self.puntos_repo = PuntosRepository(db)

    def registrar(self, usuario_id: str, datos: VisitaCreate) -> VisitaOut:
        """Valida una visita (GPS, QR o MIXTA) y acredita sus puntos en la misma transacción."""
        poi = self.db.query(Poi).filter(Poi.id == datos.poi_id).first()
        if poi is None or poi.estado != PoiEstado.APROBADO:
            raise RecordNotFoundError(f"POI with id {datos.poi_id} not found")

        inicio_dia = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        ya_validada = (
            self.db.query(Visita.id)
            .filter(
                Visita.usuario_id == usuario_id,
                Visita.poi_id == datos.poi_id,
                Visita.estado == VisitaEstado.VALIDADA,
                Visita.created_at >= inicio_dia,
            )
            .first()
        )
        if ya_validada is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya registraste una visita validada a este POI hoy",
            )

        necesita_gps = datos.metodo_validacion in (MetodoValidacion.GPS, MetodoValidacion.MIXTA)
        necesita_qr = datos.metodo_validacion in (MetodoValidacion.QR, MetodoValidacion.MIXTA)

        distancia_metros = None
        if necesita_gps:
            distancia = self.db.execute(
                select(
                    func.ST_Distance(
                        Poi.ubicacion, func.ST_GeogFromText(datos.ubicacion_usuario)
                    )
                ).where(Poi.id == datos.poi_id)
            ).scalar_one()
            distancia_metros = float(distancia)
            limite_metros = float(poi.radio_validacion) + datos.precision_metros
            if distancia_metros > limite_metros:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Estás a {distancia_metros:.1f} m del POI; "
                        f"el máximo permitido es {limite_metros:.1f} m"
                    ),
                )

        if necesita_qr:
            if not verificar_qr_checkin_poi(str(poi.id), datos.codigo_qr):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Código QR inválido para este POI",
                )

        categoria_nombre = (
            self.db.query(CategoriaPoi.nombre)
            .filter(CategoriaPoi.id == poi.categoria_id)
            .scalar()
        )
        puntos, regla_id = self._puntos_para_visita(poi, categoria_nombre)
        try:
            visita = Visita(
                usuario_id=usuario_id,
                poi_id=datos.poi_id,
                ubicacion_usuario=func.ST_GeogFromText(datos.ubicacion_usuario) if necesita_gps else None,
                precision_metros=datos.precision_metros if necesita_gps else None,
                distancia_metros=distancia_metros,
                metodo_validacion=datos.metodo_validacion,
                estado=VisitaEstado.VALIDADA,
            )
            self.db.add(visita)
            self.db.flush()
            self.movimiento_repo.crear(
                {
                    "usuario_id": usuario_id,
                    "visita_id": visita.id,
                    "regla_id": regla_id,
                    "puntos": puntos,
                }
            )
            self.db.commit()
            self.db.refresh(visita)
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise DBError("No fue posible registrar la visita") from exc

        return VisitaOut(
            id=visita.id,
            poi_id=visita.poi_id,
            estado=visita.estado,
            distancia_metros=float(visita.distancia_metros) if visita.distancia_metros is not None else None,
            puntos_otorgados=puntos,
            created_at=visita.created_at,
        )

    def obtener_saldo(self, usuario_id: str) -> int:
        return self.puntos_repo.obtener_saldo(usuario_id)

    def listar_mis_visitas(self, usuario_id: str, skip: int, limit: int, page: int) -> PaginatedVisitasResponse:
        """Historial paginado de check-ins del usuario, más reciente primero.
        `puntos_otorgados` sale de movimientos_puntos (no vive en Visita) vía
        outerjoin por visita_id: 0 si la visita no generó movimiento."""
        rows = (
            self.db.query(Visita, Poi, func.coalesce(MovimientoPuntos.puntos, 0))
            .join(Poi, Poi.id == Visita.poi_id)
            .outerjoin(MovimientoPuntos, MovimientoPuntos.visita_id == Visita.id)
            .filter(Visita.usuario_id == usuario_id)
            .order_by(Visita.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        total = self.db.query(Visita).filter(Visita.usuario_id == usuario_id).count()

        items = [
            VisitaHistorialItem(
                id=visita.id,
                poi=VisitaPoiMini.model_validate(poi),
                estado=visita.estado,
                metodo_validacion=visita.metodo_validacion,
                distancia_metros=float(visita.distancia_metros) if visita.distancia_metros is not None else None,
                puntos_otorgados=int(puntos or 0),
                created_at=visita.created_at,
            )
            for visita, poi, puntos in rows
        ]
        return PaginatedVisitasResponse(items=items, total=total, page=page, page_size=limit)

    def _puntos_para_visita(
        self, poi: Poi, categoria_nombre: str | None
    ) -> tuple[int, UUID | None]:
        """Resuelve la regla más específica y de mayor prioridad para el POI."""
        ahora = datetime.now(timezone.utc)
        reglas = (
            self.db.query(ReglaPuntos)
            .filter(
                ReglaPuntos.activo.is_(True),
                ReglaPuntos.configuracion["evento"].astext == "VISITA",
                or_(
                    ReglaPuntos.vigencia_inicio.is_(None),
                    ReglaPuntos.vigencia_inicio <= ahora,
                ),
                or_(
                    ReglaPuntos.vigencia_fin.is_(None),
                    ReglaPuntos.vigencia_fin > ahora,
                ),
            )
            .order_by(ReglaPuntos.prioridad.desc())
            .all()
        )
        for regla in reglas:
            configuracion = regla.configuracion or {}
            poi_slug = configuracion.get("poi_slug")
            categoria = configuracion.get("categoria")
            if poi_slug is not None:
                if poi_slug != poi.slug:
                    continue
            elif categoria is not None and categoria != categoria_nombre:
                continue

            puntos = configuracion.get("puntos")
            if isinstance(puntos, int) and not isinstance(puntos, bool) and puntos > 0:
                return puntos, regla.id
        return PUNTOS_VISITA_POR_DEFECTO, None
