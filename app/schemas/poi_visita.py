from uuid import UUID

from pydantic import BaseModel


class PoiParaVisitaOut(BaseModel):
    id: UUID
    nombre: str
    ubicacion: str
    radio_validacion: int
