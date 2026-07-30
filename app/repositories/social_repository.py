from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.social import Calificacion, Comentario, Favorito
from app.models.usuario import Usuario


class SocialRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- Calificaciones ---

    def get_calificacion(self, usuario_id: str, poi_id: str) -> Optional[Calificacion]:
        return (
            self.db.query(Calificacion)
            .filter(Calificacion.usuario_id == usuario_id, Calificacion.poi_id == poi_id)
            .first()
        )

    def upsert_calificacion(self, usuario_id: str, poi_id: str, valor: int) -> Calificacion:
        calificacion = self.get_calificacion(usuario_id, poi_id)
        if calificacion:
            calificacion.calificacion = valor
        else:
            calificacion = Calificacion(usuario_id=usuario_id, poi_id=poi_id, calificacion=valor)
            self.db.add(calificacion)
        self.db.commit()
        self.db.refresh(calificacion)
        return calificacion

    def delete_calificacion(self, usuario_id: str, poi_id: str) -> bool:
        calificacion = self.get_calificacion(usuario_id, poi_id)
        if not calificacion:
            return False
        self.db.delete(calificacion)
        self.db.commit()
        return True

    def list_calificaciones(self, poi_id: str, skip: int, limit: int) -> List[Tuple[Calificacion, Usuario]]:
        return (
            self.db.query(Calificacion, Usuario)
            .join(Usuario, Usuario.id == Calificacion.usuario_id)
            .filter(Calificacion.poi_id == poi_id)
            .order_by(Calificacion.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_calificaciones(self, poi_id: str) -> int:
        return self.db.query(Calificacion).filter(Calificacion.poi_id == poi_id).count()

    def resumen_calificaciones(self, poi_id: str) -> Tuple[float, int, dict]:
        promedio, total = (
            self.db.query(func.avg(Calificacion.calificacion), func.count(Calificacion.id))
            .filter(Calificacion.poi_id == poi_id)
            .one()
        )
        filas = (
            self.db.query(Calificacion.calificacion, func.count(Calificacion.id))
            .filter(Calificacion.poi_id == poi_id)
            .group_by(Calificacion.calificacion)
            .all()
        )
        distribucion = {str(v): 0 for v in range(1, 6)}
        for valor, cantidad in filas:
            distribucion[str(valor)] = cantidad
        return (float(promedio) if promedio is not None else 0.0, total or 0, distribucion)

    # --- Comentarios ---

    def create_comentario(self, usuario_id: str, poi_id: str, contenido: str) -> Comentario:
        comentario = Comentario(usuario_id=usuario_id, poi_id=poi_id, contenido=contenido)
        self.db.add(comentario)
        self.db.commit()
        self.db.refresh(comentario)
        return comentario

    def get_comentario(self, id: int) -> Optional[Comentario]:
        return self.db.query(Comentario).filter(Comentario.id == id).first()

    def get_usuario(self, usuario_id: str) -> Optional[Usuario]:
        return self.db.query(Usuario).filter(Usuario.id == usuario_id).first()

    def list_comentarios(self, poi_id: str, skip: int, limit: int, estado: str) -> List[Tuple[Comentario, Usuario]]:
        return (
            self.db.query(Comentario, Usuario)
            .join(Usuario, Usuario.id == Comentario.usuario_id)
            .filter(Comentario.poi_id == poi_id, Comentario.estado == estado)
            .order_by(Comentario.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_comentarios(self, poi_id: str, estado: str) -> int:
        return self.db.query(Comentario).filter(Comentario.poi_id == poi_id, Comentario.estado == estado).count()

    def moderar_comentario(self, id: str, estado: str) -> Comentario:
        comentario = self.get_comentario(id)
        comentario.estado = estado
        self.db.commit()
        self.db.refresh(comentario)
        return comentario

    def delete_comentario(self, id: str) -> None:
        comentario = self.get_comentario(id)
        self.db.delete(comentario)
        self.db.commit()

    # --- Favoritos ---

    def is_favorito(self, usuario_id: str, poi_id: str) -> bool:
        return (
            self.db.query(Favorito).filter(Favorito.usuario_id == usuario_id, Favorito.poi_id == poi_id).first()
            is not None
        )

    def add_favorito(self, usuario_id: str, poi_id: str) -> Favorito:
        favorito = Favorito(usuario_id=usuario_id, poi_id=poi_id)
        self.db.add(favorito)
        self.db.commit()
        self.db.refresh(favorito)
        return favorito

    def remove_favorito(self, usuario_id: str, poi_id: str) -> bool:
        favorito = (
            self.db.query(Favorito).filter(Favorito.usuario_id == usuario_id, Favorito.poi_id == poi_id).first()
        )
        if not favorito:
            return False
        self.db.delete(favorito)
        self.db.commit()
        return True

    def list_favoritos_poi_ids(self, usuario_id: str, skip: int, limit: int) -> List[str]:
        rows = (
            self.db.query(Favorito.poi_id)
            .filter(Favorito.usuario_id == usuario_id)
            .order_by(Favorito.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return [row[0] for row in rows]

    def count_favoritos(self, usuario_id: str) -> int:
        return self.db.query(Favorito).filter(Favorito.usuario_id == usuario_id).count()
