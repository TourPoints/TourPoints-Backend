from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import PoiEstado
from app.schemas.social import UsuarioMini


class RecompensaCreate(BaseModel):
    """Body for POST /rewards. No status field: the service sets it (APROBADO)."""

    poi_id: Optional[UUID] = Field(
        None, description="Associated commercial partner; null if it doesn't depend on a POI"
    )
    nombre: str = Field(..., min_length=1, max_length=200)
    descripcion: Optional[str] = None
    stock: int = Field(..., ge=0)
    puntos: int = Field(..., gt=0)


class RecompensaUpdate(BaseModel):
    """Body for PATCH /rewards/{id}. All fields optional; estado is included to
    pause (INACTIVO) without deleting."""

    nombre: Optional[str] = Field(None, min_length=1, max_length=200)
    descripcion: Optional[str] = None
    stock: Optional[int] = Field(None, ge=0)
    puntos: Optional[int] = Field(None, gt=0)
    estado: Optional[PoiEstado] = None


class RecompensaOut(BaseModel):
    """List/detail output. `disponible` is added by the service
    (it doesn't live in the ORM), same pattern as distancia_metros in POI."""

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


class PaginatedRecompensasResponse(BaseModel):
    items: list[RecompensaOut]
    total: int
    page: int
    page_size: int


class CanjeOut(BaseModel):
    """Redemption output. Reward embedded as RecompensaOut."""

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
    """Body for POST /redemptions/validate-qr."""

    codigo_qr: str = Field(..., min_length=1)


class CanjeValidacionOut(BaseModel):
    """Output of POST /redemptions/validate-qr. Includes `usuario` (who the
    redemption belongs to) and `fecha_redencion` — CanjeOut omits them because the
    owner already knows who they are; here it's needed by the staff scanning the QR."""

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
