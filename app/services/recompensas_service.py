from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    DBError,
    PuntosInsuficientesError,
    RecordNotFoundError,
    SinStockError,
)
from app.models.gamificacion import Recompensa
from app.models.poi import Poi
from app.repositories.canje_repository import CanjeRepository
from app.repositories.movimiento_puntos_repository import MovimientoPuntosRepository
from app.repositories.puntos_repository import PuntosRepository
from app.repositories.recompensa_repository import RecompensaRepository
from app.schemas.gamificacion import (
    CanjeOut,
    RecompensaCreate,
    RecompensaOut,
    RecompensaUpdate,
)
from app.utils.qr import generar_qr_canje

# Vigencia de un canje una vez emitido.
VIGENCIA_CANJE_DIAS = 30


def _to_out(recompensa: Recompensa) -> RecompensaOut:
    """Arma RecompensaOut calculando `disponible` (no vive en el ORM)."""
    data = {c: getattr(recompensa, c) for c in RecompensaOut.model_fields}
    data["disponible"] = recompensa.stock > 0
    return RecompensaOut.model_validate(data)


class RecompensasService:
    def __init__(self, db: Session):
        self.db = db
        self.recompensa_repo = RecompensaRepository(db)
        self.canje_repo = CanjeRepository(db)
        self.movimiento_repo = MovimientoPuntosRepository(db)
        self.puntos_repo = PuntosRepository(db)

    def crear(self, datos: RecompensaCreate) -> RecompensaOut:
        """Crea una recompensa en estado APROBADO (fijo, no viene del body).
        Si trae poi_id, valida que el POI exista."""
        if datos.poi_id is not None:
            poi = self.db.query(Poi).filter(Poi.id == datos.poi_id).first()
            if poi is None:
                raise RecordNotFoundError(f"POI with id {datos.poi_id} not found")

        recompensa = Recompensa(
            poi_id=datos.poi_id,
            nombre=datos.nombre,
            descripcion=datos.descripcion,
            stock=datos.stock,
            puntos=datos.puntos,
            estado="APROBADO",
        )
        self.recompensa_repo.crear(recompensa)
        self.db.commit()
        self.db.refresh(recompensa)
        return _to_out(recompensa)

    def actualizar(self, id: str, cambios: RecompensaUpdate) -> RecompensaOut:
        """PATCH parcial sobre la recompensa."""
        recompensa = self.recompensa_repo.obtener_por_id(id)
        if recompensa is None:
            raise RecordNotFoundError(f"Recompensa with id {id} not found")

        update_data = cambios.model_dump(exclude_unset=True)
        if update_data:
            self.recompensa_repo.actualizar(recompensa, update_data)
            self.db.commit()
            self.db.refresh(recompensa)
        return _to_out(recompensa)

    def listar(
        self,
        poi_id: Optional[str] = None,
        estado: Optional[str] = None,
        solo_aprobado: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[RecompensaOut]:
        """Lista recompensas. `solo_aprobado=True` fuerza estado=APROBADO
        para usuarios comunes (ignora el param estado si vino)."""
        if solo_aprobado:
            estado = "APROBADO"
        recompensas = self.recompensa_repo.listar(
            poi_id=poi_id, estado=estado, limit=limit, offset=offset
        )
        return [_to_out(r) for r in recompensas]

    def obtener(self, id: str, solo_aprobado: bool = True) -> RecompensaOut:
        recompensa = self.recompensa_repo.obtener_por_id(id)
        if recompensa is None:
            raise RecordNotFoundError(f"Recompensa with id {id} not found")
        if solo_aprobado and recompensa.estado != "APROBADO":
            # Una recompensa no publicada "no existe" para el usuario comun.
            raise RecordNotFoundError(f"Recompensa with id {id} not found")
        return _to_out(recompensa)

    def canjear(self, usuario_id: str, recompensa_id: str) -> CanjeOut:
        """Canjea una recompensa por puntos. Orden estricto (no reordenar):
        lock por usuario_id -> recompensa con lock -> validar saldo ->
        QR/expira -> insertar canje -> insertar movimiento negativo -> commit.
        """
        # 1) Advisory lock por usuario_id: serializa TODOS los canjes de ese
        #    usuario (cualquier recompensa) para que SELECT SUM + INSERT del
        #    movimiento negativo sean atomicos respecto del saldo. El stock
        #    no se lockea aca: ya lo protege el trigger.
        self.db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:uid::text))"),
            {"uid": str(usuario_id)},
        )

        # 2) Recompensa con lock de fila. Recien aca tenemos recompensa.puntos.
        recompensa = self.recompensa_repo.obtener_con_lock(recompensa_id)
        if recompensa is None:
            raise RecordNotFoundError(f"Recompensa with id {recompensa_id} not found")
        if recompensa.estado != "APROBADO":
            raise RecordNotFoundError(f"Recompensa with id {recompensa_id} not found")
        if recompensa.stock <= 0:
            raise SinStockError()

        # 3) Validar saldo contra la vista.
        saldo = self.puntos_repo.obtener_saldo(usuario_id)
        if saldo < recompensa.puntos:
            raise PuntosInsuficientesError()

        # 4) QR + vigencia. Un unico timestamp para que created_at y
        #    fecha_expira sean consistentes entre si (no confiar en el default
        #    de la columna ni en un flush a medias).
        ahora = datetime.utcnow()
        fecha_expira = ahora + timedelta(days=VIGENCIA_CANJE_DIAS)

        # 5) Insertar el canje. codigo_qr se genera ANTES del insert (es
        #    NOT NULL y UNIQUE, y el trigger corre BEFORE INSERT). El trigger
        #    descuenta stock; si esta agotado, RAISE EXCEPTION -> la
        #    transaccion queda abortada y hay que rollbackear primero.
        codigo_qr = generar_qr_canje()
        try:
            canje = self.canje_repo.crear(
                {
                    "usuario_id": usuario_id,
                    "recompensa_id": recompensa_id,
                    "origen": "PUNTOS",
                    "codigo_qr": codigo_qr,
                    "fecha_expira": fecha_expira,
                    "estado": "PENDIENTE",
                    "created_at": ahora,
                }
            )
        except SQLAlchemyError as exc:
            self.db.rollback()
            # El trigger falla con un mensaje que menciona "agotada".
            import logging
            logging.error(f"Stock agotado en canje: {exc}")
            raise SinStockError() from exc

        # 6) Movimiento negativo (tipo_movimiento es COMPUTado a partir de
        #    canje_id, no se setea a mano).
        self.movimiento_repo.crear(
            {
                "usuario_id": usuario_id,
                "canje_id": canje.id,
                "puntos": -recompensa.puntos,
            }
        )

        # 7) Commit.
        self.db.commit()
        self.db.refresh(canje)

        return CanjeOut(
            id=canje.id,
            recompensa=_to_out(recompensa),
            origen=canje.origen,
            codigo_qr=canje.codigo_qr,
            estado=canje.estado,
            fecha_expira=canje.fecha_expira,
            created_at=canje.created_at,
        )
