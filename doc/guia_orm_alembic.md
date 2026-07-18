# Guía — SQLAlchemy + Alembic en TourPoints-Backend

Cómo ejecutar lo que ya quedó conectado (modelos ORM ↔ Neon vía Alembic) y cómo seguir trabajando sobre esa base. Complementa `README.md` (setup general) y `logica_negocio.md` (qué significa cada tabla).

## Índice

1. [Puesta en marcha](#1-puesta-en-marcha)
2. [Comandos de Alembic de referencia](#2-comandos-de-alembic-de-referencia)
3. [Flujo estándar para modificar el schema](#3-flujo-estándar-para-modificar-el-schema)
4. [Ejemplo A: agregar una columna a un modelo existente](#4-ejemplo-a-agregar-una-columna-a-un-modelo-existente)
5. [Ejemplo B: construir un endpoint real con el ORM (Router → Service → Repository → Model)](#5-ejemplo-b-construir-un-endpoint-real-con-el-orm)
6. [Errores comunes y cómo leerlos](#6-errores-comunes-y-cómo-leerlos)

---

## 1. Puesta en marcha

El Python del sistema (3.14) es más nuevo que el que usa el proyecto (3.12, ver `Dockerfile`) y `psycopg2-binary` no tiene wheel para 3.14 — **usa siempre Docker**, no un venv local.

```bash
# Primera vez / cuando cambie requirements.txt o el Dockerfile
docker compose build

# Levantar la API (http://localhost:8000, /docs, /health)
docker compose up

# Correr cualquier comando suelto dentro del contenedor sin levantar la API
docker compose run --rm app <comando>
```

Ejemplos de `<comando>`: `alembic current`, `python -c "..."`, `pytest`, `bash` (para entrar interactivo).

Verificar que la conexión a Neon sigue viva y ver el estado real del schema:

```bash
docker compose run --rm app python -c "
from sqlalchemy import text
from app.database import engine
with engine.connect() as conn:
    print(conn.execute(text(\"SELECT count(*) FROM pg_tables WHERE schemaname='public'\")).scalar(), 'tablas')
"
```

---

## 2. Comandos de Alembic de referencia

Todos van precedidos de `docker compose run --rm app`.

| Comando | Qué hace |
|---|---|
| `alembic current` | Qué revisión está aplicada en Neon ahora mismo. |
| `alembic history` | Lista todas las revisiones del proyecto, en orden. |
| `alembic revision --autogenerate -m "mensaje"` | Compara `Base.metadata` (tus modelos) contra la Neon real y genera un archivo en `alembic/versions/` con el diff. |
| `alembic upgrade head` | Aplica todas las migraciones pendientes contra Neon. |
| `alembic upgrade head --sql` | **Dry run**: imprime el SQL que se ejecutaría, sin tocar la base. Úsalo siempre antes de un `upgrade` que te dé dudas. |
| `alembic downgrade -1` | Revierte la última migración aplicada (ejecuta su `downgrade()`). |

---

## 3. Flujo estándar para modificar el schema

Esto aplica para **cualquier** cambio futuro: agregar una tabla, una columna, un índice, cambiar un default, etc.

1. **Editar el modelo** en `app/models/<archivo>.py` (o crear uno nuevo — si es nuevo, regístralo en `app/models/__init__.py`, si no Alembic no lo ve).
2. **Generar la migración**:
   ```bash
   docker compose run --rm app alembic revision --autogenerate -m "descripción corta del cambio"
   ```
3. **Revisar el archivo generado a mano** en `alembic/versions/`. Esto no es opcional: autogenerate detecta columnas/índices/constraints, pero **no** puede generar:
   - Funciones/triggers PL/pgSQL (`fn_*`, `trg_*`).
   - Vistas (`CREATE VIEW`).
   - Extensiones (`CREATE EXTENSION`).
   - A veces defaults raros o cambios de tipo ambiguos.

   Si tu cambio toca algo de eso, agrégalo con `op.execute("...")` a mano (mira la migración `dd9d1878d96d_esquema_inicial.py` como plantilla — ahí está todo el patrón).
4. **Dry run**:
   ```bash
   docker compose run --rm app alembic upgrade head --sql
   ```
   Lee el SQL. Si algo no cuadra con lo que esperabas, corrige el modelo o la migración antes de seguir.
5. **Aplicar**:
   ```bash
   docker compose run --rm app alembic upgrade head
   ```
6. **Verificar** con una consulta rápida (ver sección 1) o con una prueba de INSERT/SELECT real vía ORM.

---

## 4. Ejemplo A: agregar una columna a un modelo existente

Digamos que quieres agregar `instagram_url` a `poi`.

**Paso 1 — editar el modelo** (`app/models/poi.py`):

```python
class Poi(Base):
    __tablename__ = "poi"
    ...
    sitio_web = Column(Text)
    instagram_url = Column(Text)          # <-- nuevo
    horarios = Column(JSONB, ...)
    ...
```

**Paso 2 — generar la migración**:

```bash
docker compose run --rm app alembic revision --autogenerate -m "agregar instagram_url a poi"
```

Alembic va a detectar el diff y generar algo como:

```python
def upgrade() -> None:
    op.add_column('poi', sa.Column('instagram_url', sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column('poi', 'instagram_url')
```

**Paso 3 — dry run y aplicar**:

```bash
docker compose run --rm app alembic upgrade head --sql   # revisar
docker compose run --rm app alembic upgrade head         # aplicar
```

**Paso 4 — usarlo desde el ORM** (ya funciona en cualquier query/insert):

```python
poi.instagram_url = "https://instagram.com/mi_poi"
db.commit()
```

Nada más que tocar — no hay trigger ni vista involucrados en este caso, así que autogenerate cubre el 100%.

---

## 5. Ejemplo B: construir un endpoint real con el ORM

Este es el siguiente paso lógico del proyecto: `app/routers/poi.py` ya tiene el `APIRouter()` pero los endpoints son un `TODO`. Vamos a implementar `GET /api/v1/poi` y `GET /api/v1/poi/{id}` siguiendo la arquitectura documentada en el README (`Router → Service → Repository → Model`).

### 5.1 Schema de respuesta — `app/schemas/poi.py`

```python
import uuid
from pydantic import BaseModel, ConfigDict

class PoiOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # permite Pydantic <- objeto ORM

    id: uuid.UUID
    nombre: str
    slug: str
    descripcion: str | None
    direccion: str | None
    estado: str
```

`from_attributes=True` es lo que te deja hacer `PoiOut.model_validate(poi_obj)` directo sobre una instancia del modelo ORM, sin convertir a dict a mano.

### 5.2 Repository — `app/repositories/poi_repository.py`

Acceso a datos puro, sin reglas de negocio (eso lo dice el README):

```python
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.poi import Poi

class PoiRepository:
    def __init__(self, db: Session):
        self.db = db

    def listar_aprobados(self, limit: int = 20, offset: int = 0) -> list[Poi]:
        return (
            self.db.query(Poi)
            .filter(Poi.estado == "APROBADO", Poi.deleted_at.is_(None))
            .order_by(Poi.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    def obtener_por_id(self, poi_id: UUID) -> Poi | None:
        return (
            self.db.query(Poi)
            .filter(Poi.id == poi_id, Poi.deleted_at.is_(None))
            .first()
        )
```

Nota: `Poi.estado == "APROBADO"` funciona porque `estado` está mapeado a `PoiEstado` (str Enum) — comparar contra el string literal es válido gracias a que `PoiEstado` hereda de `str`.

### 5.3 Service — capa de reglas de negocio

Para estos dos endpoints no hay regla de negocio real (es solo lectura pública), así que el service es un passthrough fino — pero se mantiene por consistencia con el patrón, y es donde crecerá lógica futura (ej. cache, permisos por rol).

```python
# app/services/poi_service.py (nuevo archivo)
from uuid import UUID
from sqlalchemy.orm import Session
from app.repositories.poi_repository import PoiRepository
from app.core.exceptions import NotFoundError  # ver 5.5

class PoiService:
    def __init__(self, db: Session):
        self.repo = PoiRepository(db)

    def listar(self, limit: int = 20, offset: int = 0):
        return self.repo.listar_aprobados(limit=limit, offset=offset)

    def obtener(self, poi_id: UUID):
        poi = self.repo.obtener_por_id(poi_id)
        if poi is None:
            raise NotFoundError(f"POI {poi_id} no existe")
        return poi
```

### 5.4 Router — `app/routers/poi.py`

```python
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.poi import PoiOut
from app.services.poi_service import PoiService

router = APIRouter()

@router.get("/", response_model=list[PoiOut])
def listar_poi(
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    return PoiService(db).listar(limit=limit, offset=offset)

@router.get("/{poi_id}", response_model=PoiOut)
def obtener_poi(poi_id: UUID, db: Session = Depends(get_db)):
    return PoiService(db).obtener(poi_id)
```

`get_db` ya existe en `app/database.py` (el `yield`/`finally` que abre y cierra la sesión por request) — no hay que tocarlo.

### 5.5 Manejo de errores — `app/core/exceptions.py` + `exception_handlers.py`

Si `NotFoundError` todavía no existe, es el momento de crearla (ambos archivos están vacíos hoy):

```python
# app/core/exceptions.py
class NotFoundError(Exception):
    pass
```

```python
# app/core/exception_handlers.py
from fastapi import Request
from fastapi.responses import JSONResponse
from app.core.exceptions import NotFoundError

async def not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})
```

Y registrarlo en `app/main.py`:

```python
from app.core.exceptions import NotFoundError
from app.core.exception_handlers import not_found_handler

app.add_exception_handler(NotFoundError, not_found_handler)
```

### 5.6 Probarlo

```bash
docker compose up
# en otra terminal, o desde /docs (Swagger UI en http://localhost:8000/docs):
curl http://localhost:8000/api/v1/poi/
curl http://localhost:8000/api/v1/poi/00000000-0000-0000-0000-000000000000   # -> 404
```

Como la tabla `poi` está vacía todavía, `GET /` devolverá `[]` — para probar con datos reales, inserta un POI de prueba vía ORM (mismo patrón que el `Usuario` de prueba que usamos para validar la migración), o crea también `POST /poi` siguiendo exactamente esta misma estructura de 4 capas.

Este ejemplo es la plantilla: **el mismo patrón (Schema → Repository → Service → Router)** aplica para `visitas`, `recompensas`, `retos`, `canjes`, etc. — los repositories y services de esos módulos ya existen como archivos vacíos (`app/repositories/visita_repository.py`, `app/services/visitas_service.py`, ...), listos para llenarse igual.

---

## 6. Errores comunes y cómo leerlos

| Error | Causa típica | Qué hacer |
|---|---|---|
| `psycopg2.errors.ForeignKeyViolation` al borrar en cascada vía ORM | No hay `relationship()` definida entre los modelos, así que SQLAlchemy no infiere el orden de borrado (padres antes que hijos). | Borra manualmente en el orden correcto (hijo primero), o define `relationship(..., cascade=...)` si el caso lo amerita. |
| `sqlalchemy.exc.ProgrammingError: type "xxx_enum" already exists` al correr `upgrade head` dos veces | Intentaste re-crear un ENUM que ya existe (normalmente por editar una migración ya aplicada en vez de generar una nueva). | Nunca edites una migración que ya corriste en Neon — genera una nueva con `alembic revision --autogenerate`. |
| `NameError: name 'geoalchemy2' is not defined` en una migración autogenerada | Autogenerate no agrega automáticamente el `import` de tipos de terceros (como `Geography`). | Agrega `import geoalchemy2.types` a mano en el header de esa migración (ver el fix ya aplicado en `dd9d1878d96d_esquema_inicial.py`). |
| Autogenerate no detecta un cambio en un trigger/función/vista | Alembic solo compara objetos que SQLAlchemy modela (tablas/columnas/índices/constraints) — triggers, funciones y vistas viven fuera de `Base.metadata`. | Edítalos a mano con `op.execute(...)` en una migración nueva; no esperes que autogenerate los detecte. |
| `pg_config executable not found` al hacer `pip install` fuera de Docker | Python local (3.14) no tiene wheel de `psycopg2-binary` y falta `libpq-dev` para compilar. | No uses venv local para este proyecto — usa `docker compose run --rm app`. |
