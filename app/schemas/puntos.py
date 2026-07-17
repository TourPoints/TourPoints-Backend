from datetime import datetime
from typing import List
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import TipoMovimientoPuntos


class SaldoOut(BaseModel):
    """GET /api/v1/points/me/saldo — saldo actual de puntos del usuario."""

    usuario_id: str
    saldo: int


class MovimientoOut(BaseModel):
    """Un movimiento individual del libro mayor de puntos."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo_movimiento: TipoMovimientoPuntos
    puntos: int
    created_at: datetime


# GET /api/v1/points/me/movimientos devuelve List[MovimientoOut] (lista plana).
# La paginacion (limit/offset) son query params del endpoint, no parte del body.