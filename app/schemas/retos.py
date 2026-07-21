from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.enums import RetoEstado, RetoModoRecompensa, RetoRecurrencia, RetoTipo


class RetoCreate(BaseModel):
    """Body for POST /challenges."""

    nombre: str = Field(..., min_length=1, max_length=200)
    descripcion: Optional[str] = None
    tipo: RetoTipo
    recurrencia: RetoRecurrencia = RetoRecurrencia.UNICA
    cantidad_requerida: int = Field(..., gt=0)
    recompensa_id: Optional[UUID] = None
    modo_recompensa: RetoModoRecompensa = RetoModoRecompensa.SIN_RECOMPENSA
    establecimiento_id: Optional[UUID] = Field(
        None, description="Required if proposed by a business (non-ADMIN); ADMIN can omit it"
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
    """Body for POST /challenges/{id}/progress. Not in the original design:
    without this, nothing could move `progreso`/`cantidad` forward."""

    incremento: int = Field(1, gt=0)
    detalle: Optional[str] = Field(None, description="Free-form identifier of what generated the progress (e.g. a poi_id)")


class SesionRetoCreate(BaseModel):
    usuario_reto_id: UUID


class SesionRetoOut(BaseModel):
    id: UUID
    usuario_reto_id: UUID
    inicio: datetime
    fin: Optional[datetime] = None
    estado: RetoEstado
    distancia_metros: Optional[float] = None

    class Config:
        from_attributes = True


class SesionRetoFinalizar(BaseModel):
    estado: str = "FINALIZADO"


class SesionPuntoCreate(BaseModel):
    """Body de POST /challenges/{id}/sessions/{session_id}/points. Un punto GPS por llamada."""

    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class SesionPuntoOut(BaseModel):
    lat: float
    lng: float
    ts: datetime


class SesionTrackOut(BaseModel):
    """Salida de GET /challenges/{id}/sessions/{session_id}/points: el track en vivo
    almacenado en Redis y la distancia acumulada hasta el momento."""

    puntos: List[SesionPuntoOut]
    distancia_metros: float


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
