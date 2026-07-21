# 🗺️ TourPoints — Backend 🧑‍💻

Backend API for **TourPoints**, a gamified tourism app: users discover points of interest (POIs), visit them, shop at partner businesses, and complete challenges — all of which earns points redeemable for rewards.

This repository is **backend only**. The frontend lives in a separate repository.

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

This project is the backend of a gamified tourism platform, built as part of the Riwi program's integrative project.

The main goal is to apply:

- Layered architecture (Router → Service → Repository → Model)
- Geospatial modeling with PostGIS
- Authentication and authorization with JWT
- Complex business rules (gamification, points ledger, moderation)
- Backend best practices with FastAPI and SQLAlchemy

The system includes:

- User authentication and management (with profile photo)
- Geographic catalog (countries, departments, cities) and POI categories
- Point-of-interest (POI) management with moderation and images
- Social interaction (ratings, comments, favorites)
- Visit check-in via GPS, QR, or a mixed method
- Rewards and redemptions, including physical QR validation at the redemption point
- Business module (partner establishments, purchases, promotions)
- Challenges module (challenges, streaks, milestones, badges)
- Points history via an append-only ledger

---

## ✨ Features

### 🔐 Authentication & Users
- Register/login with JWT (`python-jose` + `passlib`)
- Roles: `admin`, `usuario`, `establecimiento`
- Own profile, password change, profile photo via Cloudinary

### 🗺️ POIs & Geolocation
- Location using PostGIS geographic types (`Geography(Point,4326)`)
- Moderation flow (`BORRADOR` → `PENDIENTE` → `APROBADO`/`RECHAZADO`)
- Multiple images per POI, with a primary image
- Check-in QR code per POI (deterministic HMAC, no DB storage)

### 🎮 Gamification
- Challenges with recurrence (one-time, daily, weekly, monthly)
- Streaks with gap detection and automatic milestones
- Badges awarded upon reaching streak milestones
- Rewards with `GARANTIZADA` / `LIMITADA` modes, redeemable via QR

### 🏪 Business Module
- Establishments affiliated with an owned POI, with moderation
- Purchase logging with automatic points crediting
- Purchase reversal via compensating entry (the ledger is never edited)
- Promotions with validity window (`inicio`/`fin`) and moderation

### 🧱 Architecture & Quality
- Strict Router / Service / Repository / Model separation
- Authorization based on actual ownership (`establecimiento_usuarios`), not just global role
- Domain exceptions with centralized HTTP handlers
- Swagger/OpenAPI documentation in English, JSON fields in Spanish (consistent with the DB)

---

## 📁 Project Structure

```
TourPoints-Backend/
├── app/
│   ├── main.py              # builds the FastAPI app, mounts routers under /api/v1, CORS, startup/shutdown
│   ├── config.py            # Settings (pydantic-settings), reads .env
│   ├── database.py          # engine, SessionLocal, declarative Base, get_db()
│   ├── auth/                 # JWT + password hashing
│   ├── core/                 # exceptions, handlers, middleware, scheduler
│   ├── routers/               # 1 file per domain: auth, catalogos, poi, social,
│   │                          # usuarios, visitas, recompensas, canjes, comercial, retos, puntos
│   ├── services/               # business rules, 1 file per domain (mirrors routers)
│   ├── repositories/           # SQLAlchemy data access, 1 file per domain
│   ├── models/                 # ORM: usuario, poi, ubicacion, social, visita, comercial,
│   │                          # gamificacion (challenges/badges/streaks), canje, movimiento_puntos, ia, enums
│   ├── schemas/                 # Pydantic DTOs, request/response
│   ├── utils/                   # geo.py, qr.py, media.py
│   └── scripts/                 # idempotent seeds (roles, tipos_relacion_poi, insignias)
│
├── alembic/                      # migrations (env.py wired to Base.metadata and DATABASE_URL)
│   └── versions/                  # dd9d1878d96d (initial schema), 5e0ac9f7b8ed (poi_moderaciones)
│
├── tests/                         # pytest — see Tests section, ⚠️ truncates the DATABASE_URL database
├── doc/                            # in-depth documentation (see table in API Documentation)
├── scripts/                        # manual smoke tests outside the app (not seeds)
├── docker-compose.yml, Dockerfile
├── requirements.txt
├── alembic.ini
└── .env.example
```

