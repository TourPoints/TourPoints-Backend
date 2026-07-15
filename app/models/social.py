from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    TIMESTAMP,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import ComentarioEstado, comentario_estado_enum


class ImagenPoi(Base):
    __tablename__ = "imagenes_poi"

    id = Column(BigInteger, primary_key=True)
    poi_id = Column(UUID(as_uuid=True), ForeignKey("poi.id", ondelete="CASCADE"), nullable=False)
    url = Column(Text, nullable=False)
    orden = Column(SmallInteger, nullable=False, server_default=text("0"))
    principal = Column(Boolean, nullable=False, server_default=text("false"))


class Comentario(Base):
    __tablename__ = "comentarios"
    __table_args__ = (
        Index("idx_comentarios_poi", "poi_id"),
        Index("idx_comentarios_usuario", "usuario_id"),
    )

    id = Column(BigInteger, primary_key=True)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    poi_id = Column(UUID(as_uuid=True), ForeignKey("poi.id", ondelete="CASCADE"), nullable=False)
    contenido = Column(Text, nullable=False)
    estado: Mapped[ComentarioEstado] = mapped_column(
        comentario_estado_enum,
        nullable=False,
        server_default=text("'PENDIENTE'"),
    )
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class Calificacion(Base):
    __tablename__ = "calificaciones"
    __table_args__ = (
        UniqueConstraint("usuario_id", "poi_id"),
        CheckConstraint("calificacion BETWEEN 1 AND 5"),
        Index("idx_calificaciones_poi", "poi_id"),
    )

    id = Column(BigInteger, primary_key=True)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    poi_id = Column(UUID(as_uuid=True), ForeignKey("poi.id", ondelete="CASCADE"), nullable=False)
    calificacion = Column(SmallInteger, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class Favorito(Base):
    __tablename__ = "favoritos"

    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), primary_key=True)
    poi_id = Column(UUID(as_uuid=True), ForeignKey("poi.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
