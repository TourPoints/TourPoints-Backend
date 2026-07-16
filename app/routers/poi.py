from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.enums import PoiEstado
from app.models.poi import Poi
from app.models.usuario import Usuario
from app.schemas.poi_visita import PoiParaVisitaOut

router = APIRouter()


@router.get("", response_model=List[PoiParaVisitaOut])
def listar_pois_para_visita(
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Lista POIs aprobados y su ubicación para poder registrar una visita GPS."""
    rows = db.execute(
        select(
            Poi.id,
            Poi.nombre,
            func.ST_AsText(Poi.ubicacion).label("ubicacion"),
            Poi.radio_validacion,
        )
        .where(Poi.estado == PoiEstado.APROBADO)
        .limit(limit)
    ).all()
    return [
        PoiParaVisitaOut(
            id=row.id,
            nombre=row.nombre,
            ubicacion=row.ubicacion,
            radio_validacion=row.radio_validacion,
        )
        for row in rows
    ]
