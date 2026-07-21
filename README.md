# 🗺️ TourPoints — Backend 🧑‍💻

API del backend de **TourPoints**, una app de turismo gamificado: los usuarios descubren puntos de interés (POIs), los visitan, compran en negocios aliados y completan retos, todo lo cual otorga puntos canjeables por recompensas.

Este repositorio es **solo el backend**. El frontend vive en otro repositorio.

[![FastAPI](https://img.shields.io/badge/FastAPI-API-009688)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-PostGIS-336791)](https://www.postgresql.org/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-red)](https://www.sqlalchemy.org/)
[![JWT](https://img.shields.io/badge/Auth-JWT-yellow)](https://jwt.io/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED)](https://www.docker.com/)

---

## 📋 Table of Contents

- [Project Overview](#-project-overview)
- [Features](#-features)
- [Project Structure](#-project-structure)
- [Architecture](#-architecture)
- [Business Logic & Security](#-business-logic--security)
- [Database & Migrations](#-database--migrations)
- [Technologies](#-technologies)
- [How to Run](#-how-to-run)
- [API Documentation](#-api-documentation)
- [Tests](#-tests)
- [Project Status](#-project-status)
- [Academic Objectives](#-academic-objectives)
- [Author](#-author)

---

## 📖 Project Overview

Este proyecto corresponde al backend de una plataforma de turismo gamificado, desarrollado como parte del proyecto integrador del programa de Riwi.

El objetivo principal es aplicar:

- Arquitectura en capas (Router → Service → Repository → Model)
- Modelado geoespacial con PostGIS
- Autenticación y autorización con JWT
- Reglas de negocio complejas (gamificación, ledger de puntos, moderación)
- Buenas prácticas de backend con FastAPI y SQLAlchemy

El sistema incluye:

- Autenticación y gestión de usuarios (con foto de perfil)
- Catálogo geográfico (países, departamentos, ciudades) y categorías de POI
- Gestión de puntos de interés (POI) con moderación e imágenes
- Interacción social (calificaciones, comentarios, favoritos)
- Check-in de visitas por GPS, QR o método mixto
- Recompensas y canjes, incluida validación QR física en el punto de canje
- Módulo comercial (establecimientos aliados, compras, promociones)
- Módulo de retos (challenges, rachas, hitos, insignias)
- Historial de puntos vía un ledger append-only

---

## ✨ Features

### 🔐 Autenticación y Usuarios
- Registro/login con JWT (`python-jose` + `passlib`)
- Roles: `admin`, `usuario`, `establecimiento`
- Perfil propio, cambio de contraseña, foto de perfil vía Cloudinary

### 🗺️ POIs y Geolocalización
- Ubicación con tipos geográficos PostGIS (`Geography(Point,4326)`)
- Flujo de moderación (`BORRADOR` → `PENDIENTE` → `APROBADO`/`RECHAZADO`)
- Imágenes múltiples por POI, con imagen principal
- Código QR de check-in por POI (HMAC determinístico, sin almacenamiento en BD)

### 🎮 Gamificación
- Retos con recurrencia (única, diaria, semanal, mensual)
- Rachas (streaks) con detección de gaps y hitos automáticos
- Insignias otorgadas al alcanzar hitos de racha
- Recompensas con modos `GARANTIZADA` / `LIMITADA`, canje por QR

### 🏪 Módulo Comercial
- Establecimientos afiliados a un POI propio, con moderación
- Registro de compras con acreditación automática de puntos
- Reversión de compras vía movimiento compensatorio (nunca se edita el ledger)
- Promociones con vigencia (`inicio`/`fin`) y moderación

### 🧱 Arquitectura y Calidad
- Separación estricta Router / Service / Repository / Model
- Autorización por pertenencia real (`establecimiento_usuarios`), no solo por rol global
- Excepciones de dominio con handlers HTTP centralizados
- Documentación Swagger/OpenAPI en inglés, campos JSON en español (consistentes con la BD)

---

## 📁 Project Structure

```
TourPoints-Backend/
├── app/
│   ├── main.py              # arma la app FastAPI, monta routers bajo /api/v1, CORS, startup/shutdown
│   ├── config.py            # Settings (pydantic-settings), lee .env
│   ├── database.py          # engine, SessionLocal, Base declarativa, get_db()
│   ├── auth/                 # JWT + hashing de password
│   ├── core/                 # excepciones, handlers, middleware, scheduler
│   ├── routers/               # 1 archivo por dominio: auth, catalogos, poi, social,
│   │                          # usuarios, visitas, recompensas, canjes, comercial, retos, puntos
│   ├── services/               # reglas de negocio, 1 archivo por dominio (espejo de routers)
│   ├── repositories/           # acceso a datos SQLAlchemy, 1 archivo por dominio
│   ├── models/                 # ORM: usuario, poi, ubicacion, social, visita, comercial,
│   │                          # gamificacion (retos/insignias/rachas), canje, movimiento_puntos, ia, enums
│   ├── schemas/                 # DTOs Pydantic, request/response
│   ├── utils/                   # geo.py, qr.py, media.py
│   └── scripts/                 # seeds idempotentes (roles, tipos_relacion_poi, insignias)
│
├── alembic/                      # migraciones (env.py conectado a Base.metadata y DATABASE_URL)
│   └── versions/                  # dd9d1878d96d (esquema inicial), 5e0ac9f7b8ed (poi_moderaciones)
│
├── tests/                         # pytest — ver sección Tests, ⚠️ trunca la BD de DATABASE_URL
├── doc/                            # documentación profunda (ver tabla en API Documentation)
├── scripts/                        # smoke tests manuales fuera de la app (no seeds)
├── docker-compose.yml, Dockerfile
├── requirements.txt
├── alembic.ini
└── .env.example
```

> **Nota:** dos piezas del schema tienen modelo ORM pero **ningún endpoint todavía**: relaciones entre POIs (`poi_relaciones` / `tipos_relacion_poi`) e IA conversacional (`conversaciones_ia`). `app/routers/promociones.py` es un archivo vacío sin uso — las promociones reales se sirven desde `app/routers/comercial.py`. Detalle en [`doc/auth_usuarios_api.md`](doc/auth_usuarios_api.md).

---

## 🏗️ Architecture

El proyecto sigue una arquitectura en capas:

```
Router (FastAPI)  →  Service            →  Repository        →  Model (SQLAlchemy ORM)
   │                     │                      │
   └─ Schema (Pydantic)  └─ reglas de negocio    └─ acceso a datos
      valida request/       que la DB no            puro, sin
      response HTTP         garantiza                lógica de negocio
```

- **`app/routers/`** — endpoints HTTP, sin lógica de negocio.
- **`app/services/`** — orquestan repositories y aplican reglas de negocio.
- **`app/repositories/`** — acceso a datos con SQLAlchemy.
- **`app/models/`** — mapeo ORM, un archivo por dominio (no por tabla).
- **`app/schemas/`** — DTOs Pydantic para request/response.
- **`app/auth/`** — `security.py` (hashing con bcrypt, JWT) y `dependencies.py` (`get_current_user`, `get_admin_user`, `get_optional_user`, etc.).
- **`app/core/`** — `exceptions.py` + `exception_handlers.py` (excepciones de dominio y handlers HTTP), `scheduler.py` (job periódico in-process) y `middleware.py` (`JWTMiddleware`, que pese al nombre solo loguea cada request; la validación real del JWT vive en `app/auth/dependencies.py`).
- **`app/utils/`** — `geo.py` (distancia GPS), `qr.py` (códigos de canje y check-in), `media.py` (validación de imágenes).

---

## ⚡ Business Logic & Security

Puntos clave de la lógica de negocio implementada:

- **Ledger append-only de puntos** (`movimientos_puntos`): nunca se edita ni se borra un movimiento; las reversiones (ej. cancelar una compra) se hacen con un movimiento negativo compensatorio.
- **Autorización por pertenencia real**: endpoints como `POST /redemptions/validate-qr` verifican membresía en `establecimiento_usuarios`, no solo el rol global del token.
- **Check-in de visitas** por GPS (distancia calculada con PostGIS `ST_DWithin`/`ST_Distance`), por QR (código HMAC determinístico por POI) o `MIXTA` (ambos a la vez).
- **QR de canje vs. QR de check-in**: el de canje de recompensa usa un token aleatorio almacenado en BD; el de check-in de POI es determinístico (HMAC) y no requiere almacenamiento.
- **Gamificación de retos**: cálculo de periodo según recurrencia, detección de gaps en la racha, otorgamiento automático de hitos/insignias, y un flujo de dos fases al completar un reto (los puntos/racha/hitos se confirman aunque el canje de recompensa `LIMITADA` falle por falta de stock).
- **Job periódico in-process** (`APScheduler`, no `pg_cron` — no disponible en el plan de Neon usado) que expira retos vencidos cada hora.

---

## 🗄️ Database & Migrations

- **PostgreSQL (Neon)** con extensión **PostGIS** habilitada (los POIs usan `Geography(Point,4326)`).
- **Alembic** conectado a `Base.metadata` (`app/database.py`) y a `DATABASE_URL` (`app/config.py`).

Migraciones aplicadas hoy en la base real:

1. `dd9d1878d96d` — esquema inicial (todas las tablas de [`doc/schem_posgrest.sql`](doc/schem_posgrest.sql)).
2. `5e0ac9f7b8ed` — tabla de auditoría `poi_moderaciones`.

```bash
alembic current        # ver el estado real de la base
```

Flujo normal para un cambio de schema (detallado con ejemplos en [`doc/guia_orm_alembic.md`](doc/guia_orm_alembic.md)):

```bash
alembic revision --autogenerate -m "descripción del cambio"
alembic upgrade head
```

---

## 🛠️ Technologies

| Category       | Technologies                                  |
|-----------------|------------------------------------------------|
| Framework       | FastAPI                                        |
| Language        | Python 3.12                                    |
| ORM / Migrations| SQLAlchemy 2.x + Alembic                       |
| Database        | PostgreSQL (Neon) + PostGIS                    |
| Auth            | python-jose + passlib (JWT propio, bcrypt)     |
| Media Storage   | Cloudinary                                     |
| Scheduling      | APScheduler (in-process, sin `pg_cron`)        |
| Testing         | pytest + httpx                                 |
| Containerization| Docker + Docker Compose                        |

---

## 🚀 How to Run

### Requisitos previos

- Docker y Docker Compose (para correrlo en contenedor), **o** Python 3.12 (para correrlo local sin Docker).
- Acceso a una base de datos PostgreSQL con PostGIS habilitado (se usa Neon en este proyecto).

### Configuración

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

   `.env` está en `.gitignore` — nunca se commitea. `.env.example` sí se commitea y **no** debe tener secretos reales.

### Con Docker (recomendado)

```bash
docker compose up --build
```

- La API queda disponible en `http://localhost:8000`.
- El contenedor corre con `--reload` y el código local está montado como volumen (`.:/app`): cualquier cambio en tu editor se refleja al instante, sin reconstruir la imagen.
- Para detenerlo: `docker compose down`.
- Solo hace falta reconstruir (`docker compose up --build`) cuando cambian `requirements.txt` o el `Dockerfile`.

### Sin Docker (local)

```bash
python3 -m venv .venv
source .venv/bin/activate        # en Windows: .venv\Scripts\activate
pip install -r requirements.txt

# si no tienes .env todavía: cp .env.example .env y complétalo (ver sección "Configuración")

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 📚 API Documentation

Con la app corriendo (por cualquiera de los dos métodos):

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health check: `http://localhost:8000/health`

Todas las rutas de negocio cuelgan del prefijo `/api/v1`. Cómo se monta cada router en [`app/main.py`](app/main.py):

| Router | Prefijo | Tag | Paths de ejemplo |
|---|---|---|---|
| `auth.py` | `/auth` | `auth` | `/register`, `/login` |
| `catalogos.py` | *(ninguno)* | `catalogs` | `/countries`, `/departments`, `/cities`, `/poi-categories` |
| `poi.py` | `/poi` | `poi` | `/`, `/{poi_id}`, `/{poi_id}/checkin` |
| `social.py` | *(ninguno)* | `social` | `/poi/{poi_id}/my-rating`, `/favorites`, `/comments/{id}` |
| `usuarios.py` | `/users` | `users` | `/me`, `/me/photo` |
| `visitas.py` | `/visits` | *(sin tag)* | `/`, `/me`, `/me/balance` |
| `recompensas.py` | `/rewards` | `rewards` | listado y gestión de recompensas |
| `canjes.py` | `/redemptions` | `redemptions` | canje y validación QR física |
| `comercial.py` | *(ninguno)* | `businesses` | `/businesses`, `/businesses/{id}/purchases`, `/poi/{poi_id}/promotions` |
| `retos.py` | *(ninguno)* | `challenges` | `/challenges`, `/challenges/{id}/join`, `/users/me/badges` |
| `puntos.py` | `/points` | *(sin tag)* | `/me/movements` |

Los routers sin prefijo declaran el path completo dentro de cada `@router.get/post/...`. El contrato completo, campo por campo, está en [`doc/endpoints_api.md`](doc/endpoints_api.md).

Documentación más profunda en `doc/`:

| Archivo | Qué cubre |
|---|---|
| [`doc/endpoints_api.md`](doc/endpoints_api.md) | **Contrato completo de la API** — todos los endpoints implementados, con auth, body, response real y notas de qué difiere del diseño original. |
| [`doc/auth_usuarios_api.md`](doc/auth_usuarios_api.md) | Detalle fino de `/auth` y `/users` (claims del JWT, reglas de cada campo, cobertura de tests). |
| [`doc/logica_negocio.md`](doc/logica_negocio.md) | Qué hace cada tabla, qué invariantes garantiza la base de datos (`CHECK`s, triggers, columnas generadas) y cómo fluyen los procesos de negocio de punta a punta. |
| [`doc/schem_posgrest.sql`](doc/schem_posgrest.sql) | El DDL completo de referencia (33 tablas, triggers, vistas). |
| [`doc/guia_orm_alembic.md`](doc/guia_orm_alembic.md) | Cómo trabajar con SQLAlchemy + Alembic en este proyecto: comandos, flujo para modificar el schema, errores comunes. |

---

## 🧪 Tests

```bash
pytest
```

(requiere tener el entorno virtual activado y las dependencias instaladas, ver sección "Sin Docker" arriba)

⚠️ **`pytest` borra todos los datos de la base configurada en `DATABASE_URL`.** No hay una base de test separada — la suite corre contra la misma Neon real de `.env`. El fixture `_schema` (session-scoped, autouse, en `tests/conftest.py`) ejecuta `TRUNCATE {tabla} CASCADE` sobre **las 33 tablas del schema, una sola vez al arrancar la sesión de tests**, antes de que corra un solo test. Después de ese truncado inicial, cada test individual sí queda aislado (el fixture `db` corre dentro de una transacción con `rollback()` al final) — pero ese primer `TRUNCATE` es real e irreversible. **Nunca corras `pytest` apuntando `DATABASE_URL` a una base con datos que te importen.** Usá una base descartable (una branch de Neon, por ejemplo) — nunca la de desarrollo compartida.

---

## 📊 Project Status

Todos los módulos de negocio del diseño original están implementados y probados end-to-end contra la base real: catálogos (países/departamentos/ciudades/categorías), POI (con moderación, imágenes y check-in QR), usuarios (con foto de perfil), social (calificaciones/comentarios/favoritos), visitas (GPS/QR/MIXTA), recompensas y canjes (con validación QR física), comercial (establecimientos/compras/promociones, con autorización real por pertenencia), retos (plantillas, inscripción, progreso, rachas, hitos, insignias) y puntos (historial del ledger).

El detalle endpoint por endpoint, incluidas las decisiones que no estaban en el diseño original y los gaps conocidos, vive en [`doc/endpoints_api.md`](doc/endpoints_api.md) — ese documento es la fuente de verdad más actualizada, más que este README.

Pendiente conocido:

- **Relaciones entre POIs** (`poi_relaciones` / `tipos_relacion_poi`) — modelo ORM ya existe (`app/models/poi.py`), catálogo de tipos ya sembrado (`app/scripts/seed_tipos_relacion_poi.py`), pero **sin router todavía**.
- **IA conversacional** (`conversaciones_ia`) — modelo ORM ya existe (`app/models/ia.py`, log de turnos con `session_id`, `modelo`, `tokens`, `costo_usd`, etc.), **sin router todavía**.
- Tracking punto-a-punto en vivo de los retos tipo `RECORRIDO`, no bloqueante (`sesiones_reto` solo guarda el marco inicio/fin/estado, sin coordenadas — el diseño original lo pensaba con Redis, todavía no implementado).

`app/routers/promociones.py` es un archivo vacío sin uso — no confundir con el módulo de promociones real, que vive dentro de `comercial.py`/`comercial_service.py`.

---

## 🎯 Academic Objectives

Este proyecto cumple con:

✔ Arquitectura en capas (Router → Service → Repository → Model)
✔ Modelado geoespacial con PostGIS
✔ Autenticación y autorización con JWT
✔ Diseño de un sistema de gamificación completo (retos, rachas, insignias, puntos)
✔ Migraciones versionadas con Alembic
✔ Buenas prácticas de backend con FastAPI
✔ Documentación técnica completa (API, lógica de negocio, esquema de base de datos)
