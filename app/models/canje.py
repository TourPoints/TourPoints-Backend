from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Text, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import CanjeEstado, CanjeOrigen, canje_estado_enum, canje_origen_enum


class Canje(Base):
    __tablename__ = "canjes"
    __table_args__ = (
        CheckConstraint(
            "(origen = 'RETO' AND usuario_reto_id IS NOT NULL) "
            "OR (origen = 'PUNTOS' AND usuario_reto_id IS NULL)"
        ),
        Index(
            "idx_canjes_usuario_reto",
            "usuario_reto_id",
            postgresql_where=text("usuario_reto_id IS NOT NULL"),
        ),
        Index("idx_canjes_origen", "origen"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    recompensa_id = Column(UUID(as_uuid=True), ForeignKey("recompensas.id"), nullable=False)
    origen: Mapped[CanjeOrigen] = mapped_column(
        canje_origen_enum, nullable=False, server_default=text("'PUNTOS'")
    )
    # Qué intento de reto lo otorgó, si origen = RETO.
    usuario_reto_id = Column(UUID(as_uuid=True), ForeignKey("usuario_retos.id"))
    codigo_qr = Column(Text, unique=True, nullable=False)
    fecha_expira = Column(TIMESTAMP(timezone=True))
    fecha_redencion = Column(TIMESTAMP(timezone=True))
    estado: Mapped[CanjeEstado] = mapped_column(
        canje_estado_enum, nullable=False, server_default=text("'PENDIENTE'")
    )
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
