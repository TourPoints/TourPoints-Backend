from geoalchemy2 import Geography
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    TIMESTAMP,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import PoiEstado, PoiFuente, poi_estado_enum, poi_fuente_enum


class CategoriaPoi(Base):
    __tablename__ = "categorias_poi"

    id = Column(SmallInteger, primary_key=True)
    nombre = Column(String(80), nullable=False)
    icono = Column(Text)
    color = Column(String(20))


class Poi(Base):
    __tablename__ = "poi"
    __table_args__ = (
        Index("idx_poi_ubicacion", "ubicacion", postgresql_using="gist"),
        Index("idx_poi_metadata", "metadata", postgresql_using="gin"),
        Index("idx_poi_horarios", "horarios", postgresql_using="gin"),
        Index("idx_poi_slug", "slug"),
        Index("idx_poi_created_at", "created_at"),
        Index("idx_poi_categoria", "categoria_id"),
        Index("idx_poi_ciudad", "ciudad_id"),
        Index("idx_poi_fuente", "fuente"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    categoria_id = Column(SmallInteger, ForeignKey("categorias_poi.id"), nullable=False)
    ciudad_id = Column(BigInteger, ForeignKey("ciudades.id"), nullable=False)
    creado_por_usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    fuente: Mapped[PoiFuente] = mapped_column(
        poi_fuente_enum,
        nullable=False,
        server_default=text("'ADMIN'"),
    )
    # profundidad en el grafo de poi_relaciones; la mantiene el trigger
    # fn_actualizar_nivel_poi (creado en la migración), no la aplicación.
    nivel = Column(SmallInteger)
    nombre = Column(String(200), nullable=False)
    slug = Column(String(200), unique=True, nullable=False)
    descripcion = Column(Text)
    direccion = Column(Text)
    ubicacion = Column(Geography(geometry_type="POINT", srid=4326, spatial_index=False), nullable=False)
    radio_validacion = Column(SmallInteger, nullable=False, server_default=text("50"))
    telefono = Column(String(30))
    correo = Column(String(120))
    sitio_web = Column(Text)
    horarios = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    metadata_ = Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    estado: Mapped[PoiEstado] = mapped_column(
        poi_estado_enum,
        nullable=False,
        server_default=text("'BORRADOR'"),
    )
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    deleted_at = Column(TIMESTAMP(timezone=True))


class PoiModeracionLog(Base):
    """Auditoría de cada cambio de estado de un POI: quién, cuándo, de qué a qué y por qué.

    Registra tanto transiciones disparadas por el dueño (enviar a revisión, reintentar
    tras rechazo) como por un ADMIN (aprobar/rechazar/activar/inactivar) — no se borra,
    es append-only, igual que poi_relaciones.
    """

    __tablename__ = "poi_moderaciones"
    __table_args__ = (Index("idx_poi_moderaciones_poi", "poi_id"),)

    id = Column(BigInteger, primary_key=True)
    poi_id = Column(UUID(as_uuid=True), ForeignKey("poi.id", ondelete="CASCADE"), nullable=False)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    estado_anterior: Mapped[PoiEstado] = mapped_column(poi_estado_enum, nullable=False)
    estado_nuevo: Mapped[PoiEstado] = mapped_column(poi_estado_enum, nullable=False)
    motivo = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class TipoRelacionPoi(Base):
    __tablename__ = "tipos_relacion_poi"

    id = Column(SmallInteger, primary_key=True)
    nombre = Column(String(50), nullable=False)
    descripcion = Column(Text)
    es_jerarquica = Column(Boolean, nullable=False, server_default=text("false"))
    es_bidireccional = Column(Boolean, nullable=False, server_default=text("false"))
    requiere_orden = Column(Boolean, nullable=False, server_default=text("false"))


class PoiRelacion(Base):
    __tablename__ = "poi_relaciones"
    __table_args__ = (
        UniqueConstraint("poi_origen_id", "poi_destino_id", "tipo_relacion_id"),
        CheckConstraint("poi_origen_id <> poi_destino_id"),
        CheckConstraint("vigencia_fin IS NULL OR vigencia_fin > vigencia_inicio"),
        Index("idx_poi_relaciones_origen", "poi_origen_id"),
        Index("idx_poi_relaciones_destino", "poi_destino_id"),
        Index("idx_poi_relaciones_activo", "activo", postgresql_where=text("activo = true")),
    )

    id = Column(BigInteger, primary_key=True)
    poi_origen_id = Column(UUID(as_uuid=True), ForeignKey("poi.id"), nullable=False)
    poi_destino_id = Column(UUID(as_uuid=True), ForeignKey("poi.id"), nullable=False)
    tipo_relacion_id = Column(SmallInteger, ForeignKey("tipos_relacion_poi.id"), nullable=False)
    orden = Column(SmallInteger)
    vigencia_inicio = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    vigencia_fin = Column(TIMESTAMP(timezone=True))
    metadata_ = Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    activo = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
