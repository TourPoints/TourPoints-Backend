from sqlalchemy import text
from sqlalchemy.orm import Session


class PuntosRepository:
    """Repo de puntos compartido con el futuro modulo de Puntos. Lee el saldo
    de la vista saldo_puntos_usuario (Core con sqlalchemy.text, no ORM) para
    no duplicar el SUM(puntos). Ver comentario en app/models/movimiento_puntos.py."""

    def __init__(self, db: Session):
        self.db = db

    def obtener_saldo(self, usuario_id: str) -> int:
        row = self.db.execute(
            text("SELECT saldo FROM saldo_puntos_usuario WHERE usuario_id = :uid"),
            {"uid": usuario_id},
        ).first()
        return int(row.saldo) if row else 0