> **Note:** two pieces of the schema have an ORM model but **no endpoint yet**: relationships between POIs (`poi_relaciones` / `tipos_relacion_poi`) and conversational AI (`conversaciones_ia`). `app/routers/promociones.py` is an unused empty file — the real promotions are served from `app/routers/comercial.py`. Details in [`doc/auth_usuarios_api.md`](doc/auth_usuarios_api.md).

---

## 🏗️ Architecture

The project follows a layered architecture:

```
Router (FastAPI)  →  Service            →  Repository        →  Model (SQLAlchemy ORM)
   │                     │                      │
   └─ Schema (Pydantic)  └─ business rules       └─ pure data
      validates HTTP        the DB doesn't          access, no
      request/response      guarantee                business logic
```

- **`app/routers/`** — HTTP endpoints, no business logic.
- **`app/services/`** — orchestrate repositories and apply business rules.
- **`app/repositories/`** — data access with SQLAlchemy.
- **`app/models/`** — ORM mapping, one file per domain (not per table).
- **`app/schemas/`** — Pydantic DTOs for request/response.
- **`app/auth/`** — `security.py` (bcrypt hashing, JWT) and `dependencies.py` (`get_current_user`, `get_admin_user`, `get_optional_user`, etc.).
- **`app/core/`** — `exceptions.py` + `exception_handlers.py` (domain exceptions and their HTTP handlers), `scheduler.py` (in-process periodic job), and `middleware.py` (`JWTMiddleware`, which despite the name only logs each request; actual JWT validation lives in `app/auth/dependencies.py`).
- **`app/utils/`** — `geo.py` (GPS distance), `qr.py` (redemption and check-in codes), `media.py` (image validation).

---

## ⚡ Business Logic & Security

Key points of the implemented business logic:

- **Append-only points ledger** (`movimientos_puntos`): an entry is never edited or deleted; reversals (e.g. canceling a purchase) are done with a compensating negative entry.
- **Authorization by actual ownership**: endpoints like `POST /redemptions/validate-qr` verify membership in `establecimiento_usuarios`, not just the token's global role.
- **Visit check-in** via GPS (distance computed with PostGIS `ST_DWithin`/`ST_Distance`), via QR (deterministic per-POI HMAC code), or `MIXTA` (both at once).
- **Redemption QR vs. check-in QR**: reward redemption uses a random token stored in the DB; POI check-in is deterministic (HMAC) and requires no storage.
- **Challenge gamification**: period calculation based on recurrence, streak gap detection, automatic milestone/badge awarding, and a two-phase flow on challenge completion (points/streak/milestones are confirmed even if a `LIMITADA` reward redemption fails due to stock).
- **In-process periodic job** (`APScheduler`, not `pg_cron` — unavailable on the Neon plan used) that expires overdue challenges every hour.

---

## 🗄️ Database & Migrations

- **PostgreSQL (Neon)** with the **PostGIS** extension enabled (POIs use `Geography(Point,4326)`).
- **Alembic** wired to `Base.metadata` (`app/database.py`) and `DATABASE_URL` (`app/config.py`).

Migrations currently applied to the real database:

1. `dd9d1878d96d` — initial schema (all tables from [`doc/schem_posgrest.sql`](doc/schem_posgrest.sql)).
2. `5e0ac9f7b8ed` — `poi_moderaciones` audit table.

```bash
alembic current        # check the database's actual state
```

Normal workflow for a schema change (detailed with examples in [`doc/guia_orm_alembic.md`](doc/guia_orm_alembic.md)):

```bash
alembic revision --autogenerate -m "change description"
alembic upgrade head
```

