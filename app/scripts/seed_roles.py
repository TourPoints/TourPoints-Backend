# Seed de roles iniciales para la base de datos
from alembic.runtime.migration import Migrator
from alembic.runtime.environment import EnvironmentContext
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from app.models.rol import Rol
import os

# Obtener conexión a la base de datos desde .env
DATABASE_URL = os.getenv('DATABASE_URL')
engine = create_engine(DATABASE_URL)

# Función para ejecutar seed después de migraciones
@event.listens_for(engine, 'connect')
def set_sqlalchemy_event_listeners(conn, connect_args, options):
    # Crear roles si no existen
    with Session(bind=conn) as session:
        if session.query(Rol).count() == 0:
            roles = [
                Rol(id=1, nombre='ADMIN'),
                Rol(id=2, nombre='USUARIO'),
                Rol(id=3, nombre='ESTABLECIMIENTO')
            ]
            session.add_all(roles)
            session.commit()
            session.expire_on_commit(roles)

if __name__ == '__main__':
    # Ejecutar migración y seed
    config = ContextConfig(
        alembic_ini=os.getenv('ALEMBIC_INI', 'alembic.ini'),
        sql_format=True
    )
    with engine.begin() as conn:
        context = EnvironmentContext(config, conn)
        migrator = Migrator(context)
        migrator.run_migrations()
        # El seed se ejecuta automáticamente al crear la conexión
