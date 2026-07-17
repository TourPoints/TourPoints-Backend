from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import TipoMovimientoPuntos


class MovimientoPuntoOut(BaseModel):
    id: int
    tipo_movimiento: TipoMovimientoPuntos
    referencia_id: Optional[UUID] = None
    puntos: int
    created_at: datetime


class PaginatedMovimientosResponse(BaseModel):
    items: List[MovimientoPuntoOut]
    total: int
    page: int
    page_size: int
