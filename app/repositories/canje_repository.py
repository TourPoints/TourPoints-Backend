from app.models.canje import Canje
from sqlalchemy.orm import Session


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
