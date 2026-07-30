from geoalchemy2 import Geography
from sqlalchemy import Column, ForeignKey, Index, Numeric, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import (
    MetodoValidacion,
    VisitaEstado,
    metodo_validacion_enum,
    visita_estado_enum,
)


class Visita(Base):
    __tablename__ = "visitas"
    __table_args__ = (
        Index("idx_visitas_ubicacion", "ubicacion_usuario", postgresql_using="gist"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    poi_id = Column(UUID(as_uuid=True), ForeignKey("poi.id"), nullable=False)
    ubicacion_usuario = Column(Geography(geometry_type="POINT", srid=4326, spatial_index=False))
    precision_metros = Column(Numeric(6, 2))
    distancia_metros = Column(Numeric(8, 2))
    metodo_validacion: Mapped[MetodoValidacion] = mapped_column(metodo_validacion_enum, nullable=False)
    estado: Mapped[VisitaEstado] = mapped_column(
        visita_estado_enum,
        nullable=False,
        server_default=text("'PENDIENTE'"),
    )
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
