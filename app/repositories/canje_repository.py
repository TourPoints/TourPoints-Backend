from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.canje import Canje


class CanjeRepository:
    """Repo de canjes. El trigger trg_descontar_stock_canje descuenta stock
    al insertar; si stock agotado, el trigger RAISE EXCEPTION (el service lo
    captura y traduce a SinStockError)."""

    def __init__(self, db: Session):
        self.db = db

    def crear(self, datos: dict) -> Canje:
        canje = Canje(**datos)
        self.db.add(canje)
        self.db.flush()  # dispara el trigger; sin commit (lo hace el service)
        return canje

    def obtener_por_id(self, id: str) -> Optional[Canje]:
        return self.db.query(Canje).filter(Canje.id == id).first()

    def obtener_por_codigo_qr(self, codigo_qr: str) -> Optional[Canje]:
        return self.db.query(Canje).filter(Canje.codigo_qr == codigo_qr).first()

    def listar_por_usuario(self, usuario_id: str, skip: int = 0, limit: int = 20) -> List[Canje]:
        return (
            self.db.query(Canje)
            .filter(Canje.usuario_id == usuario_id)
            .order_by(Canje.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def contar_por_usuario(self, usuario_id: str) -> int:
        return self.db.query(Canje).filter(Canje.usuario_id == usuario_id).count()

    def actualizar(self, canje: Canje, cambios: dict) -> Canje:
        for field, value in cambios.items():
            if hasattr(canje, field):
                setattr(canje, field, value)
        self.db.flush()
        return canje
