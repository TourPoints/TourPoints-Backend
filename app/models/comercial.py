from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    TIMESTAMP,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import (
    CompraEstado,
    Moneda,
    PoiEstado,
    compra_estado_enum,
    moneda_enum,
    poi_estado_enum,
)


class Establecimiento(Base):
    __tablename__ = "establecimientos"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    poi_id = Column(UUID(as_uuid=True), ForeignKey("poi.id"), unique=True, nullable=False)
    nit = Column(String(30), unique=True)
    razon_social = Column(String(200), nullable=False)
    tipo_negocio = Column(String(80))
    fecha_afiliacion = Column(Date, nullable=False, server_default=text("CURRENT_DATE"))
    estado: Mapped[PoiEstado] = mapped_column(
        poi_estado_enum,
        nullable=False,
        server_default=text("'PENDIENTE'"),
    )
    metadata_ = Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))


class EstablecimientoUsuario(Base):
    __tablename__ = "establecimiento_usuarios"
    __table_args__ = (Index("idx_establecimiento_usuarios_usuario", "usuario_id"),)

    establecimiento_id = Column(
        UUID(as_uuid=True),
        ForeignKey("establecimientos.id", ondelete="CASCADE"),
        primary_key=True,
    )
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), primary_key=True)
    cargo = Column(String(80))


class Compra(Base):
    __tablename__ = "compras"
    __table_args__ = (
        CheckConstraint("valor > 0"),
        CheckConstraint(
            "(estado = 'CANCELADA' AND cancelada_por IS NOT NULL AND fecha_cancelacion IS NOT NULL) "
            "OR (estado <> 'CANCELADA' AND cancelada_por IS NULL AND fecha_cancelacion IS NULL)"
        ),
        Index("idx_compras_establecimiento", "establecimiento_id"),
        Index("idx_compras_usuario", "usuario_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    establecimiento_id = Column(UUID(as_uuid=True), ForeignKey("establecimientos.id"), nullable=False)
    valor = Column(Numeric(12, 2), nullable=False)
    moneda: Mapped[Moneda] = mapped_column(moneda_enum, nullable=False, server_default=text("'COP'"))
    codigo_transaccion = Column(String(60), unique=True)
    estado: Mapped[CompraEstado] = mapped_column(
        compra_estado_enum,
        nullable=False,
        server_default=text("'REGISTRADA'"),
    )
    cancelada_por = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    fecha_cancelacion = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class Promocion(Base):
    __tablename__ = "promociones"
    __table_args__ = (CheckConstraint("fin > inicio"),)

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    establecimiento_id = Column(UUID(as_uuid=True), ForeignKey("establecimientos.id"), nullable=False)
    titulo = Column(String(200), nullable=False)
    descripcion = Column(Text)
    inicio = Column(TIMESTAMP(timezone=True), nullable=False)
    fin = Column(TIMESTAMP(timezone=True), nullable=False)
    estado: Mapped[PoiEstado] = mapped_column(
        poi_estado_enum,
        nullable=False,
        server_default=text("'PENDIENTE'"),
    )
