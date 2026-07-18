# TourPoints — Backend

API del backend de TourPoints, una app de turismo gamificado: los usuarios descubren puntos de interés (POIs), los visitan, compran en negocios aliados y completan retos, todo lo cual otorga puntos canjeables por recompensas.

Este repositorio es **solo el backend**. El frontend vive en otro repositorio.

## Stack

- **FastAPI** — framework de la API.
- **SQLAlchemy** + **Alembic** — ORM y migraciones.
- **PostgreSQL (Neon)** — base de datos. Requiere la extensión **PostGIS** (los POIs se ubican con tipos geográficos, `Geography(Point,4326)`).
- **python-jose** + **passlib** — autenticación propia por JWT (no se usa Neon Auth en esta etapa).
- **Cloudinary** — almacenamiento de imágenes (fotos de POI y de perfil de usuario). La BD solo guarda la URL, nunca el binario.
- **APScheduler** — job periódico in-process (expira intentos de reto vencidos cada hora). Ver [`app/core/scheduler.py`](app/core/scheduler.py) y la nota sobre `pg_cron` más abajo.
- **pytest** — tests. ⚠️ **borran todos los datos** de la base configurada en `DATABASE_URL` al arrancar (no hay base de test separada) — ver sección [Tests](#tests) antes de correrlos.

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
- `app/core/` — excepciones de dominio, sus handlers HTTP, y el scheduler de jobs periódicos.
- `app/utils/` — helpers (`geo.py` para distancia GPS, `qr.py` para códigos de canje y check-in, `media.py` para validación de imágenes).
- `app/scripts/` — seeds ejecutables una vez (`seed_roles.py`, `seed_tipos_relacion_poi.py`, `seed_insignias.py`) para poblar catálogos base en un entorno nuevo.

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
   | `ACCESS_TOKEN_EXPIRE_MINUTES` | Minutos de validez del token (`60` por defecto). No hay refresh token todavía — al expirar, el cliente debe volver a hacer login |
   | `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` | Credenciales de Cloudinary (Dashboard → Account Details). **Obligatorias** — `app/config.py` no tiene default para estas tres, la app no arranca sin ellas |

   Todas las variables son requeridas salvo que el default esté indicado arriba — `Settings` en `app/config.py` es la fuente de verdad si hay dudas.

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

Documentación más profunda en `doc/`:

| Archivo | Qué cubre |
|---|---|
| [`doc/endpoints_api.md`](doc/endpoints_api.md) | **Contrato completo de la API** — todos los endpoints implementados, con auth, body, response real y notas de qué difiere del diseño original. Es la referencia más actualizada y detallada; ante cualquier duda sobre un endpoint, empezar acá. |
| [`doc/auth_usuarios_api.md`](doc/auth_usuarios_api.md) | Detalle fino de `/auth` y `/users` (claims del JWT, reglas de cada campo, cobertura de tests). |
| [`doc/logica_negocio.md`](doc/logica_negocio.md) | Qué hace cada tabla, qué invariantes garantiza la base de datos (`CHECK`s, triggers, columnas generadas) y cómo fluyen los procesos de negocio de punta a punta — **no describe endpoints**, es el modelo de datos puro. |
| [`doc/schem_posgrest.sql`](doc/schem_posgrest.sql) | El DDL completo de referencia (33 tablas, triggers, vistas). |
| [`doc/guia_orm_alembic.md`](doc/guia_orm_alembic.md) | Cómo trabajar con SQLAlchemy + Alembic en este proyecto: comandos, flujo para modificar el schema, errores comunes. |

## Migraciones (Alembic)

Alembic está inicializado y conectado a `Base.metadata` (`app/database.py`) y a `DATABASE_URL` (`app/config.py`). Migraciones aplicadas hoy en la base real:

1. `dd9d1878d96d` — esquema inicial (todas las tablas de `doc/schem_posgrest.sql`).
2. `5e0ac9f7b8ed` — tabla de auditoría `poi_moderaciones`.

Ver el estado real de la base:

```bash
alembic current
```

Flujo normal para un cambio de schema (detallado con ejemplos en [`doc/guia_orm_alembic.md`](doc/guia_orm_alembic.md)):

```bash
alembic revision --autogenerate -m "descripción del cambio"
alembic upgrade head
```

## Tests

```bash
pytest
```

(requiere tener el entorno virtual activado y las dependencias instaladas, ver sección "sin Docker" arriba)

⚠️ **`pytest` borra todos los datos de la base configurada en `DATABASE_URL`.** No hay una base de test separada — la suite corre contra la misma Neon real de `.env`. El fixture `_schema` (session-scoped, autouse, en `tests/conftest.py`) ejecuta `TRUNCATE {tabla} CASCADE` sobre **las 33 tablas del schema, una sola vez al arrancar la sesión de tests**, antes de que corra un solo test. Después de ese truncado inicial, cada test individual sí queda aislado (el fixture `db` corre dentro de una transacción con `rollback()` al final, así que lo que crea un test no lo ve el siguiente) — pero ese primer `TRUNCATE` es real e irreversible. **Nunca corras `pytest` apuntando `DATABASE_URL` a una base con datos que te importen.** Si necesitás correr los tests, usá una base descartable (una branch de Neon, por ejemplo) — nunca la de desarrollo compartida.

## Estado actual

Todos los módulos de negocio del diseño original están implementados y probados end-to-end contra la base real: catálogos (países/departamentos/ciudades/categorías), POI (con moderación, imágenes y check-in QR), usuarios (con foto de perfil), social (calificaciones/comentarios/favoritos), visitas (GPS/QR/MIXTA), recompensas y canjes (con validación QR física), comercial (establecimientos/compras/promociones, con autorización real por pertenencia), retos (plantillas, inscripción, progreso, rachas, hitos, insignias) y puntos (historial del ledger).

El detalle endpoint por endpoint, incluidas las decisiones que no estaban en el diseño original y los gaps conocidos, vive en [`doc/endpoints_api.md`](doc/endpoints_api.md) — ese documento es la fuente de verdad más actualizada, más que este README.

Pendiente conocido, no bloqueante: el tracking punto-a-punto en vivo de los retos tipo `RECORRIDO` (`sesiones_reto` solo guarda el marco inicio/fin/estado, sin coordenadas — el diseño original lo pensaba con Redis, todavía no implementado).
