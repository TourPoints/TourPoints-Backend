from sqlalchemy.orm import Session

from app.core.exceptions import DBError
from app.repositories.movimiento_puntos_repository import MovimientoPuntosRepository
from app.schemas.puntos import MovimientoPuntoOut, PaginatedMovimientosResponse


class PuntosService:
    def __init__(self, db: Session):
        self.db = db
        self.movimiento_repo = MovimientoPuntosRepository(db)

    def _referencia_id(self, movimiento):
        return movimiento.visita_id or movimiento.compra_id or movimiento.usuario_reto_id or movimiento.canje_id

    def listar_mis_movimientos(self, usuario_id: str, skip: int, limit: int, page: int) -> PaginatedMovimientosResponse:
        try:
            movimientos = self.movimiento_repo.list_por_usuario(usuario_id, skip=skip, limit=limit)
            total = self.movimiento_repo.count_por_usuario(usuario_id)
            items = [
                MovimientoPuntoOut(
                    id=m.id,
                    tipo_movimiento=m.tipo_movimiento,
                    referencia_id=self._referencia_id(m),
                    puntos=m.puntos,
                    created_at=m.created_at,
                )
                for m in movimientos
            ]
            return PaginatedMovimientosResponse(items=items, total=total, page=page, page_size=limit)
        except Exception as exc:
            raise DBError(f"List movimientos failed: {str(exc)}") from exc
