from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.gamificacion import Recompensa


class RecompensaRepository:
    """Repo de recompensas. El service maneja el commit; aca solo add/flush
    en el crear. Patron = usuario_repository (inyecta db en __init__)."""

    def __init__(self, db: Session):
        self.db = db

    def crear(self, recompensa: Recompensa) -> Recompensa:
        self.db.add(recompensa)
        self.db.flush()  # sin commit; lo hace el service
        return recompensa

    def listar(
        self,
        poi_id: Optional[str] = None,
        estado: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Recompensa]:
        query = self.db.query(Recompensa)
        if poi_id is not None:
            query = query.filter(Recompensa.poi_id == poi_id)
        if estado is not None:
            query = query.filter(Recompensa.estado == estado)
        return query.offset(offset).limit(limit).all()

    def obtener_por_id(self, id: str) -> Optional[Recompensa]:
        return self.db.query(Recompensa).filter(Recompensa.id == id).first()

    def obtener_con_lock(self, id: str) -> Optional[Recompensa]:
        return (
            self.db.query(Recompensa)
            .filter(Recompensa.id == id)
            .with_for_update()
            .first()
        )

    def actualizar(self, recompensa: Recompensa, cambios: dict) -> Recompensa:
        for field, value in cambios.items():
            if hasattr(recompensa, field):
                setattr(recompensa, field, value)
        self.db.flush()
        return recompensa
