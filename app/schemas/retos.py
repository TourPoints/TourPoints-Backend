from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.enums import RetoEstado, RetoModoRecompensa, RetoRecurrencia, RetoTipo


class RetoCreate(BaseModel):
    """Body de POST /challenges."""

    nombre: str = Field(..., min_length=1, max_length=200)
    descripcion: Optional[str] = None
    tipo: RetoTipo
    recurrencia: RetoRecurrencia = RetoRecurrencia.UNICA
    cantidad_requerida: int = Field(..., gt=0)
    recompensa_id: Optional[UUID] = None
    modo_recompensa: RetoModoRecompensa = RetoModoRecompensa.SIN_RECOMPENSA
    establecimiento_id: Optional[UUID] = Field(
        None, description="Requerido si lo propone un establecimiento (no-ADMIN); ADMIN puede omitirlo"
    )
    inicio: datetime
    fin: Optional[datetime] = None
    configuracion: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validar_coherencia(self) -> "RetoCreate":
        if self.fin is not None and self.fin <= self.inicio:
            raise ValueError("fin debe ser posterior a inicio")
        if self.modo_recompensa == RetoModoRecompensa.SIN_RECOMPENSA:
            if self.recompensa_id is not None:
                raise ValueError("recompensa_id debe ser null cuando modo_recompensa es SIN_RECOMPENSA")
        elif self.recompensa_id is None:
            raise ValueError("recompensa_id es obligatorio cuando modo_recompensa es GARANTIZADA o LIMITADA")
        return self


class RetoModeracion(BaseModel):
    estado: str


class RetoRecompensaMini(BaseModel):
    id: UUID
    nombre: str
    puntos: int

    class Config:
        from_attributes = True


class RetoListItem(BaseModel):
    id: UUID
    nombre: str
    tipo: RetoTipo
    recurrencia: RetoRecurrencia
    cantidad_requerida: int
    modo_recompensa: RetoModoRecompensa
    recompensa: Optional[RetoRecompensaMini] = None
    inicio: datetime
    fin: Optional[datetime] = None
    estado: RetoEstado
    disponible: bool


class RetoDetail(RetoListItem):
    descripcion: Optional[str] = None
    establecimiento_id: Optional[UUID] = None
    configuracion: Dict[str, Any]


class PaginatedRetosResponse(BaseModel):
    items: List[RetoListItem]
    total: int
    page: int
    page_size: int


class UsuarioRetoOut(BaseModel):
    id: UUID
    reto_id: UUID
    periodo_inicio: datetime
    periodo_fin: Optional[datetime] = None
    numero_intento: int
    progreso: Dict[str, Any]
    porcentaje: int
    estado: RetoEstado
    fecha_completado: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedUsuarioRetosResponse(BaseModel):
    items: List[UsuarioRetoOut]
    total: int
    page: int
    page_size: int


class RetoProgressUpdate(BaseModel):
    """Body de POST /challenges/{id}/progress. No estaba en el diseño original:
    sin esto, nada podía mover `progreso`/`cantidad` hacia adelante."""

    incremento: int = Field(1, gt=0)
    detalle: Optional[str] = Field(None, description="Identificador libre de qué generó el avance (ej. un poi_id)")


class SesionRetoCreate(BaseModel):
    usuario_reto_id: UUID


class SesionRetoOut(BaseModel):
    id: UUID
    usuario_reto_id: UUID
    inicio: datetime
    fin: Optional[datetime] = None
    estado: RetoEstado

    class Config:
        from_attributes = True


class SesionRetoFinalizar(BaseModel):
    estado: str = "FINALIZADO"


class RachaOut(BaseModel):
    racha_actual: int
    racha_maxima: int


class InsigniaMini(BaseModel):
    codigo: str
    nombre: str
    icono: Optional[str] = None

    class Config:
        from_attributes = True


class InsigniaAlcanzadaOut(BaseModel):
    insignia: InsigniaMini
    recompensa_otorgada: bool
    created_at: datetime


class PaginatedInsigniasResponse(BaseModel):
    items: List[InsigniaAlcanzadaOut]
    total: int
    page: int
    page_size: int
