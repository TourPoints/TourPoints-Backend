# TourPoints — Backend

API del backend de TourPoints, una app de turismo gamificado: los usuarios descubren puntos de interés (POIs), los visitan, compran en negocios aliados y completan retos, todo lo cual otorga puntos canjeables por recompensas.

Este repositorio es **solo el backend**. El frontend vive en otro repositorio.

## Stack

- **FastAPI** — framework de la API.
- **SQLAlchemy** + **Alembic** — ORM y migraciones.
- **PostgreSQL (Neon)** — base de datos. Requiere la extensión **PostGIS** (los POIs se ubican con tipos geográficos).
- **python-jose** + **passlib** — autenticación propia por JWT (no se usa Neon Auth en esta etapa).
- **pytest** — tests.

## Arquitectura

El proyecto sigue una arquitectura en capas:

```
Router (FastAPI)  →  Service            →  Repository        →  Model (SQLAlchemy ORM)
   │                     │                      │
   └─ Schema (Pydantic)  └─ reglas de negocio    └─ acceso a datos
      valida request/       que la DB no            puro, sin
      response HTTP         garantiza                lógica de negocio
```

- `app/routers/` — endpoints HTTP, sin lógica de negocio.
- `app/services/` — orquestan repositories y aplican reglas de negocio.
- `app/repositories/` — acceso a datos con SQLAlchemy.
- `app/models/` — mapeo ORM, un archivo por dominio (no por tabla).
- `app/schemas/` — DTOs Pydantic para request/response.
- `app/auth/` — hashing de password, creación/validación de JWT.
- `app/core/` — excepciones de dominio y sus handlers HTTP.
- `app/utils/` — helpers (`geo.py` para validar distancia GPS, `qr.py` para códigos de canje).

## Requisitos previos

- Docker y Docker Compose (para correrlo en contenedor), **o** Python 3.12 (para correrlo local sin Docker).
- Acceso a una base de datos PostgreSQL con PostGIS habilitado (se usa Neon en este proyecto).

## Configuración

1. Si es la primera vez que clonas el repo (todavía no tienes `.env`), copia la plantilla:
   ```bash
   cp .env.example .env
   ```
   ⚠️ Si ya tienes un `.env` con credenciales reales, **no** ejecutes esto — lo sobrescribirías.
2. Completa `.env` con tus valores reales:

   | Variable | Descripción |
   |---|---|
   | `DATABASE_URL` | Connection string de Postgres (Neon → Dashboard → Connection Details) |
   | `SECRET_KEY` | Clave para firmar los JWT. Genera una propia: `openssl rand -hex 32` — **nunca reutilices la del ejemplo** |
   | `ALGORITHM` | Algoritmo de firma del JWT (`HS256` por defecto) |
   | `ACCESS_TOKEN_EXPIRE_MINUTES` | Minutos de validez del token (`60` por defecto) |

   `.env` está en `.gitignore` — nunca se commitea. `.env.example` sí se commitea y **no** debe tener secretos reales.

## Cómo ejecutar — con Docker (recomendado)

```bash
docker compose up --build
```

- La API queda disponible en `http://localhost:8000`.
- El contenedor corre con `--reload` y el código local está montado como volumen (`.:/app`): cualquier cambio en tu editor se refleja al instante, sin reconstruir la imagen.
- Para detenerlo: `docker compose down`.
- Solo hace falta reconstruir (`docker compose up --build`) cuando cambian `requirements.txt` o el `Dockerfile`.

## Cómo ejecutar — sin Docker (local)

```bash
python3 -m venv .venv
source .venv/bin/activate        # en Windows: .venv\Scripts\activate
pip install -r requirements.txt

# si no tienes .env todavía: cp .env.example .env y complétalo (ver sección "Configuración")

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Documentación de la API

Con la app corriendo (por cualquiera de los dos métodos):

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health check: `http://localhost:8000/health`

Todas las rutas de negocio cuelgan del prefijo `/api/v1`.

## Migraciones (Alembic)

El proyecto tiene la carpeta `alembic/` scaffolded pero **Alembic todavía no está inicializado** (`alembic.ini` y `alembic/env.py` están vacíos). Antes de generar la primera migración hay que:

1. Inicializar `alembic/env.py` para que use `Base.metadata` de `app/database.py` y lea `DATABASE_URL` desde `app/config.py`.
2. Generar la revisión inicial reflejando el schema del proyecto (no partir de cero con `--autogenerate` si ya existe un DDL de referencia).

Una vez configurado, el flujo normal es:

```bash
alembic revision --autogenerate -m "descripción del cambio"
alembic upgrade head
```

## Tests

```bash
pytest
```

(requiere tener el entorno virtual activado y las dependencias instaladas, ver sección "sin Docker" arriba)

## Estado actual

Este backend está en construcción activa. La arquitectura (capas, Docker, auth JWT) ya está resuelta; los endpoints de negocio (POIs, visitas, recompensas, canjes, puntos) se están implementando módulo por módulo siguiendo el mismo patrón Router → Service → Repository.
