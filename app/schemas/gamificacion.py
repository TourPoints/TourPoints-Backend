from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import PoiEstado
from app.schemas.social import UsuarioMini


class RecompensaCreate(BaseModel):
    """Body de POST /rewards. Sin estado: lo fija el service (APROBADO)."""

    poi_id: Optional[UUID] = Field(
        None, description="Aliado comercial asociado; null si no depende de un POI"
    )
    nombre: str = Field(..., min_length=1, max_length=200)
    descripcion: Optional[str] = None
    stock: int = Field(..., ge=0)
    puntos: int = Field(..., gt=0)


class RecompensaUpdate(BaseModel):
    """Body de PATCH /rewards/{id}. Todos opcionales; estado incluido para
    pausar (INACTIVO) sin borrar."""

    nombre: Optional[str] = Field(None, min_length=1, max_length=200)
    descripcion: Optional[str] = None
    stock: Optional[int] = Field(None, ge=0)
    puntos: Optional[int] = Field(None, gt=0)
    estado: Optional[PoiEstado] = None


class RecompensaOut(BaseModel):
    """Salida de listar/detalle. `disponible` lo agrega el service
    (no vive en el ORM), mismo patron que distancia_metros en POI."""

    id: UUID
    poi_id: Optional[UUID] = None
    nombre: str
    descripcion: Optional[str] = None
    stock: int
    puntos: int
    estado: PoiEstado
    disponible: bool

    class Config:
        from_attributes = True


class CanjeOut(BaseModel):
    """Salida del canje. Recompensa embebida como RecompensaOut."""

    id: UUID
    recompensa: RecompensaOut
    origen: str
    codigo_qr: str
    estado: str
    fecha_expira: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedCanjesResponse(BaseModel):
    items: list[CanjeOut]
    total: int
    page: int
    page_size: int


class CanjeValidateQR(BaseModel):
    """Body de POST /redemptions/validate-qr."""

    codigo_qr: str = Field(..., min_length=1)


class CanjeValidacionOut(BaseModel):
    """Salida de POST /redemptions/validate-qr. Incluye `usuario` (a quién
    pertenece el canje) y `fecha_redencion` — CanjeOut no los trae porque el
    dueño ya sabe quién es; aquí lo necesita el staff que escanea el QR."""

    id: UUID
    recompensa: RecompensaOut
    usuario: UsuarioMini
    origen: str
    estado: str
    fecha_expira: Optional[datetime] = None
    fecha_redencion: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
