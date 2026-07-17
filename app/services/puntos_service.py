from typing import List

from sqlalchemy.orm import Session

from app.repositories.movimiento_puntos_repository import MovimientoPuntosRepository
from app.repositories.puntos_repository import PuntosRepository
from app.schemas.puntos import SaldoOut, MovimientoOut


class PuntosService:
    """Servicio de lectura de puntos. Encapsula PuntosRepository (saldo)
    y MovimientoPuntosRepository (historial). Sigue el molde de RecompensasService:
    recibe db y construye sus propios repos internamente."""

    def __init__(self, db: Session):
        self.db = db
        self.puntos_repo = PuntosRepository(db)
        self.movimiento_repo = MovimientoPuntosRepository(db)

    def obtener_saldo(self, usuario_id: str) -> SaldoOut:
        saldo = self.puntos_repo.obtener_saldo(usuario_id)
        return SaldoOut(usuario_id=usuario_id, saldo=saldo)

    def listar_movimientos(
        self, usuario_id: str, limit: int = 20, offset: int = 0
    ) -> List[MovimientoOut]:
        movimientos = self.movimiento_repo.listar(
            usuario_id, limit=limit, offset=offset
        )
        return [MovimientoOut.model_validate(m) for m in movimientos]