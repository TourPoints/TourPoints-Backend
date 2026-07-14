import enum

from sqlalchemy.types import Enum as SAEnum


class UsuarioEstado(str, enum.Enum):
    ACTIVO = "ACTIVO"
    SUSPENDIDO = "SUSPENDIDO"
    ELIMINADO = "ELIMINADO"


class PoiEstado(str, enum.Enum):
    BORRADOR = "BORRADOR"
    PENDIENTE = "PENDIENTE"
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"
    INACTIVO = "INACTIVO"


class PoiFuente(str, enum.Enum):
    ADMIN = "ADMIN"
    ESTABLECIMIENTO = "ESTABLECIMIENTO"
    USUARIO = "USUARIO"
    IA = "IA"


class VisitaEstado(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    VALIDADA = "VALIDADA"
    RECHAZADA = "RECHAZADA"


class MetodoValidacion(str, enum.Enum):
    GPS = "GPS"
    QR = "QR"
    MIXTA = "MIXTA"


class CompraEstado(str, enum.Enum):
    REGISTRADA = "REGISTRADA"
    CANCELADA = "CANCELADA"
    VALIDADA = "VALIDADA"


class CanjeEstado(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    REDIMIDO = "REDIMIDO"
    EXPIRADO = "EXPIRADO"


class CanjeOrigen(str, enum.Enum):
    PUNTOS = "PUNTOS"
    RETO = "RETO"


class Moneda(str, enum.Enum):
    COP = "COP"
    USD = "USD"


class ComentarioEstado(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    APROBADO = "APROBADO"
    RECHAZADO = "RECHAZADO"


class RetoTipo(str, enum.Enum):
    VISITA = "VISITA"
    COMPRA = "COMPRA"
    RECORRIDO = "RECORRIDO"


class RetoEstado(str, enum.Enum):
    BORRADOR = "BORRADOR"
    ACTIVO = "ACTIVO"
    FINALIZADO = "FINALIZADO"
    CANCELADO = "CANCELADO"


class RetoRecurrencia(str, enum.Enum):
    UNICA = "UNICA"
    DIARIA = "DIARIA"
    SEMANAL = "SEMANAL"
    MENSUAL = "MENSUAL"


class RetoModoRecompensa(str, enum.Enum):
    GARANTIZADA = "GARANTIZADA"
    LIMITADA = "LIMITADA"
    SIN_RECOMPENSA = "SIN_RECOMPENSA"


class TipoMovimientoPuntos(str, enum.Enum):
    VISITA = "VISITA"
    COMPRA = "COMPRA"
    RETO = "RETO"
    CANJE = "CANJE"


class ConversacionRole(str, enum.Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


# Tipos SQLAlchemy compartidos: una única instancia por ENUM nativo de
# Postgres, reutilizada en todas las columnas/tablas que lo usan (ej.
# poi_estado_enum en poi/establecimientos/promociones/recompensas). Así
# Alembic solo emite un CREATE TYPE por nombre en vez de duplicarlo.
usuario_estado_enum = SAEnum(UsuarioEstado, name="usuario_estado_enum")
poi_estado_enum = SAEnum(PoiEstado, name="poi_estado_enum")
poi_fuente_enum = SAEnum(PoiFuente, name="poi_fuente_enum")
visita_estado_enum = SAEnum(VisitaEstado, name="visita_estado_enum")
metodo_validacion_enum = SAEnum(MetodoValidacion, name="metodo_validacion_enum")
compra_estado_enum = SAEnum(CompraEstado, name="compra_estado_enum")
canje_estado_enum = SAEnum(CanjeEstado, name="canje_estado_enum")
canje_origen_enum = SAEnum(CanjeOrigen, name="canje_origen_enum")
moneda_enum = SAEnum(Moneda, name="moneda_enum")
comentario_estado_enum = SAEnum(ComentarioEstado, name="comentario_estado_enum")
reto_tipo_enum = SAEnum(RetoTipo, name="reto_tipo_enum")
reto_estado_enum = SAEnum(RetoEstado, name="reto_estado_enum")
reto_recurrencia_enum = SAEnum(RetoRecurrencia, name="reto_recurrencia_enum")
reto_modo_recompensa_enum = SAEnum(RetoModoRecompensa, name="reto_modo_recompensa_enum")
tipo_movimiento_puntos_enum = SAEnum(TipoMovimientoPuntos, name="tipo_movimiento_puntos_enum")
conversacion_role_enum = SAEnum(ConversacionRole, name="conversacion_role_enum")
