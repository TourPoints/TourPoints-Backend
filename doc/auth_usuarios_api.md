# Autenticación y Usuarios — referencia de la API implementada

> Documenta con más detalle lo que existe en `app/routers/auth.py` y `app/routers/usuarios.py` — claims del JWT, reglas campo por campo, cobertura de tests. `doc/endpoints_api.md` ya está al día para todos los módulos (incluido este), pero acá hay nivel de detalle que no vale la pena repetir ahí. Ante cualquier discrepancia entre ambos, el código es la fuente de verdad; entre este documento y `endpoints_api.md`, el que tenga la fecha de actualización más reciente.

## Cambios recientes (2026-07-17)

- **Paginación de `/users` unificada con el resto de la API:** `GET /users` dejó de aceptar `skip`/`limit` con respuesta en lista plana. Ahora usa `page`/`page_size` y devuelve el mismo sobre `{items, total, page, page_size}` que `/poi`, `/cities`, etc. (`GET /users/count` no cambió, sigue siendo un entero suelto).
- **Foto de perfil real:** se agregaron `POST /users/me/photo` (sube a Cloudinary, reemplaza `foto_url`) y `DELETE /users/me/photo` (la quita). Antes `foto_url` solo se podía setear pegando una URL arbitraria vía `PATCH /users/me` — ver [§3](#3-apiv1users).
- **Gestión de roles por el admin:** `UsuarioCreate` y `UsuarioUpdate` aceptan `rol_id` opcional. Un admin puede asignarlo al crear (`POST /users`) o editar (`PATCH /users/{id}`) cualquier usuario, incluyendo crear otro admin. Sigue sin poder tocarse desde `POST /auth/register` ni `PATCH /users/me` — ver [§4](#4-esquemas-pydantic).
- **Eliminado `GET /auth/me`** por ser un duplicado de `GET /users/me` (mismo `current_user`, distinto — y más limitado — schema de respuesta). Se retiró junto con el schema `UsuarioProfileResponse`. Usar `GET /users/me`.
- **Tabla `roles` sembrada** en la BD real vía `app/scripts/seed_roles.py`: `1=admin`, `2=usuario`, `3=establecimiento`.

## Índice

1. [Convenciones](#1-convenciones)
2. [`/api/v1/auth`](#2-apiv1auth)
3. [`/api/v1/users`](#3-apiv1users)
4. [Esquemas (Pydantic)](#4-esquemas-pydantic)
5. [Cobertura de tests](#5-cobertura-de-tests)
6. [Estado del resto de la API](#6-estado-del-resto-de-la-api)

---

## 1. Convenciones

- **Base URL:** `/api/v1` (`app/main.py`).
- **Auth:** header `Authorization: Bearer <token>`. JWT firmado HS256 (`app/config.py`: `secret_key`, `algorithm`, `access_token_expire_minutes`, default 60 min). No hay refresh token.
- **Claims del token:** `sub` (UUID del usuario), `role` (`"admin"` si `rol_id == 1`, si no `"user"`), `status` (`estado` del usuario), `iat`, `exp`.
- **Roles:** `roles.id`: `1 = admin`, `2 = usuario`, `3 = establecimiento` (ver `app/scripts/seed_roles.py`). La autorización de endpoints de administrador exige `rol.nombre.lower() == "admin"`, resuelto en cada request contra la tabla `roles` (`get_admin_user`).
- **Estados de usuario:** `ACTIVO | SUSPENDIDO | ELIMINADO`. `get_current_user` rechaza con `403` cualquier token válido de un usuario no `ACTIVO` o con `deleted_at` seteado, aunque el JWT no haya expirado.
- **Errores:** `{"detail": "mensaje"}` para 4xx de negocio; `422` con el formato estándar de validación de FastAPI/Pydantic.

---

## 2. `/api/v1/auth`

### `POST /auth/register`
**Auth:** pública.

Body (`UsuarioCreate`):
```json
{ "nombre": "Camila", "apellido": "Restrepo", "email": "camila@example.com", "telefono": "3001234567", "password": "Sup3rSegura!" }
```
- `password` se hashea con bcrypt antes de guardar (nunca se persiste ni se devuelve en texto plano).
- El rol se asigna en backend: busca el rol `"usuario"` (case-insensitive); si no existe en la tabla `roles`, cae a `rol_id = 2`. **El schema `UsuarioCreate` acepta `rol_id`, pero este endpoint lo ignora explícitamente** (`model_dump(exclude={"password", "rol_id"})`) — no hay forma de auto-asignarse un rol distinto de "usuario" vía registro público, sin importar qué envíe el cliente.

Respuesta `201` (`UsuarioResponse`, sin `password_hash`). Errores: `400` si el email ya existe.

### `POST /auth/login`
**Auth:** pública.

Body (`UsuarioLogin`): `{"email": "...", "password": "..."}`

Reglas de `authenticate_user` (en orden): usuario debe existir y no tener `deleted_at`, `estado == "ACTIVO"`, password correcta. Cualquier fallo en cualquiera de esos pasos devuelve el mismo `401 Credenciales inválidas` — no se distingue "usuario no existe" de "contraseña incorrecta" para no filtrar qué emails están registrados.

Respuesta `200` (`Token`): `{"access_token": "...", "token_type": "bearer"}`.

---

## 3. `/api/v1/users`

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| `POST` | `/users` | admin | Crea un usuario. `rol_id` por defecto `2` ("usuario") si no se envía; el admin puede especificar cualquier rol, incluido `1` (admin) |
| `GET` | `/users` | admin | Lista paginada (`page`/`page_size`) con filtros |
| `GET` | `/users/count` | admin | Cuenta con los mismos filtros que la lista |
| `GET` | `/users/me` | autenticado | Perfil propio completo |
| `PATCH` | `/users/me` | autenticado | Auto-edición parcial |
| `PATCH` | `/users/me/password` | autenticado | Cambio de contraseña propia |
| `POST` | `/users/me/photo` | autenticado | Sube/reemplaza la foto de perfil (`multipart/form-data`) |
| `DELETE` | `/users/me/photo` | autenticado | Quita la foto de perfil |
| `POST` | `/users/{id}/activate` | admin | `estado → ACTIVO`, limpia `deleted_at` |
| `POST` | `/users/{id}/suspend` | admin | `estado → SUSPENDIDO` |
| `GET` | `/users/{id}` | admin | Detalle de un usuario |
| `PATCH` | `/users/{id}` | admin | Edición parcial de cualquier usuario |
| `DELETE` | `/users/{id}` | admin | Soft delete por defecto (`?soft=false` = hard delete) |

Notas relevantes que no son obvias leyendo solo las rutas:

- **`GET /users`** acepta `page` (≥1, default 1), `page_size` (1-100, default 20), y filtros opcionales `name`, `surname`, `email` (`ILIKE`, parciales), `estado`, `rol_id` (match exacto), `include_deleted`. Responde `{"items": [...], "total": N, "page": 1, "page_size": 20}`. Con `include_deleted=false` (default), excluye filas con `deleted_at` seteado. **`GET /users/count`** acepta los mismos filtros salvo paginación y devuelve un entero suelto, no el sobre.
- **`PATCH /users/me`**: si el body trae `email`, valida que no pertenezca a otro usuario (`409` si choca); si trae `password`, la rehashea. Solo aplica los campos presentes (`exclude_unset`). **`rol_id` se descarta explícitamente del payload antes de aplicarlo**, aunque `UsuarioUpdate` lo acepte como campo — un usuario nunca puede cambiar su propio rol por esta vía, solo un admin vía `PATCH /users/{id}`.
- **`PATCH /users/me/password`** (`ChangePasswordRequest`): requiere `current_password` correcta (`400` si no coincide) y `new_password` (mín. 8 caracteres, `422` si falta o es corta). Responde `204` sin body.
- **`POST /users/me/photo`**: `file` debe ser `image/jpeg`, `image/png` o `image/webp` (`422` si no). Sube a Cloudinary (`tourpoints/usuarios/{id}/`) y guarda solo la `secure_url` en `foto_url` — la BD nunca tiene el binario. Si ya había una foto, borra el asset anterior en Cloudinary (best-effort: si ese borrado falla, no bloquea la subida de la nueva).
- **`DELETE /users/me/photo`**: borra el asset en Cloudinary (si había uno) y deja `foto_url = null`. Idempotente — llamarlo sin tener foto no da error.
- **`POST /{id}/activate` y `/suspend`**: devuelven `404` si el `id` no existe.
- **`PATCH /{id}` y `DELETE /{id}`**: mismas reglas que sus versiones `/me` pero operando sobre cualquier usuario; requieren rol admin. A diferencia de `/me`, `PATCH /{id}` sí aplica `rol_id` si viene en el body — es la única vía para cambiar el rol de un usuario (incluido convertirlo en admin).
- El orden de declaración de rutas importa: `/count`, `/me` y `/me/photo` están registradas **antes** que `/{user_id}` en `app/routers/usuarios.py`, evitando que FastAPI intente resolver `"count"` o `"me"` como un UUID.

---

## 4. Esquemas (Pydantic)

| Esquema | Uso | Campos |
|---|---|---|
| `UsuarioCreate` | body de `register` / `POST /users` | `nombre`, `apellido`, `email`, `telefono?`, `password` (8-100), `rol_id?` (solo respetado en `POST /users`, ignorado en `register`) |
| `UsuarioLogin` | body de `login` | `email`, `password` |
| `Token` | respuesta de `login` | `access_token`, `token_type` |
| `UsuarioResponse` | respuesta con datos completos (sin password) | `id`, `nombre`, `apellido`, `email`, `telefono`, `rol_id`, `estado`, `foto_url`, `configuracion`, `created_at`, `updated_at`, `deleted_at` |
| `UsuarioUpdate` | body de `PATCH /users/me` y `PATCH /users/{id}` | todos los campos de `UsuarioCreate` opcionales + `foto_url?`, `estado?`, `configuracion?`, `rol_id?` (solo respetado en `PATCH /users/{id}`, descartado en `/me`) |
| `ChangePasswordRequest` | body de `PATCH /users/me/password` | `current_password`, `new_password` (8-100) |
| `PaginatedUsuariosResponse` | respuesta de `GET /users` | `items: UsuarioResponse[]`, `total`, `page`, `page_size` |

`POST /users/me/photo` y `DELETE /users/me/photo` no tienen schema de body propio (multipart el primero, sin body el segundo) — ambos responden `UsuarioResponse` completo, igual que `GET /users/me`.

---

## 5. Cobertura de tests

Suite en `tests/test_auth_endpoints.py`, `tests/test_auth_users.py` y `tests/test_users_endpoints.py` — **46 tests**, todos contra una base de datos Postgres real (no mocks), vía `TestClient` de FastAPI. Ejecución: `docker exec tourpoints_app python -m pytest tests/test_auth_endpoints.py tests/test_auth_users.py tests/test_users_endpoints.py`.

### `/auth` — 11 tests (`test_auth_endpoints.py` + `test_auth_users.py`)

| Endpoint | Casos cubiertos |
|---|---|
| `POST /auth/register` | éxito; email duplicado (`400`); campos faltantes (`422`); email inválido (`422`); password corta (`422`) |
| `POST /auth/login` | éxito con token; credenciales inválidas (`401`); usuario inexistente (`401`); usuario con `deleted_at` (`401`); usuario `SUSPENDIDO` (`401`) |
| `authenticate_user` (unitario, sin BD) | rechaza usuarios no `ACTIVO` (`test_auth_users.py`) |

> `GET /auth/me` se eliminó (era duplicado de `GET /users/me`); sus 3 tests se retiraron con él — la cobertura equivalente vive en `GET /users/me` (tabla de abajo).

### `/users` — 35 tests (`test_users_endpoints.py`)

| Endpoint | Casos cubiertos |
|---|---|
| `POST /users` | admin crea; usuario regular rechazado (`403`); sin auth (`403`); email duplicado (`400`) |
| `GET /users` | admin lista; regular rechazado; sin auth; paginación; filtro por email |
| `GET /users/count` | admin cuenta; regular rechazado; sin auth |
| `GET /users/me` | autenticado ve su perfil; sin auth (`403`) |
| `PATCH /users/me` | actualiza nombre/teléfono; cambia email único; rechaza email duplicado (`409`); sin auth (`403`) |
| `PATCH /users/me/password` | éxito (`204`); contraseña actual incorrecta (`400`); campo faltante (`422`); sin auth (`403`) |
| `GET /users/{id}` | admin obtiene; regular rechazado; id inexistente (`404`); sin auth |
| `DELETE /users/{id}` | admin elimina (`204`); regular rechazado; id inexistente (`404`) |
| `POST /users/{id}/suspend` | admin suspende y persiste el cambio; regular rechazado; id inexistente (`404`) |
| `POST /users/{id}/activate` | admin activa un usuario suspendido; regular rechazado; id inexistente (`404`) |
| `PATCH /users/{id}` (admin sobre otro usuario) | **sin cobertura** — solo está testeado el equivalente `/me`. Incluye la asignación de `rol_id` (crear/ascender a admin), también sin test |
| `POST /users` con `rol_id` explícito | **sin cobertura** — solo está testeado el default (`rol_id=2`) |
| `POST /users/me/photo`, `DELETE /users/me/photo` | **sin cobertura en la suite de pytest** — se validaron manualmente end-to-end contra Cloudinary y la BD real (subida, reemplazo con borrado del asset anterior confirmado vía `cloudinary.api.resource`, formato no permitido, borrado, doble-borrado idempotente), pero no hay tests automatizados todavía |

### Diseño del fixture de BD (`tests/conftest.py`)

- `DATABASE_URL` se toma de `.env` — **no** hay credenciales hardcodeadas en el archivo (antes sí las había, se corrigió).
- La fixture `_schema` (session-scoped, autouse) crea el esquema y trunca las 30 tablas **una sola vez** al inicio de la sesión de tests.
- La fixture `db` (por test) abre una conexión, inicia una transacción externa + un `SAVEPOINT`, y hace `rollback()` de todo al finalizar. Los `commit()` que hacen los endpoints durante el test solo liberan el `SAVEPOINT` interno (vía el listener `after_transaction_end`); nada persiste entre tests. Esto reemplazó el `TRUNCATE CASCADE` de las 30 tablas en cada uno de los tests, que era el cuello de botella real (cada `TRUNCATE` es un round-trip contra la BD remota en Neon): la suite bajó de ~450s a ~90s.
- `client` sobreescribe `get_db` para inyectar esa misma sesión en cada request del `TestClient`.

---

## 6. Estado del resto de la API

Este documento cubre solo `/auth` y `/users`. Para el contrato completo de los demás módulos (POI, catálogos, social, visitas, recompensas, canjes, comercial, retos, puntos) — incluidos cuáles gaps siguen abiertos hoy — ver [`doc/endpoints_api.md`](endpoints_api.md), que es el documento que se mantiene actualizado en cada cambio. Al momento de esta revisión, los únicos módulos genuinamente sin endpoints son **relaciones entre POIs** (`poi_relaciones`/`tipos_relacion_poi`) e **IA conversacional** (`conversaciones_ia`) — ambos con modelo ORM ya existente, sin router. Todo lo demás (incluidos Retos, Comercial y Canjes, que en algún momento estuvieron completamente vacíos) ya está implementado.