---

## 🛠️ Technologies

| Category        | Technologies                                   |
|-----------------|-------------------------------------------------|
| Framework       | FastAPI                                        |
| Language        | Python 3.12                                    |
| ORM / Migrations| SQLAlchemy 2.x + Alembic                       |
| Database        | PostgreSQL (Neon) + PostGIS                    |
| Auth            | python-jose + passlib (own JWT, bcrypt)        |
| Media Storage   | Cloudinary                                     |
| Scheduling      | APScheduler (in-process, no `pg_cron`)         |
| Testing         | pytest + httpx                                 |
| Containerization| Docker + Docker Compose                        |

---

## 🚀 How to Run

### Prerequisites

- Docker and Docker Compose (to run it in a container), **or** Python 3.12 (to run it locally without Docker).
- Access to a PostgreSQL database with PostGIS enabled (this project uses Neon).

### Setup

1. If this is your first time cloning the repo (you don't have a `.env` yet), copy the template:

   ```bash
   cp .env.example .env
   ```

   ⚠️ If you already have a `.env` with real credentials, **do not** run this — it would overwrite them.

2. Fill in `.env` with your real values:

   | Variable | Description |
   |---|---|
   | `DATABASE_URL` | Postgres connection string (Neon → Dashboard → Connection Details) |
   | `SECRET_KEY` | Key used to sign JWTs. Generate your own: `openssl rand -hex 32` — **never reuse the example value** |
   | `ALGORITHM` | JWT signing algorithm (`HS256` by default) |
   | `ACCESS_TOKEN_EXPIRE_MINUTES` | Token validity in minutes (`60` by default). No refresh token yet — once it expires, the client must log in again |
   | `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` | Cloudinary credentials (Dashboard → Account Details). **Required** — `app/config.py` has no default for these three, the app won't start without them |

   `.env` is in `.gitignore` — it's never committed. `.env.example` is committed and **must not** contain real secrets.

### With Docker (recommended)

```bash
docker compose up --build
```

- The API becomes available at `http://localhost:8000`.
- The container runs with `--reload` and the local code is mounted as a volume (`.:/app`): any change in your editor is reflected instantly, no image rebuild needed.
- To stop it: `docker compose down`.
- You only need to rebuild (`docker compose up --build`) when `requirements.txt` or the `Dockerfile` change.

### Without Docker (local)

```bash
python3 -m venv .venv
source .venv/bin/activate        # on Windows: .venv\Scripts\activate
pip install -r requirements.txt

# if you don't have a .env yet: cp .env.example .env and fill it in (see "Setup" section)

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 📚 API Documentation

With the app running (either method above):

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health check: `http://localhost:8000/health`

All business routes hang off the `/api/v1` prefix. How each router is mounted in [`app/main.py`](app/main.py):

| Router | Prefix | Tag | Example Paths |
|---|---|---|---|
| `auth.py` | `/auth` | `auth` | `/register`, `/login` |
| `catalogos.py` | *(none)* | `catalogs` | `/countries`, `/departments`, `/cities`, `/poi-categories` |
| `poi.py` | `/poi` | `poi` | `/`, `/{poi_id}`, `/{poi_id}/checkin` |
| `social.py` | *(none)* | `social` | `/poi/{poi_id}/my-rating`, `/favorites`, `/comments/{id}` |
| `usuarios.py` | `/users` | `users` | `/me`, `/me/photo` |
| `visitas.py` | `/visits` | *(no tag)* | `/`, `/me`, `/me/balance` |
| `recompensas.py` | `/rewards` | `rewards` | listing and managing rewards |
| `canjes.py` | `/redemptions` | `redemptions` | redemption and physical QR validation |
| `comercial.py` | *(none)* | `businesses` | `/businesses`, `/businesses/{id}/purchases`, `/poi/{poi_id}/promotions` |
| `retos.py` | *(none)* | `challenges` | `/challenges`, `/challenges/{id}/join`, `/users/me/badges` |
| `puntos.py` | `/points` | *(no tag)* | `/me/movements` |

Routers without a prefix declare the full path inside each `@router.get/post/...`. The full contract, field by field, is in [`doc/endpoints_api.md`](doc/endpoints_api.md).

More in-depth documentation in `doc/`:

| File | What it covers |
|---|---|
| [`doc/endpoints_api.md`](doc/endpoints_api.md) | **Full API contract** — every implemented endpoint, with auth, body, actual response, and notes on what differs from the original design. |
| [`doc/auth_usuarios_api.md`](doc/auth_usuarios_api.md) | Fine detail on `/auth` and `/users` (JWT claims, per-field rules, test coverage). |
| [`doc/logica_negocio.md`](doc/logica_negocio.md) | What each table does, what invariants the database guarantees (`CHECK`s, triggers, generated columns), and how business processes flow end to end. |
| [`doc/schem_posgrest.sql`](doc/schem_posgrest.sql) | The full reference DDL (33 tables, triggers, views). |
| [`doc/guia_orm_alembic.md`](doc/guia_orm_alembic.md) | How to work with SQLAlchemy + Alembic in this project: commands, workflow for schema changes, common errors. |

---

## 🧪 Tests

```bash
pytest
```

(requires the virtual environment activated and dependencies installed, see the "Without Docker" section above)

⚠️ **`pytest` deletes all data in the database configured in `DATABASE_URL`.** There is no separate test database — the suite runs against the same real Neon database from `.env`. The `_schema` fixture (session-scoped, autouse, in `tests/conftest.py`) runs `TRUNCATE {table} CASCADE` on **all 33 tables in the schema, once when the test session starts**, before a single test runs. After that initial truncate, each individual test is isolated (the `db` fixture runs inside a transaction with `rollback()` at the end) — but that first `TRUNCATE` is real and irreversible. **Never run `pytest` pointing `DATABASE_URL` at a database with data you care about.** Use a disposable database (a Neon branch, for example) — never the shared development one.

---

## 📊 Project Status

All business modules from the original design are implemented and tested end-to-end against the real database: catalogs (countries/departments/cities/categories), POI (with moderation, images, and QR check-in), users (with profile photo), social (ratings/comments/favorites), visits (GPS/QR/MIXTA), rewards and redemptions (with physical QR validation), business (establishments/purchases/promotions, with real ownership-based authorization), challenges (templates, enrollment, progress, streaks, milestones, badges), and points (ledger history).

The endpoint-by-endpoint detail, including decisions not in the original design and known gaps, lives in [`doc/endpoints_api.md`](doc/endpoints_api.md) — that document is the most up-to-date source of truth, more so than this README.

Known pending work:

- **Relationships between POIs** (`poi_relaciones` / `tipos_relacion_poi`) — the ORM model already exists (`app/models/poi.py`), the type catalog is already seeded (`app/scripts/seed_tipos_relacion_poi.py`), but there's **no router yet**.
- **Conversational AI** (`conversaciones_ia`) — the ORM model already exists (`app/models/ia.py`, turn log with `session_id`, `modelo`, `tokens`, `costo_usd`, etc.), **no router yet**.
- Live point-by-point tracking for `RECORRIDO`-type challenges, non-blocking (`sesiones_reto` only stores the start/end/status frame, no coordinates — the original design planned this with Redis, not yet implemented).

`app/routers/promociones.py` is an unused empty file — don't confuse it with the real promotions module, which lives inside `comercial.py`/`comercial_service.py`.

---

## 🎯 Academic Objectives

This project fulfills:

✔ Layered architecture (Router → Service → Repository → Model)
✔ Geospatial modeling with PostGIS
✔ Authentication and authorization with JWT
✔ Design of a complete gamification system (challenges, streaks, badges, points)
✔ Versioned migrations with Alembic
✔ Backend best practices with FastAPI
✔ Complete technical documentation (API, business logic, database schema)

