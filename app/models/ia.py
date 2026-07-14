from sqlalchemy import BigInteger, Column, ForeignKey, Index, Integer, Numeric, String, Text, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import ConversacionRole, conversacion_role_enum


class ConversacionIa(Base):
    __tablename__ = "conversaciones_ia"
    # Acceso típico: "toda la sesión, en orden".
    __table_args__ = (Index("idx_conversaciones_ia_session", "session_id", "created_at"),)

    id = Column(BigInteger, primary_key=True)
    session_id = Column(UUID(as_uuid=True), nullable=False)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    role: Mapped[ConversacionRole] = mapped_column(conversacion_role_enum, nullable=False)
    contenido = Column(Text, nullable=False)
    modelo = Column(String(80))
    tokens = Column(Integer)
    temperatura = Column(Numeric(3, 2))
    latencia_ms = Column(Integer)
    costo_usd = Column(Numeric(10, 6))
    finish_reason = Column(String(40))
    metadata_ = Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
