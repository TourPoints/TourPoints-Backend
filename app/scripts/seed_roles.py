"""Siembra los roles base (admin, usuario, establecimiento). Uso: python -m app.scripts.seed_roles"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.usuario import Rol
from app.database import Base


def get_database_url() -> str:
    return os.getenv("DATABASE_URL") or os.getenv("DATABASE_URL_LOCAL")


def seed_roles(database_url: str | None = None) -> None:
    if not database_url:
        database_url = get_database_url()
    if not database_url:
        raise RuntimeError("DATABASE_URL no está definida en el entorno")

    engine = create_engine(database_url)
    Base.metadata.create_all(bind=engine)  # no-op si el esquema ya está migrado

    with Session(bind=engine) as session:
        existing = {r.nombre.upper(): r for r in session.query(Rol).all()}

        roles_to_create = []
        for id_, name in ((1, "admin"), (2, "usuario"), (3, "establecimiento")):
            if name.upper() not in existing:
                roles_to_create.append(Rol(id=id_, nombre=name, descripcion=f"Rol {name}"))

        if roles_to_create:
            session.add_all(roles_to_create)
            session.commit()
            print(f"Se crearon {len(roles_to_create)} roles: {[r.nombre for r in roles_to_create]}")
        else:
            print("Los roles ya existen. No se realizaron cambios.")


if __name__ == "__main__":
    seed_roles()
