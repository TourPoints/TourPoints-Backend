from typing import List, Optional
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.gamificacion import (
    HitoRacha,
    HitoRachaAlcanzado,
    Insignia,
    RachaReto,
    Reto,
    SesionReto,
    UsuarioReto,
)


class RetoRepository:
    def __init__(self, db: Session):
        self.db = db

    # --- Retos (plantillas) ---

    def get_by_id(self, id: str) -> Optional[Reto]:
        return self.db.query(Reto).filter(Reto.id == id).first()

    def _filtered_query(self, **filters):
        query = self.db.query(Reto)
        if filters.get("tipo"):
            query = query.filter(Reto.tipo == filters["tipo"])
        if filters.get("establecimiento_id"):
            query = query.filter(Reto.establecimiento_id == filters["establecimiento_id"])
        estado = filters.get("estado", "ACTIVO")
        if estado:
            query = query.filter(Reto.estado == estado)
        return query

    def list(self, skip: int, limit: int, **filters) -> List[Reto]:
        return self._filtered_query(**filters).order_by(Reto.inicio.desc()).offset(skip).limit(limit).all()

    def count(self, **filters) -> int:
        return self._filtered_query(**filters).count()

    def create(self, datos: dict) -> Reto:
        reto = Reto(**datos)
        self.db.add(reto)
        self.db.flush()
        return reto

    def actualizar_estado(self, reto: Reto, estado: str) -> Reto:
        reto.estado = estado
        self.db.commit()
        self.db.refresh(reto)
        return reto

    # --- Intentos (usuario_retos) ---

    def get_usuario_reto_activo(self, usuario_id: str, reto_id: str, periodo_inicio: datetime) -> Optional[UsuarioReto]:
        return (
            self.db.query(UsuarioReto)
            .filter(
                UsuarioReto.usuario_id == usuario_id,
                UsuarioReto.reto_id == reto_id,
                UsuarioReto.periodo_inicio == periodo_inicio,
                UsuarioReto.estado == "ACTIVO",
            )
            .first()
        )

    def get_max_numero_intento(self, usuario_id: str, reto_id: str, periodo_inicio: datetime) -> int:
        maximo = (
            self.db.query(UsuarioReto.numero_intento)
            .filter(
                UsuarioReto.usuario_id == usuario_id,
                UsuarioReto.reto_id == reto_id,
                UsuarioReto.periodo_inicio == periodo_inicio,
            )
            .order_by(UsuarioReto.numero_intento.desc())
            .first()
        )
        return maximo[0] if maximo else 0

    def crear_usuario_reto(self, datos: dict) -> UsuarioReto:
        usuario_reto = UsuarioReto(**datos)
        self.db.add(usuario_reto)
        self.db.flush()  # dispara trg_reservar_o_bloquear_reto
        return usuario_reto

    def get_usuario_reto(self, id: str) -> Optional[UsuarioReto]:
        return self.db.query(UsuarioReto).filter(UsuarioReto.id == id).first()

    def list_mis_usuario_retos(self, usuario_id: str, skip: int, limit: int) -> List[UsuarioReto]:
        return (
            self.db.query(UsuarioReto)
            .filter(UsuarioReto.usuario_id == usuario_id)
            .order_by(UsuarioReto.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_mis_usuario_retos(self, usuario_id: str) -> int:
        return self.db.query(UsuarioReto).filter(UsuarioReto.usuario_id == usuario_id).count()

    def get_mi_intento_activo(self, usuario_id: str, reto_id: str) -> Optional[UsuarioReto]:
        return (
            self.db.query(UsuarioReto)
            .filter(
                UsuarioReto.usuario_id == usuario_id,
                UsuarioReto.reto_id == reto_id,
                UsuarioReto.estado == "ACTIVO",
            )
            .order_by(UsuarioReto.created_at.desc())
            .first()
        )

    def actualizar_usuario_reto(self, usuario_reto: UsuarioReto, cambios: dict) -> UsuarioReto:
        for field, value in cambios.items():
            if hasattr(usuario_reto, field):
                setattr(usuario_reto, field, value)
        self.db.commit()  # dispara trg_liberar_reserva_si_no_completa si aplica (ACTIVO->CANCELADO)
        self.db.refresh(usuario_reto)
        return usuario_reto

    # --- Rachas ---

    def get_racha(self, usuario_id: str, reto_id: str) -> Optional[RachaReto]:
        return (
            self.db.query(RachaReto)
            .filter(RachaReto.usuario_id == usuario_id, RachaReto.reto_id == reto_id)
            .first()
        )

    def crear_racha(self, usuario_id: str, reto_id: str) -> RachaReto:
        racha = RachaReto(usuario_id=usuario_id, reto_id=reto_id)
        self.db.add(racha)
        self.db.flush()
        return racha

    def guardar_racha(self, racha: RachaReto) -> RachaReto:
        self.db.flush()
        return racha

    # --- Hitos ---

    def list_hitos_reto(self, reto_id: str) -> List[HitoRacha]:
        return self.db.query(HitoRacha).filter(HitoRacha.reto_id == reto_id).order_by(HitoRacha.racha_requerida).all()

    def crear_hito_alcanzado(self, datos: dict) -> HitoRachaAlcanzado:
        alcanzado = HitoRachaAlcanzado(**datos)
        self.db.add(alcanzado)
        self.db.flush()  # dispara trg_otorgar_recompensa_hito
        return alcanzado

    def list_insignias_usuario(self, usuario_id: str, skip: int, limit: int):
        return (
            self.db.query(HitoRachaAlcanzado, Insignia)
            .join(HitoRacha, HitoRacha.id == HitoRachaAlcanzado.hito_id)
            .join(Insignia, Insignia.id == HitoRacha.insignia_id)
            .filter(HitoRachaAlcanzado.usuario_id == usuario_id)
            .order_by(HitoRachaAlcanzado.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_insignias_usuario(self, usuario_id: str) -> int:
        return (
            self.db.query(HitoRachaAlcanzado)
            .join(HitoRacha, HitoRacha.id == HitoRachaAlcanzado.hito_id)
            .filter(HitoRachaAlcanzado.usuario_id == usuario_id, HitoRacha.insignia_id.isnot(None))
            .count()
        )

    # --- Sesiones (RECORRIDO) ---

    def crear_sesion(self, datos: dict) -> SesionReto:
        sesion = SesionReto(**datos)
        self.db.add(sesion)
        self.db.commit()
        self.db.refresh(sesion)
        return sesion

    def get_sesion(self, id: str) -> Optional[SesionReto]:
        return self.db.query(SesionReto).filter(SesionReto.id == id).first()

    def finalizar_sesion(self, sesion: SesionReto, estado: str, fin: datetime) -> SesionReto:
        sesion.estado = estado
        sesion.fin = fin
        self.db.commit()
        self.db.refresh(sesion)
        return sesion
