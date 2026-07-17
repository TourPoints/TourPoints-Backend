from typing import List

from sqlalchemy.orm import Session

from app.models.movimiento_puntos import MovimientoPuntos


class MovimientoPuntosRepository:
    """Repo del libro mayor de puntos (append-only). tipo_movimiento es una
    columna COMPUTADA (derivada de las FK), asi que no se setea a mano: basta
    con dejar canje_id lleno y el CASE la resuelve como 'CANJE'."""

    def __init__(self, db: Session):
        self.db = db

    def crear(self, datos: dict) -> MovimientoPuntos:
        movimiento = MovimientoPuntos(**datos)
        self.db.add(movimiento)
        self.db.flush()
        return movimiento

    def list_por_usuario(self, usuario_id: str, skip: int = 0, limit: int = 20) -> List[MovimientoPuntos]:
        return (
            self.db.query(MovimientoPuntos)
            .filter(MovimientoPuntos.usuario_id == usuario_id)
            .order_by(MovimientoPuntos.created_at.desc(), MovimientoPuntos.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_por_usuario(self, usuario_id: str) -> int:
        return self.db.query(MovimientoPuntos).filter(MovimientoPuntos.usuario_id == usuario_id).count()
