from app.models.movimiento_puntos import MovimientoPuntos
from sqlalchemy.orm import Session


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
