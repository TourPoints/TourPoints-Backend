from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.comercial import Compra, Establecimiento, EstablecimientoUsuario, Promocion


class ComercialRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- Establecimientos ---

    def get_establecimiento(self, id: str) -> Optional[Establecimiento]:
        return self.db.query(Establecimiento).filter(Establecimiento.id == id).first()

    def get_establecimiento_by_poi(self, poi_id: str) -> Optional[Establecimiento]:
        return self.db.query(Establecimiento).filter(Establecimiento.poi_id == poi_id).first()

    def crear_establecimiento(self, datos: dict) -> Establecimiento:
        establecimiento = Establecimiento(**datos)
        self.db.add(establecimiento)
        self.db.flush()
        return establecimiento

    def agregar_staff(self, establecimiento_id: str, usuario_id: str, cargo: str) -> EstablecimientoUsuario:
        vinculo = EstablecimientoUsuario(establecimiento_id=establecimiento_id, usuario_id=usuario_id, cargo=cargo)
        self.db.add(vinculo)
        self.db.flush()
        return vinculo

    def es_staff(self, establecimiento_id: str, usuario_id: str) -> bool:
        return (
            self.db.query(EstablecimientoUsuario)
            .filter(
                EstablecimientoUsuario.establecimiento_id == establecimiento_id,
                EstablecimientoUsuario.usuario_id == usuario_id,
            )
            .first()
            is not None
        )

    def list_mis_establecimientos(
        self, usuario_id: str, skip: int, limit: int
    ) -> List[Tuple[Establecimiento, str]]:
        return (
            self.db.query(Establecimiento, EstablecimientoUsuario.cargo)
            .join(EstablecimientoUsuario, EstablecimientoUsuario.establecimiento_id == Establecimiento.id)
            .filter(EstablecimientoUsuario.usuario_id == usuario_id)
            .order_by(Establecimiento.razon_social)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_mis_establecimientos(self, usuario_id: str) -> int:
        return (
            self.db.query(EstablecimientoUsuario)
            .filter(EstablecimientoUsuario.usuario_id == usuario_id)
            .count()
        )

    def actualizar_estado_establecimiento(self, establecimiento: Establecimiento, estado: str) -> Establecimiento:
        establecimiento.estado = estado
        self.db.commit()
        self.db.refresh(establecimiento)
        return establecimiento

    # --- Compras ---

    def crear_compra(self, datos: dict) -> Compra:
        compra = Compra(**datos)
        self.db.add(compra)
        self.db.flush()
        return compra

    def get_compra(self, id: str) -> Optional[Compra]:
        return self.db.query(Compra).filter(Compra.id == id).first()

    def cancelar_compra(self, compra: Compra, cancelada_por: str) -> Compra:
        compra.estado = "CANCELADA"
        compra.cancelada_por = cancelada_por
        compra.fecha_cancelacion = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(compra)
        return compra

    # --- Promociones ---

    def crear_promocion(self, datos: dict) -> Promocion:
        promocion = Promocion(**datos)
        self.db.add(promocion)
        self.db.flush()
        return promocion

    def get_promocion(self, id: str) -> Optional[Promocion]:
        return self.db.query(Promocion).filter(Promocion.id == id).first()

    def actualizar_estado_promocion(self, promocion: Promocion, estado: str) -> Promocion:
        promocion.estado = estado
        self.db.commit()
        self.db.refresh(promocion)
        return promocion

    def list_promociones_vigentes_por_poi(self, poi_id: str, skip: int, limit: int) -> List[Promocion]:
        ahora = datetime.now(timezone.utc)
        return (
            self.db.query(Promocion)
            .join(Establecimiento, Establecimiento.id == Promocion.establecimiento_id)
            .filter(
                Establecimiento.poi_id == poi_id,
                Promocion.estado == "APROBADO",
                Promocion.inicio <= ahora,
                Promocion.fin > ahora,
            )
            .order_by(Promocion.inicio.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_promociones_vigentes_por_poi(self, poi_id: str) -> int:
        ahora = datetime.now(timezone.utc)
        return (
            self.db.query(Promocion)
            .join(Establecimiento, Establecimiento.id == Promocion.establecimiento_id)
            .filter(
                Establecimiento.poi_id == poi_id,
                Promocion.estado == "APROBADO",
                Promocion.inicio <= ahora,
                Promocion.fin > ahora,
            )
            .count()
        )
