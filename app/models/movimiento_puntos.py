from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Computed,
    ForeignKey,
    Index,
    Integer,
    TIMESTAMP,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import TipoMovimientoPuntos, tipo_movimiento_puntos_enum


class MovimientoPuntos(Base):
    """Libro mayor de puntos: append-only, nunca se actualiza ni se borra
    una fila existente (ver movimientos_puntos en schem_posgrest.sql)."""

    __tablename__ = "movimientos_puntos"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(visita_id, compra_id, usuario_reto_id, canje_id) = 1"
        ),
        Index("idx_movimientos_puntos_tipo", "tipo_movimiento"),
        Index("idx_movimientos_puntos_usuario", "usuario_id"),
    )

    id = Column(BigInteger, primary_key=True)
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    # Qué regla de reglas_puntos generó el movimiento (trazabilidad).
    regla_id = Column(UUID(as_uuid=True), ForeignKey("reglas_puntos.id"))
    visita_id = Column(UUID(as_uuid=True), ForeignKey("visitas.id"))
    compra_id = Column(UUID(as_uuid=True), ForeignKey("compras.id"))
    # Referencia al INTENTO del usuario (usuario_retos), no al reto genérico.
    usuario_reto_id = Column(UUID(as_uuid=True), ForeignKey("usuario_retos.id"))
    canje_id = Column(UUID(as_uuid=True), ForeignKey("canjes.id"))
    # Derivada de las FK, no escribible directamente: elimina el riesgo de
    # inconsistencia entre "tipo declarado" y "FK realmente llena".
    tipo_movimiento: Mapped[TipoMovimientoPuntos] = mapped_column(
        tipo_movimiento_puntos_enum,
        Computed(
            """
            CASE
                WHEN visita_id IS NOT NULL THEN 'VISITA'::tipo_movimiento_puntos_enum
                WHEN compra_id IS NOT NULL THEN 'COMPRA'::tipo_movimiento_puntos_enum
                WHEN usuario_reto_id IS NOT NULL THEN 'RETO'::tipo_movimiento_puntos_enum
                WHEN canje_id IS NOT NULL THEN 'CANJE'::tipo_movimiento_puntos_enum
            END
            """,
            persisted=True,
        ),
    )
    puntos = Column(Integer, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))

# El saldo NUNCA se guarda como columna: se calcula con SUM(puntos) vía la
# vista `saldo_puntos_usuario`, creada con SQL crudo en la migración (no
# es una tabla, así que no se mapea aquí como modelo ORM de escritura;
# consúltala con sqlalchemy.text()/Core, ej. en puntos_service).
