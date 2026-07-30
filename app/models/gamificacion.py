from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
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
from app.models.enums import (
    PoiEstado,
    RetoEstado,
    RetoModoRecompensa,
    RetoRecurrencia,
    RetoTipo,
    poi_estado_enum,
    reto_estado_enum,
    reto_modo_recompensa_enum,
    reto_recurrencia_enum,
    reto_tipo_enum,
)


class ReglaPuntos(Base):
    __tablename__ = "reglas_puntos"
    __table_args__ = (
        CheckConstraint(
            "vigencia_fin IS NULL OR vigencia_inicio IS NULL OR vigencia_fin > vigencia_inicio"
        ),
        Index("idx_reglas_puntos_configuracion", "configuracion", postgresql_using="gin"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    nombre = Column(String(200), nullable=False)
    prioridad = Column(SmallInteger, nullable=False, server_default=text("0"))
    configuracion = Column(JSONB, nullable=False)  # {"evento":"VISITA","categoria":"Museo","puntos":120}
    vigencia_inicio = Column(TIMESTAMP(timezone=True))
    vigencia_fin = Column(TIMESTAMP(timezone=True))
    activo = Column(Boolean, nullable=False, server_default=text("true"))


# recompensas se declara antes de retos/canjes porque ambos la referencian.
class Recompensa(Base):
    __tablename__ = "recompensas"
    __table_args__ = (CheckConstraint("stock >= 0"), CheckConstraint("puntos > 0"))

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    poi_id = Column(UUID(as_uuid=True), ForeignKey("poi.id"))  # nullable: no toda recompensa depende de un aliado
    nombre = Column(String(200), nullable=False)
    descripcion = Column(Text)
    stock = Column(Integer, nullable=False, server_default=text("0"))
    puntos = Column(Integer, nullable=False)
    estado: Mapped[PoiEstado] = mapped_column(
        poi_estado_enum,
        nullable=False,
        server_default=text("'BORRADOR'"),
    )


class Reto(Base):
    __tablename__ = "retos"
    __table_args__ = (
        CheckConstraint("fin IS NULL OR fin > inicio"),
        CheckConstraint(
            "(modo_recompensa = 'SIN_RECOMPENSA' AND recompensa_id IS NULL) "
            "OR (modo_recompensa IN ('GARANTIZADA','LIMITADA') AND recompensa_id IS NOT NULL)"
        ),
        Index("idx_retos_tipo_estado", "tipo", "estado"),
        Index("idx_retos_recurrencia", "recurrencia", postgresql_where=text("estado = 'ACTIVO'")),
        Index(
            "idx_retos_establecimiento",
            "establecimiento_id",
            postgresql_where=text("establecimiento_id IS NOT NULL"),
        ),
        Index("idx_retos_configuracion", "configuracion", postgresql_using="gin"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    nombre = Column(String(200), nullable=False)
    descripcion = Column(Text)
    tipo: Mapped[RetoTipo] = mapped_column(reto_tipo_enum, nullable=False)
    recurrencia: Mapped[RetoRecurrencia] = mapped_column(
        reto_recurrencia_enum, nullable=False, server_default=text("'UNICA'")
    )
    cantidad_requerida = Column(SmallInteger, nullable=False)
    recompensa_id = Column(UUID(as_uuid=True), ForeignKey("recompensas.id"))
    modo_recompensa: Mapped[RetoModoRecompensa] = mapped_column(
        reto_modo_recompensa_enum, nullable=False, server_default=text("'SIN_RECOMPENSA'")
    )
    # Quién lo creó: si lo propone un establecimiento aliado,
    # establecimiento_id queda lleno y el reto nace en BORRADOR hasta
    # que un admin lo apruebe (ACTIVO) o lo rechace (CANCELADO).
    creado_por_usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"))
    establecimiento_id = Column(UUID(as_uuid=True), ForeignKey("establecimientos.id"))
    inicio = Column(TIMESTAMP(timezone=True), nullable=False)
    fin = Column(TIMESTAMP(timezone=True))
    estado: Mapped[RetoEstado] = mapped_column(
        reto_estado_enum, nullable=False, server_default=text("'BORRADOR'")
    )
    configuracion = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))


class UsuarioReto(Base):
    __tablename__ = "usuario_retos"
    __table_args__ = (
        CheckConstraint("periodo_fin IS NULL OR periodo_fin > periodo_inicio"),
        CheckConstraint("porcentaje BETWEEN 0 AND 100"),
        UniqueConstraint("usuario_id", "reto_id", "periodo_inicio", "numero_intento"),
        Index("idx_usuario_retos_periodo", "reto_id", "periodo_inicio"),
        Index("idx_usuario_retos_progreso", "progreso", postgresql_using="gin"),
        # Solo un intento ACTIVO por usuario+reto+periodo a la vez.
        Index(
            "idx_usuario_retos_intento_activo",
            "usuario_id",
            "reto_id",
            "periodo_inicio",
            unique=True,
            postgresql_where=text("estado = 'ACTIVO'"),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    reto_id = Column(UUID(as_uuid=True), ForeignKey("retos.id"), nullable=False)
    periodo_inicio = Column(TIMESTAMP(timezone=True), nullable=False)
    periodo_fin = Column(TIMESTAMP(timezone=True))
    numero_intento = Column(SmallInteger, nullable=False, server_default=text("1"))
    progreso = Column(
        JSONB, nullable=False, server_default=text("""'{"completados": [], "cantidad": 0}'::jsonb""")
    )
    porcentaje = Column(SmallInteger, nullable=False, server_default=text("0"))
    fecha_completado = Column(TIMESTAMP(timezone=True))
    estado: Mapped[RetoEstado] = mapped_column(
        reto_estado_enum, nullable=False, server_default=text("'ACTIVO'")
    )
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class SesionReto(Base):
    __tablename__ = "sesiones_reto"
    __table_args__ = (
        CheckConstraint("fin IS NULL OR fin > inicio"),
        Index("idx_sesiones_reto_usuario_reto", "usuario_reto_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    usuario_reto_id = Column(
        UUID(as_uuid=True), ForeignKey("usuario_retos.id", ondelete="CASCADE"), nullable=False
    )
    inicio = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
    fin = Column(TIMESTAMP(timezone=True))
    estado: Mapped[RetoEstado] = mapped_column(
        reto_estado_enum, nullable=False, server_default=text("'ACTIVO'")
    )


class RachaReto(Base):
    __tablename__ = "rachas_retos"
    __table_args__ = (
        UniqueConstraint("usuario_id", "reto_id"),
        CheckConstraint("racha_actual >= 0 AND racha_maxima >= racha_actual"),
        Index("idx_rachas_retos_usuario", "usuario_id", "reto_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    reto_id = Column(UUID(as_uuid=True), ForeignKey("retos.id"), nullable=False)
    racha_actual = Column(SmallInteger, nullable=False, server_default=text("0"))
    racha_maxima = Column(SmallInteger, nullable=False, server_default=text("0"))
    ultimo_periodo_inicio = Column(TIMESTAMP(timezone=True))
    # ASUNCION: distingue "participó" de "completó" el último ciclo visto.
    ultimo_periodo_completado = Column(Boolean, nullable=False, server_default=text("false"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))


class Insignia(Base):
    __tablename__ = "insignias"

    id = Column(SmallInteger, primary_key=True)
    codigo = Column(String(60), unique=True, nullable=False)
    nombre = Column(String(200), nullable=False)
    descripcion = Column(Text)
    icono = Column(Text)


class HitoRacha(Base):
    __tablename__ = "hitos_racha"
    __table_args__ = (
        CheckConstraint("racha_requerida > 0"),
        CheckConstraint("puntos_bonus >= 0"),
        UniqueConstraint("reto_id", "racha_requerida"),
        Index("idx_hitos_racha_reto", "reto_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    reto_id = Column(UUID(as_uuid=True), ForeignKey("retos.id"), nullable=False)
    racha_requerida = Column(SmallInteger, nullable=False)
    nombre = Column(String(200), nullable=False)  # ej. "Racha de fuego"
    puntos_bonus = Column(Integer, nullable=False, server_default=text("0"))
    recompensa_id = Column(UUID(as_uuid=True), ForeignKey("recompensas.id"))
    insignia_id = Column(SmallInteger, ForeignKey("insignias.id"))


class HitoRachaAlcanzado(Base):
    __tablename__ = "hitos_racha_alcanzados"
    __table_args__ = (Index("idx_hitos_racha_alcanzados_usuario", "usuario_id", "hito_id"),)

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    usuario_id = Column(UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False)
    hito_id = Column(UUID(as_uuid=True), ForeignKey("hitos_racha.id"), nullable=False)
    usuario_reto_id = Column(UUID(as_uuid=True), ForeignKey("usuario_retos.id"), nullable=False)
    # Se completa vía trigger fn_otorgar_recompensa_hito (creado en la
    # migración): nunca bloquea el logro, solo decide si hubo stock.
    recompensa_otorgada = Column(Boolean, nullable=False, server_default=text("false"))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("now()"))
