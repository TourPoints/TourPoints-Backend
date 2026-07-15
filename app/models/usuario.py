from sqlalchemy import Column, ForeignKey, SmallInteger, String, Text, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import UsuarioEstado, usuario_estado_enum


class Rol(Base):
    __tablename__ = "roles"

    id = Column(SmallInteger, primary_key=True)
    nombre = Column(String(50), unique=True, nullable=False)
    descripcion = Column(Text)


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    rol_id = Column(SmallInteger, ForeignKey("roles.id"), nullable=False)
    nombre = Column(String(100), nullable=False)
    apellido = Column(String(100))
    email = Column(String(150), unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    telefono = Column(String(20))
    foto_url = Column(Text)
    estado: Mapped[UsuarioEstado] = mapped_column(
        usuario_estado_enum,
        nullable=False,
        server_default=text("'ACTIVO'"),
    )
    configuracion = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    deleted_at = Column(TIMESTAMP(timezone=True))
