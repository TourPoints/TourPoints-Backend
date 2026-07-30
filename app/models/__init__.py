"""Importar este paquete registra todos los modelos en Base.metadata
(necesario para que Alembic los detecte en autogenerate)."""

from app.models.canje import Canje
from app.models.comercial import Compra, Establecimiento, EstablecimientoUsuario, Promocion
from app.models.gamificacion import (
    HitoRacha,
    HitoRachaAlcanzado,
    Insignia,
    RachaReto,
    ReglaPuntos,
    Recompensa,
    Reto,
    SesionReto,
    UsuarioReto,
)
from app.models.ia import ConversacionIa
from app.models.movimiento_puntos import MovimientoPuntos
from app.models.poi import CategoriaPoi, Poi, PoiModeracionLog, PoiRelacion, TipoRelacionPoi
from app.models.social import Calificacion, Comentario, Favorito, ImagenPoi
from app.models.ubicacion import Ciudad, Departamento, Pais
from app.models.usuario import Rol, Usuario
from app.models.visita import Visita

__all__ = [
    "Canje",
    "Compra",
    "Establecimiento",
    "EstablecimientoUsuario",
    "Promocion",
    "HitoRacha",
    "HitoRachaAlcanzado",
    "Insignia",
    "RachaReto",
    "ReglaPuntos",
    "Recompensa",
    "Reto",
    "SesionReto",
    "UsuarioReto",
    "ConversacionIa",
    "MovimientoPuntos",
    "CategoriaPoi",
    "Poi",
    "PoiModeracionLog",
    "PoiRelacion",
    "TipoRelacionPoi",
    "Calificacion",
    "Comentario",
    "Favorito",
    "ImagenPoi",
    "Ciudad",
    "Departamento",
    "Pais",
    "Rol",
    "Usuario",
    "Visita",
]
