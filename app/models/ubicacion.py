from sqlalchemy import (
    BigInteger,
    CHAR,
    Column,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
)

from app.database import Base


class Pais(Base):
    __tablename__ = "paises"

    id = Column(SmallInteger, primary_key=True)
    nombre = Column(String(100), nullable=False)
    codigo_iso = Column(CHAR(2), unique=True, nullable=False)


class Departamento(Base):
    __tablename__ = "departamentos"
    __table_args__ = (UniqueConstraint("pais_id", "nombre"),)

    id = Column(Integer, primary_key=True)
    pais_id = Column(SmallInteger, ForeignKey("paises.id"), nullable=False)
    nombre = Column(String(100), nullable=False)


class Ciudad(Base):
    __tablename__ = "ciudades"
    __table_args__ = (UniqueConstraint("departamento_id", "nombre"),)

    id = Column(BigInteger, primary_key=True)
    departamento_id = Column(Integer, ForeignKey("departamentos.id"), nullable=False)
    nombre = Column(String(100), nullable=False)
