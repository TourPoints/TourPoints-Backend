# TOURPOINTS — Diseño de endpoints de la API

> Contrato REST de `TourPoints-Backend`, derivado del esquema real (`doc/schem_posgrest.sql`) y de la lógica de negocio documentada en `doc/logica_negocio.md`. Para cada endpoint se indica: quién puede llamarlo, qué debe enviar el frontend (path/query params y body) y un ejemplo de la respuesta.
>
> Este documento mezcla dos cosas y cada sección lo indica explícitamente:
> - ✅ **Implementado** — el código en `app/routers/*.py` existe, fue probado end-to-end contra la base real y el shape documentado es el que realmente devuelve la API (cualquier diferencia respecto al diseño original quedó anotada).
> - 🚧 **Pendiente** — sigue siendo la propuesta original, el router es un stub (`app/routers/*.py` con un `# TODO`); el shape es un diseño, no una garantía.

## Índice

1. [Convenciones generales](#1-convenciones-generales)
2. [Autenticación (`/auth`)](#2-autenticación-auth) — ✅ implementado
3. [Usuarios (`/users`)](#3-usuarios-users) — ✅ implementado
4. [Catálogos (`/countries`, `/departments`, `/cities`, `/poi-categories`)](#4-catálogos-countries-departments-cities-poi-categories) — ✅ implementado
5. [POI (`/poi`)](#5-poi-poi) — ✅ implementado
6. [Calificaciones (`/poi/{poi_id}/ratings`)](#6-calificaciones-poipoi_idratings) — ✅ implementado
7. [Comentarios (`/poi/{poi_id}/comments`)](#7-comentarios-poipoi_idcomments) — ✅ implementado
8. [Favoritos (`/favorites`)](#8-favoritos-favorites) — ✅ implementado
9. [Visitas / Check-in (`/visits`)](#9-visitas--check-in-visits) — ✅ implementado
10. [Comercial: establecimientos, compras, promociones](#10-comercial-establecimientos-compras-promociones) — ✅ implementado
11. [Retos (`/challenges`)](#11-retos-challenges) — ✅ implementado
12. [Recompensas (`/rewards`)](#12-recompensas-rewards) — ✅ implementado
13. [Canjes y validación QR (`/redemptions`)](#13-canjes-y-validación-qr-redemptions) — ✅ implementado
14. [Puntos (`/points`)](#14-puntos-points) — ✅ implementado
15. [Gamificación adicional: insignias y rachas](#15-gamificación-adicional-insignias-y-rachas) — ✅ implementado (junto con la sección 11)
16. [Notas y decisiones pendientes](#16-notas-y-decisiones-pendientes)

> **Convención de rutas:** todos los endpoints usan segmentos en inglés (`/cities`, `/favorites`, `/comments/{id}/moderation`...), incluidos los módulos aún no implementados — es el estándar a seguir para cualquier endpoint nuevo. Los nombres de campos dentro del JSON (`nombre`, `estado`, `calificacion`...) siguen en español, igual que las columnas de la base de datos — eso no cambió.

---

## 1. Convenciones generales

- **Base URL:** `/api/v1` (ver `app/main.py`).
- **Content-Type:** `application/json`, salvo subida de imágenes (`multipart/form-data`).
- **Autenticación:** header `Authorization: Bearer <token>`, JWT emitido por `POST /auth/login` (HS256, ver `app/config.py`: `secret_key`, `access_token_expire_minutes`). Hoy **no hay refresh token configurado** — al expirar, el frontend debe volver a hacer login.
- **Roles:** catálogo `roles` (no precargado en el DDL); se asumen `ADMIN`, `USUARIO`, `ESTABLECIMIENTO`. Un usuario puede administrar un establecimiento sin tener `rol_id = ESTABLECIMIENTO` (ver `establecimiento_usuarios` en `doc/logica_negocio.md` módulo 1) — la autorización de rutas "de establecimiento" debe validar esa tabla puente, no solo el rol global.
- **Paginación:** query params `page` (≥1, default 1) y `page_size` (1-100, default 20). Toda lista responde:
  ```json
  { "items": [ /* ... */ ], "total": 137, "page": 1, "page_size": 20 }
  ```
- **Fechas:** ISO-8601 con zona horaria, ej. `"2026-07-14T15:30:00-05:00"` (columnas `TIMESTAMPTZ`).
- **Coordenadas:** el front siempre envía/recibe `{"lat": <float>, "lng": <float>}`; el backend las traduce a `Geography(Point, 4326)` de PostGIS.
- **IDs:** `UUID` (string) en entidades expuestas (`usuarios`, `poi`, `visitas`, `retos`, `canjes`...); entero en catálogos internos (`categorias_poi`, `ciudades`, `roles`).
- **Errores:** formato por defecto de FastAPI.
  - `4xx` genérico: `{"detail": "mensaje"}`
  - `422` de validación: `{"detail": [{"loc": ["body","calificacion"], "msg": "...", "type": "..."}]}`
  - `409` para violaciones de reglas de negocio (stock agotado, calificación duplicada, etc.), siempre con `detail` descriptivo.

---

## 2. Autenticación (`/auth`) — ✅ implementado

Implementado en [app/routers/auth.py](../app/routers/auth.py). Solo tiene estos dos endpoints — no existe `GET /auth/me` (el perfil propio vive en `GET /users/me`, ver sección 3).

### `POST /auth/register`
**Auth:** pública.

Body:
```json
{
  "nombre": "Camila",
  "apellido": "Restrepo",
  "email": "camila@example.com",
  "password": "Sup3rSegura!",
  "telefono": "3001234567"
}
```
Reglas de negocio: `email` único (`usuarios.email UNIQUE`); `password` se hashea con bcrypt/passlib antes de guardar (`password_hash`), nunca se persiste ni se retorna en texto plano. **`rol_id` siempre se fuerza a `usuario` en el backend, sin importar lo que envíe el front** — este endpoint no puede usarse para crear admins ni establecimientos (eso solo lo hace un ADMIN vía `POST /users`, sección 3).

Response `201` (shape real = `UsuarioResponse`, más campos que el diseño original):
```json
{
  "id": "3f1c2a90-6b3e-4c1a-9f2d-7e8b1a2c3d4e",
  "nombre": "Camila",
  "apellido": "Restrepo",
  "email": "camila@example.com",
  "telefono": "3001234567",
  "rol_id": 2,
  "estado": "ACTIVO",
  "foto_url": null,
  "configuracion": {},
  "created_at": "2026-07-14T15:30:00Z",
  "updated_at": "2026-07-14T15:30:00Z",
  "deleted_at": null
}
```
Errores: `400` (no `409`) si el email ya existe — `{"detail": "El email ya está registrado"}`.

### `POST /auth/login`
**Auth:** pública.

Body:
```json
{ "email": "camila@example.com", "password": "Sup3rSegura!" }
```
Response `200` (shape real — **no** incluye `expires_in` ni `usuario`, solo el token):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```
El JWT lleva `sub` (id de usuario), `role` (`"admin"` si `rol_id == 1`, si no `"user"` — no distingue `usuario` de `establecimiento` a nivel de claim) y `status`. El front debe pedir el perfil aparte con `GET /users/me` si necesita `rol_id`/`estado`.

Errores: `401` credenciales inválidas; `403` si `usuarios.estado != ACTIVO` (suspendido/eliminado).

---

## 3. Usuarios (`/users`) — ✅ implementado

Implementado en [app/routers/usuarios.py](../app/routers/usuarios.py). No existen `GET /users/me/points` ni `GET /users/me/redemptions` — dependen de los módulos de Puntos/Canjes, que siguen pendientes (secciones 13-14).

### `GET /users/me`
**Auth:** usuario autenticado.

Response `200` (shape = `UsuarioResponse`, igual al de `POST /auth/register`):
```json
{
  "id": "3f1c2a90-6b3e-4c1a-9f2d-7e8b1a2c3d4e",
  "nombre": "Camila",
  "apellido": "Restrepo",
  "email": "camila@example.com",
  "telefono": "3001234567",
  "rol_id": 2,
  "estado": "ACTIVO",
  "foto_url": null,
  "configuracion": {},
  "created_at": "2026-07-14T15:30:00Z",
  "updated_at": "2026-07-14T15:30:00Z",
  "deleted_at": null
}
```

### `PATCH /users/me`
**Auth:** usuario autenticado. Todos los campos opcionales (`nombre`, `apellido`, `email`, `telefono`, `password`, `foto_url`, `estado`, `configuracion`). `rol_id` se ignora aunque se envíe — solo se cambia vía `PATCH /users/{id}` (ADMIN). Si se envía `email`, valida que no esté tomado por otro usuario (`409`).

Response `200`: el usuario actualizado (mismo shape que `GET /users/me`).

### `PATCH /users/me/password`
Body:
```json
{ "current_password": "Sup3rSegura!", "new_password": "OtraClave2026!" }
```
Response `204` (sin body). Error `400` si `current_password` no coincide.

### `POST /users/me/photo` *(no estaba en el diseño original)*
**Auth:** usuario autenticado. `multipart/form-data`: `file` (`image/jpeg`, `image/png` o `image/webp`; cualquier otro `content_type` responde `422`). Sube a Cloudinary (`tourpoints/usuarios/{usuario_id}/`, mismo patrón que las imágenes de POI) y reemplaza `foto_url`. Antes de esto, la columna `foto_url` existía en la BD y en los schemas, pero **no había forma de subir un archivo** — solo se podía pegar una URL arbitraria vía `PATCH /users/me`. Si ya tenías una foto, la anterior se borra de Cloudinary automáticamente (best-effort: si ese borrado falla, no bloquea la subida de la nueva).

Response `200`: el usuario actualizado (mismo shape que `GET /users/me`), con `foto_url` apuntando a la nueva imagen.

### `DELETE /users/me/photo` *(no estaba en el diseño original)*
**Auth:** usuario autenticado. Borra el asset en Cloudinary (si había uno) y limpia `foto_url` a `null`. Idempotente: llamarlo sin tener foto no da error, solo no hace nada.

### CRUD administrativo
| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| `POST` | `/users` | ADMIN | Crea un usuario con cualquier `rol_id` |
| `GET` | `/users` | ADMIN | Lista paginada (`page`/`page_size`, sobre `{items,total,page,page_size}`) con filtros `name`, `surname`, `email`, `estado`, `rol_id`, `include_deleted` |
| `GET` | `/users/count` | ADMIN | Cuenta con los mismos filtros que el listado |
| `GET` | `/users/{id}` | ADMIN | Detalle de un usuario |
| `PATCH` | `/users/{id}` | ADMIN | Actualización parcial, incluido `rol_id` (único lugar donde se puede cambiar el rol de otro usuario) |
| `POST` | `/users/{id}/activate` | ADMIN | Reactiva un usuario suspendido/eliminado |
| `POST` | `/users/{id}/suspend` | ADMIN | Suspende un usuario activo |
| `DELETE` | `/users/{id}` | ADMIN | Query `?soft=true` (default, setea `deleted_at`) o `?soft=false` (borrado permanente) |

---

## 4. Catálogos (`/countries`, `/departments`, `/cities`, `/poi-categories`) — ✅ implementado

Solo lectura, públicos, usados para poblar selects del frontend (incluido el combo país→departamento→ciudad en cascada). Implementado en [app/routers/catalogos.py](../app/routers/catalogos.py).

### `GET /countries?q=&page=&page_size=`
`q` filtra por `nombre` del país (`ILIKE`).
```json
{
  "items": [ { "id": 1, "nombre": "Colombia", "codigo_iso": "CO" } ],
  "total": 1, "page": 1, "page_size": 20
}
```

### `GET /departments?pais_id=&q=&page=&page_size=`
`pais_id` filtra directo (`departamentos.pais_id`); `q` filtra por `nombre` del departamento (`ILIKE`).
```json
{
  "items": [ { "id": 1, "nombre": "Atlántico", "pais_id": 1, "pais": "Colombia" } ],
  "total": 1, "page": 1, "page_size": 20
}
```

### `GET /cities?departamento_id=&pais_id=&q=&page=&page_size=`
`q` filtra por `nombre` de la ciudad (`ILIKE`). `pais_id` filtra vía join con `departamentos.pais_id` (una ciudad no tiene `pais_id` propio).
```json
{
  "items": [
    { "id": 1, "nombre": "Barranquilla", "departamento_id": 1, "departamento": "Atlántico" }
  ],
  "total": 2, "page": 1, "page_size": 20
}
```

### `GET /poi-categories?page=&page_size=`
```json
{
  "items": [
    { "id": 1, "nombre": "Cultura", "icono": "landmark", "color": "#3b82f6" },
    { "id": 5, "nombre": "Compras", "icono": "shopping-bag", "color": "#ec4899" }
  ],
  "total": 5, "page": 1, "page_size": 20
}
```

---

## 5. POI (`/poi`) — ✅ implementado

Implementado en [app/routers/poi.py](../app/routers/poi.py), [app/services/poi_service.py](../app/services/poi_service.py), [app/repositories/poi_repository.py](../app/repositories/poi_repository.py).

### `GET /poi`
**Auth:** pública (solo devuelve `estado = APROBADO`); ADMIN puede pasar `estado` para ver otros (si un usuario no-admin envía `estado`, se ignora silenciosamente).

Query params: **`nombre`** (texto sobre `poi.nombre`, `ILIKE` — el diseño original lo llamaba `q`, se renombró para ser consistente con `categoria_id`/`ciudad_id`), `categoria_id`, `ciudad_id`, `estado` (solo ADMIN), `lat`, `lng`, `radio_metros` (búsqueda geoespacial `ST_DWithin` sobre `poi.ubicacion`), `page`, `page_size`.

Response `200`:
```json
{
  "items": [
    {
      "id": "8b2e4a10-1c2d-4e3f-9a1b-0c1d2e3f4a5b",
      "nombre": "Museo del Oro",
      "slug": "museo-del-oro-bogota",
      "categoria": { "id": 3, "nombre": "Museo", "icono": "museum" },
      "ciudad": { "id": 11001, "nombre": "Bogotá" },
      "ubicacion": { "lat": 4.601, "lng": -74.072 },
      "calificacion_promedio": 4.6,
      "total_calificaciones": 312,
      "imagen_principal": "https://cdn.tourpoints.co/poi/8b2e/portada.jpg",
      "distancia_metros": 850.3
    }
  ],
  "total": 48, "page": 1, "page_size": 20
}
```
`distancia_metros` solo aparece si se enviaron `lat`/`lng`.

### `GET /poi/{id}`
**Auth:** pública si `estado = APROBADO`; si no, solo lo ve el dueño (`creado_por_usuario_id`) o un ADMIN — para cualquier otro caller responde `404` (no `403`, para no revelar que el POI existe).

Response `200` (detalle completo):
```json
{
  "id": "8b2e4a10-1c2d-4e3f-9a1b-0c1d2e3f4a5b",
  "nombre": "Museo del Oro",
  "slug": "museo-del-oro-bogota",
  "descripcion": "Colección de orfebrería precolombina más grande del mundo.",
  "direccion": "Cra 6 #15-88, Bogotá",
  "ubicacion": { "lat": 4.601, "lng": -74.072 },
  "radio_validacion": 60,
  "telefono": "6013431424",
  "correo": "info@museodeloro.gov.co",
  "sitio_web": "https://www.banrepcultural.org/museo-del-oro",
  "horarios": { "lunes": null, "martes": ["09:00", "18:00"] },
  "metadata": { "wifi": true, "parking": false, "precio_promedio": 0 },
  "categoria": { "id": 3, "nombre": "Museo" },
  "ciudad": { "id": 11001, "nombre": "Bogotá" },
  "estado": "APROBADO",
  "fuente": "ADMIN",
  "nivel": null,
  "calificacion_promedio": 4.6,
  "total_calificaciones": 312,
  "imagenes": [
    { "id": 55, "url": "https://cdn.tourpoints.co/poi/8b2e/portada.jpg", "orden": 0, "principal": true }
  ],
  "created_at": "2025-03-10T09:00:00-05:00"
}
```

### `POST /poi`
**Auth:** USUARIO (crea `fuente=USUARIO`), ESTABLECIMIENTO (`fuente=ESTABLECIMIENTO`) o ADMIN (`fuente=ADMIN`) — el backend resuelve `fuente` según el rol del token, el front **no la envía**.

Body:
```json
{
  "categoria_id": 3,
  "ciudad_id": 11001,
  "nombre": "Mirador de la 93",
  "descripcion": "Terraza con vista panorámica de la ciudad.",
  "direccion": "Cra 13 #93-40, Bogotá",
  "ubicacion": { "lat": 4.6764, "lng": -74.0479 },
  "radio_validacion": 50,
  "telefono": "3011234567",
  "correo": null,
  "sitio_web": null,
  "horarios": { "todos_los_dias": ["06:00", "22:00"] },
  "metadata": { "pet_friendly": true }
}
```
Response `201`: mismo shape que `GET /poi/{id}`, con `estado: "BORRADOR"` y `slug` autogenerado a partir de `nombre`.

### `PATCH /poi/{id}`
**Auth:** dueño (`creado_por_usuario_id`) o ADMIN. Mismos campos que `POST`, todos opcionales.

### `POST /poi/{id}/submit-for-review`
Transición `BORRADOR → PENDIENTE`. Response `200`: `{"id": "8b2e...", "estado": "PENDIENTE"}`.

### `PATCH /poi/{id}/moderation`
**Auth:** ADMIN.
```json
{ "estado": "APROBADO" }
```
o
```json
{ "estado": "RECHAZADO", "motivo": "Falta verificar dirección" }
```
Transiciones válidas: `PENDIENTE → APROBADO|RECHAZADO`, `APROBADO → INACTIVO`, `INACTIVO → APROBADO`. Cualquier otra combinación responde `400`. **`motivo` ahora se persiste** (en el diseño original se aceptaba pero se descartaba) — cada transición, con o sin `motivo`, queda registrada en la tabla de auditoría `poi_moderaciones` (ver `POST /poi/{id}/retry` y `GET /poi/{id}/moderation-log` abajo, y el modelo en [app/models/poi.py](../app/models/poi.py)).

### `POST /poi/{id}/retry` *(no estaba en el diseño original)*
**Auth:** dueño o ADMIN. Transición `RECHAZADO → BORRADOR` — completa el diagrama de estados de `doc/logica_negocio.md` (`RECHAZADO --> BORRADOR: se corrige y reintenta`), que no tenía endpoint propio. `400` si el POI no está en `RECHAZADO`.

Response `200`: mismo shape que `GET /poi/{id}`, con `estado: "BORRADOR"`.

### `GET /poi/{id}/moderation-log` *(no estaba en el diseño original)*
**Auth:** dueño o ADMIN. Historial completo de auditoría del POI (cada `submit-for-review`, `moderation` y `retry` queda registrado), más reciente primero.

Response `200`:
```json
[
  {
    "id": 2,
    "usuario_id": "9d410612-ba5c-4c73-9265-4bd1c9963894",
    "estado_anterior": "PENDIENTE",
    "estado_nuevo": "RECHAZADO",
    "motivo": "Falta verificar dirección",
    "created_at": "2026-07-16T15:33:10Z"
  },
  {
    "id": 1,
    "usuario_id": "9d410612-ba5c-4c73-9265-4bd1c9963894",
    "estado_anterior": "BORRADOR",
    "estado_nuevo": "PENDIENTE",
    "motivo": null,
    "created_at": "2026-07-16T15:33:08Z"
  }
]
```

### `DELETE /poi/{id}`
**Auth:** dueño o ADMIN. Soft delete (`deleted_at`). Response `204`.

### `POST /poi/{id}/images`
**Auth:** dueño o ADMIN. `multipart/form-data`: `file` (imagen — solo `image/jpeg`, `image/png` o `image/webp`, cualquier otro `content_type` responde `400`), `principal` (bool, default `false`).

El archivo se sube a **Cloudinary** (no a la base de datos ni a disco) en la carpeta `tourpoints/pois/{poi_id}/`; solo la URL resultante (`secure_url`) se guarda en `imagenes_poi.url`. Si `principal=true`, la imagen previamente marcada como principal se desmarca automáticamente (la base de datos no lo garantiza con un `CHECK`, lo hace el backend).

Response `201`:
```json
{ "id": 56, "poi_id": "8b2e4a10-1c2d-4e3f-9a1b-0c1d2e3f4a5b", "url": "https://res.cloudinary.com/<cloud_name>/image/upload/v.../tourpoints/pois/8b2e4a10-.../foto2.jpg", "orden": 1, "principal": false }
```

### `PATCH /poi/{id}/images/{imagen_id}` *(no estaba en el diseño original)*
**Auth:** dueño o ADMIN. Cambia `principal` y/o `orden` **sin volver a subir el archivo**. Body, ambos campos opcionales:
```json
{ "principal": true, "orden": 0 }
```
Si `principal=true`, desmarca automáticamente cualquier otra imagen del mismo POI que lo fuera (mismo criterio que en el `POST`). `404` si `imagen_id` no existe **o pertenece a otro POI** — el lookup siempre está escopado por `poi_id` + `imagen_id` juntos, no alcanza con adivinar un id de imagen válido de otro POI (confirmado: ni siquiera un ADMIN puede editar una imagen de un POI distinto al del path, es un 404, no un 403).

Response `200`: `{ "id": 56, "url": "...", "orden": 0, "principal": true }`.

### `DELETE /poi/{id}/images/{imagen_id}` *(no estaba en el diseño original)*
**Auth:** dueño o ADMIN. Borra la fila **y** el asset en Cloudinary (se deriva el `public_id` de la `url` guardada — no hay columna separada para eso — y se llama `cloudinary.uploader.destroy`; verificado con `cloudinary.api.resource` que el archivo realmente desaparece, no solo la referencia). Si el borrado en Cloudinary falla por algo transitorio, no bloquea el borrado en base de datos (se loguea el error; peor caso es un asset huérfano en el storage, no una imagen fantasma en la API).

Si la imagen borrada era la `principal` y quedan otras, **promueve automáticamente** la de menor `orden` a `principal=true`. Si era la última imagen del POI, simplemente queda `imagenes: []` — no hace falta subir una nueva para que el endpoint siga funcionando.

Response `204`.

---

## 6. Calificaciones (`/poi/{poi_id}/ratings`) — ✅ implementado

Implementado en [app/routers/social.py](../app/routers/social.py) (registrado sin prefijo — las rutas son literalmente `/api/v1/poi/{poi_id}/...`). `calificaciones` tiene `UNIQUE(usuario_id, poi_id)` — un usuario califica una sola vez por POI, por eso el endpoint de escritura es idempotente (`PUT`, no `POST`); el `PUT` hace upsert real (actualiza la fila existente, no inserta una segunda).

### `PUT /poi/{poi_id}/my-rating`
**Auth:** usuario autenticado.
```json
{ "calificacion": 5 }
```
`calificacion` entero 1-5 (`CHECK calificacion BETWEEN 1 AND 5`). Si ya existía una calificación de este usuario para este POI, se actualiza en vez de duplicar.

Response `200`:
```json
{
  "id": 981,
  "poi_id": "8b2e4a10-1c2d-4e3f-9a1b-0c1d2e3f4a5b",
  "usuario_id": "3f1c2a90-6b3e-4c1a-9f2d-7e8b1a2c3d4e",
  "calificacion": 5,
  "created_at": "2026-07-14T16:00:00-05:00"
}
```

### `DELETE /poi/{poi_id}/my-rating`
**Auth:** usuario autenticado (dueño). Response `204`. `404` si no tenías una calificación registrada para ese POI.

### `GET /poi/{poi_id}/ratings`
**Auth:** pública, paginado.
```json
{
  "items": [
    { "id": 981, "usuario": { "id": "3f1c...", "nombre": "Camila" }, "calificacion": 5, "created_at": "2026-07-14T16:00:00-05:00" }
  ],
  "total": 312, "page": 1, "page_size": 20
}
```

### `GET /poi/{poi_id}/ratings/summary`
```json
{ "promedio": 4.6, "total": 312, "distribucion": { "5": 210, "4": 70, "3": 20, "2": 8, "1": 4 } }
```

---

## 7. Comentarios (`/poi/{poi_id}/comments`) — ✅ implementado

Implementado en [app/routers/social.py](../app/routers/social.py).

### `POST /poi/{poi_id}/comments`
**Auth:** usuario autenticado.
```json
{ "contenido": "Excelente lugar, muy recomendado para ir en familia." }
```
Response `201` (nace `PENDIENTE`, requiere moderación):
```json
{
  "id": 4021,
  "poi_id": "8b2e4a10-1c2d-4e3f-9a1b-0c1d2e3f4a5b",
  "usuario": { "id": "3f1c...", "nombre": "Camila" },
  "contenido": "Excelente lugar, muy recomendado para ir en familia.",
  "estado": "PENDIENTE",
  "created_at": "2026-07-14T16:10:00-05:00"
}
```

### `GET /poi/{poi_id}/comments`
**Auth:** pública — solo `estado = APROBADO` por defecto; ADMIN puede pasar `?estado=PENDIENTE` para moderar. Paginado, mismo shape que arriba.

### `PATCH /comments/{id}/moderation`
**Auth:** ADMIN. Body `{"estado": "APROBADO"}` o `{"estado": "RECHAZADO"}` — cualquier otro valor (incluido `"PENDIENTE"`) responde `400`.

### `DELETE /comments/{id}`
**Auth:** dueño o ADMIN. Response `204`.

---

## 8. Favoritos (`/favorites`) — ✅ implementado

Implementado en [app/routers/social.py](../app/routers/social.py). Tabla puente pura (`usuario_id`, `poi_id`), sin `id` propio.

### `POST /favorites`
**Auth:** usuario autenticado.
```json
{ "poi_id": "8b2e4a10-1c2d-4e3f-9a1b-0c1d2e3f4a5b" }
```
Response `201`:
```json
{ "usuario_id": "3f1c2a90-6b3e-4c1a-9f2d-7e8b1a2c3d4e", "poi_id": "8b2e4a10-1c2d-4e3f-9a1b-0c1d2e3f4a5b", "created_at": "2026-07-14T16:15:00-05:00" }
```
`400` si el POI ya estaba en tus favoritos (no se duplica).

### `DELETE /favorites/{poi_id}`
**Auth:** usuario autenticado. Response `204`. `404` si ese POI no estaba en tus favoritos.

### `GET /favorites/me`
**Auth:** usuario autenticado. Paginado — devuelve los POI favoritos con el mismo shape resumido de `GET /poi` (reutiliza la misma query de agregados: categoría, ciudad, calificación promedio, imagen principal).

---

## 9. Visitas / Check-in (`/visits`) — ✅ implementado

Implementado en [app/routers/visitas.py](../app/routers/visitas.py), [app/services/visitas_service.py](../app/services/visitas_service.py). El shape real difiere del diseño original: el body no acepta `{lat, lng}` sino un string WKT. Los tres métodos (`GPS`, `QR`, `MIXTA`) están implementados y probados end-to-end.

### `POST /visits`
**Auth:** usuario autenticado. Qué campos son obligatorios depende de `metodo_validacion`:

| `metodo_validacion` | Requiere | Qué valida |
|---|---|---|
| `GPS` (default) | `ubicacion_usuario` + `precision_metros` | `ST_Distance` contra `poi.ubicacion` ≤ `poi.radio_validacion` + `precision_metros` |
| `QR` | `codigo_qr` | HMAC(SECRET_KEY, poi_id) — ver `GET /poi/{id}/qr-code` abajo |
| `MIXTA` | los tres | ambas validaciones, deben pasar las dos |

Si queda `VALIDADA`, dispara un `movimientos_puntos` consultando `reglas_puntos`.

Body (GPS):
```json
{
  "poi_id": "8b2e4a10-1c2d-4e3f-9a1b-0c1d2e3f4a5b",
  "ubicacion_usuario": "POINT(-74.0721 4.6015)",
  "precision_metros": 8.5
}
```
`ubicacion_usuario` es un string WKT (`POINT(longitud latitud)`, orden invertido respecto a `{lat, lng}`), no un objeto — distinto al resto de la API (`GET /poi`, `POST /poi`, etc., que sí usan `{"lat":..,"lng":..}`).

Body (QR):
```json
{ "poi_id": "8b2e4a10-1c2d-4e3f-9a1b-0c1d2e3f4a5b", "metodo_validacion": "QR", "codigo_qr": "TP-POI-a42f02cfbe968f139987" }
```
`codigo_qr` se obtiene de `GET /poi/{id}/qr-code` (dueño o ADMIN) — es determinístico (`HMAC(SECRET_KEY, poi_id)`, primeros 20 hex), no se guarda en base de datos: se recalcula igual siempre a partir del `poi_id`, así que basta con imprimirlo una vez en el sitio físico. Nadie puede forjar un código válido sin conocer `SECRET_KEY` del backend, aunque el `poi_id` sea público.

Response `201`:
```json
{
  "id": "v7712a10-...",
  "poi_id": "8b2e4a10-1c2d-4e3f-9a1b-0c1d2e3f4a5b",
  "estado": "VALIDADA",
  "distancia_metros": 42.1,
  "puntos_otorgados": 120,
  "created_at": "2026-07-14T16:20:00-05:00"
}
```
`distancia_metros` es `null` en un check-in `QR` puro (no se midió GPS). `estado: "RECHAZADA"` — en la práctica, si la distancia excede `radio_validacion` o el `codigo_qr` no coincide, el endpoint responde `422` y **no llega a crear la fila** (comportamiento heredado del flujo GPS original, no se cambió); un intento fallido no queda registrado, solo el error de la respuesta. Límite de un check-in `VALIDADA` por usuario+POI+día natural (UTC), sin importar el método: `409` si ya hiciste uno hoy.

### `GET /poi/{id}/qr-code` *(no estaba en el diseño original)*
**Auth:** dueño del POI o ADMIN. Documentado aquí porque es el complemento directo del check-in `QR`, aunque vive en el router de POI.
```json
{ "codigo_qr": "TP-POI-a42f02cfbe968f139987" }
```

### `GET /visits/me/balance`
**Auth:** usuario autenticado. Saldo agregado (`SUM` sobre `movimientos_puntos`, vista `saldo_puntos_usuario`).
```json
{ "saldo": 220 }
```

### `GET /visits/me` *(no estaba en el diseño original)*
**Auth:** usuario autenticado. Paginado (`page`/`page_size`) — historial de check-ins, más reciente primero. `puntos_otorgados` se resuelve con un `outerjoin` contra `movimientos_puntos` (no vive en `visitas`); `0` si esa visita no generó movimiento.
```json
{
  "items": [
    { "id": "...", "poi": { "id": "...", "nombre": "Gran Malecón del Río", "slug": "gran-malecon-del-rio" }, "estado": "VALIDADA", "metodo_validacion": "MIXTA", "distancia_metros": 0.0, "puntos_otorgados": 200, "created_at": "2026-07-17T03:26:32Z" }
  ],
  "total": 3, "page": 1, "page_size": 20
}
```

---

## 10. Comercial: establecimientos, compras, promociones — ✅ implementado

Implementado en [app/routers/comercial.py](../app/routers/comercial.py), [app/services/comercial_service.py](../app/services/comercial_service.py), [app/repositories/comercial_repository.py](../app/repositories/comercial_repository.py). `establecimientos` es una extensión 1:1 de `poi` (`poi_id UNIQUE`) — no duplica nombre/dirección/ubicación. **Autorización real por pertenencia**, no por rol global: cada endpoint de negocio valida contra `establecimiento_usuarios` (¿este usuario administra *este* establecimiento específico?), no solo `rol_id`. `POST /redemptions/validate-qr` y `GET /redemptions/{id}` (sección 13) ya se ajustaron a este mismo criterio, reutilizando `ComercialRepository.es_staff`.

### `POST /businesses`
**Auth:** dueño del POI o ADMIN. El POI debe estar `APROBADO` (`422` si no). `409` si ese `poi_id` ya tiene un establecimiento (`UNIQUE`). Te registra automáticamente en `establecimiento_usuarios` con `cargo="dueño"`.
```json
{ "poi_id": "9c3f...", "nit": "900123456-7", "razon_social": "Café La Terraza S.A.S.", "tipo_negocio": "Restaurante" }
```
Response `201` (`estado: "PENDIENTE"`, pendiente de aprobación admin).

### `GET /businesses/me`
**Auth:** usuario autenticado. Paginado. Lista los establecimientos que administrás (join con `establecimiento_usuarios`), incluye tu `cargo` en cada uno.

### `PATCH /businesses/{id}/moderation`
**Auth:** ADMIN. Body `{"estado": "APROBADO"}`. Mismas transiciones válidas que POI (`PENDIENTE → APROBADO|RECHAZADO`, `APROBADO → INACTIVO`, `INACTIVO → APROBADO`) — reutiliza `poi_estado_enum` pero con su propio diccionario de transiciones (`VALID_MODERATION_TRANSITIONS` en `comercial_service.py`, separado del de POI).

### `POST /businesses/{id}/purchases`
**Auth:** staff del establecimiento (vía `establecimiento_usuarios`, cualquier `cargo`) o ADMIN — `403` si no. El establecimiento debe estar `APROBADO` (`422` si no).
```json
{ "usuario_id": "3f1c2a90-6b3e-4c1a-9f2d-7e8b1a2c3d4e", "valor": 45000, "moneda": "COP", "codigo_transaccion": "POS-00981" }
```
Los puntos se calculan igual que en visitas: busca en `reglas_puntos` una regla `evento=COMPRA` con `configuracion.puntos_por_1000` (proporción configurable); si no hay ninguna sembrada, usa el default de 1 punto por cada 1000 unidades de moneda (`valor=45000` → `45` puntos, confirmado en pruebas reales contra la BD).

Response `201`:
```json
{
  "id": "cp901a...",
  "establecimiento_id": "e5a1...",
  "usuario_id": "3f1c2a90-6b3e-4c1a-9f2d-7e8b1a2c3d4e",
  "valor": 45000,
  "moneda": "COP",
  "codigo_transaccion": "POS-00981",
  "estado": "REGISTRADA",
  "puntos_otorgados": 45,
  "created_at": "2026-07-14T16:30:00-05:00"
}
```

### `PATCH /purchases/{id}/cancel`
**Auth:** staff del establecimiento dueño de la compra, o ADMIN. `409` si ya estaba `CANCELADA`. El `CHECK` de la tabla obliga a que, al cancelar, quede quién y cuándo — el backend los completa (`cancelada_por` = usuario del token, `fecha_cancelacion = now()`), el front no los envía.

**Importante — reversión de puntos:** cancelar una compra inserta un `movimientos_puntos` **negativo compensatorio** por el mismo `compra_id` (el ledger es append-only, nunca se edita/borra la fila original — ver `doc/logica_negocio.md`). Verificado contra la BD real: una compra de 45000 (+45 puntos) cancelada deja el saldo del usuario exactamente donde estaba antes, con las dos filas (+45 y −45) intactas en `movimientos_puntos`. Esto **no estaba explícito en el diseño original** — se agregó porque sin esto, cancelar una compra dejaría al usuario quedándose con puntos de algo que ya no cuenta como venta válida.

### `POST /businesses/{id}/promotions`
**Auth:** staff del establecimiento o ADMIN. El establecimiento debe estar `APROBADO`.
```json
{ "titulo": "2x1 en café los martes", "descripcion": "Válido de 3pm a 6pm.", "inicio": "2026-07-15T00:00:00-05:00", "fin": "2026-09-15T23:59:59-05:00" }
```
`CHECK (fin > inicio)` en la base de datos, validado también en el schema (Pydantic) para devolver `422` en vez de un error de base de datos. Nace `PENDIENTE`.

### `PATCH /businesses/{id}/promotions/{promotion_id}/moderation` *(no estaba en el diseño original)*
**Auth:** ADMIN. Body `{"estado": "APROBADO"}` o `{"estado": "RECHAZADO"}`. Se agregó porque el diseño original nunca tenía forma de aprobar una promoción — sin este endpoint, `POST .../promotions` la dejaría `PENDIENTE` para siempre y **nunca aparecería** en `GET /poi/{id}/promotions` (que solo muestra `APROBADO`). Mismo patrón que `POST /poi/{id}/retry` completando un hueco del flujo original.

### `GET /poi/{id}/promotions`
Público — promociones vigentes (`estado = APROBADO` y dentro de `inicio`/`fin`) del establecimiento asociado a ese POI. Probado end-to-end: antes de aprobar, vacío; después de aprobar, aparece sin necesitar token.

---

## 11. Retos (`/challenges`) — ✅ implementado

Implementado en [app/routers/retos.py](../app/routers/retos.py), [app/services/reto_service.py](../app/services/reto_service.py), [app/repositories/reto_repository.py](../app/repositories/reto_repository.py). Es el módulo más grande de la API — cubre plantillas de reto, inscripción, progreso, rachas, hitos e insignias. Probado end-to-end contra la BD real, incluida la interacción con los 4 triggers de PostgreSQL (`fn_reservar_o_bloquear_reto`, `fn_liberar_reserva_si_no_completa`, `fn_otorgar_recompensa_hito`, `fn_descontar_stock_canje`).

### `GET /challenges`
**Auth:** pública. Query: `tipo` (`VISITA|COMPRA|RECORRIDO`), `estado` (default `ACTIVO`, solo ADMIN puede pasar otro), `establecimiento_id`, `page`, `page_size`.
```json
{
  "items": [
    {
      "id": "rt441a...",
      "nombre": "Recorre 3 museos esta semana",
      "tipo": "VISITA",
      "recurrencia": "SEMANAL",
      "cantidad_requerida": 3,
      "modo_recompensa": "LIMITADA",
      "recompensa": { "id": "rc10...", "nombre": "Kit de souvenirs", "puntos": 0 },
      "inicio": "2026-07-01T00:00:00-05:00",
      "fin": "2026-12-31T23:59:59-05:00",
      "estado": "ACTIVO",
      "disponible": true
    }
  ],
  "total": 12, "page": 1, "page_size": 20
}
```
`disponible` se calcula en Python con el mismo criterio que la vista `retos_disponibilidad` (`SIN_RECOMPENSA`/`LIMITADA` siempre `true`; `GARANTIZADA` solo si `stock > 0`) — no se consulta la vista directamente, para mantener el mismo estilo que `disponible` en `RecompensaOut` (calculado en el service, no en SQL).

### `GET /challenges/{id}`
Detalle completo incluyendo `descripcion`, `establecimiento_id` y `configuracion` (JSONB libre con reglas del reto).

### `POST /challenges`
**Auth:** ADMIN (nace `ACTIVO`) o staff de un establecimiento propio, vía `establecimiento_usuarios` (nace `BORRADOR`, pendiente de aprobación — `422` si no envía `establecimiento_id`, `403` si no administra ese negocio).
```json
{
  "nombre": "Recorre 3 museos esta semana",
  "descripcion": "Visita 3 museos distintos en la misma semana.",
  "tipo": "VISITA",
  "recurrencia": "SEMANAL",
  "cantidad_requerida": 3,
  "modo_recompensa": "LIMITADA",
  "recompensa_id": "rc10...",
  "inicio": "2026-07-01T00:00:00-05:00",
  "fin": "2026-12-31T23:59:59-05:00",
  "configuracion": { "categoria_id": 3 }
}
```
Coherencia `modo_recompensa`/`recompensa_id` y `fin > inicio` validadas en el schema (Pydantic, `422` limpio) además del `CHECK` de la base de datos.

### `PATCH /challenges/{id}/moderation`
**Auth:** ADMIN. `{"estado": "ACTIVO"}` o `{"estado": "CANCELADO"}`. Transiciones válidas: `BORRADOR → ACTIVO|CANCELADO`, `ACTIVO → CANCELADO`.

### `POST /challenges/{id}/join`
**Auth:** usuario autenticado. Calcula el periodo vigente según `recurrencia` (`UNICA` usa `inicio`/`fin` del reto tal cual; `DIARIA`/`SEMANAL`/`MENSUAL` se calculan en Python — semana empieza lunes, mes empieza el día 1, ambos en UTC). `422` si el reto no está `ACTIVO` o `ahora` está fuera de su ventana de vigencia.

Si `modo_recompensa = GARANTIZADA`, el trigger `fn_reservar_o_bloquear_reto` reserva 1 unidad de stock de inmediato o bloquea con `409` — **verificado contra la BD real**: creé una recompensa con `stock=1`, un usuario se inscribió (stock pasó a `0`), un segundo usuario intentó inscribirse y recibió `409`.

Response `201`:
```json
{
  "id": "ur559a...",
  "reto_id": "rt441a...",
  "periodo_inicio": "2026-07-14T00:00:00-05:00",
  "periodo_fin": "2026-07-20T23:59:59-05:00",
  "numero_intento": 1,
  "progreso": { "completados": [], "cantidad": 0 },
  "porcentaje": 0,
  "estado": "ACTIVO"
}
```
Error `409`: `{"detail": "Ya existe un intento activo para este periodo"}` (índice único parcial) o `{"detail": "Sin stock disponible para reservar la recompensa"}`.

### `POST /challenges/{id}/abandon` *(no estaba en el diseño original)*
**Auth:** usuario autenticado. Cancela tu intento `ACTIVO` (cualquier reto). Se agregó porque, sin este endpoint, un intento `GARANTIZADA` dejaba el stock reservado atrapado hasta la próxima corrida de `fn_expirar_retos_vencidos()` — que ahora corre sola cada hora vía un scheduler in-process (ver sección 16), pero este endpoint sigue siendo útil para liberar el stock al instante en vez de esperar hasta la próxima hora en punto. Verificado: abandonar un intento `GARANTIZADA` devuelve el stock reservado (`0 → 1`) vía el trigger `fn_liberar_reserva_si_no_completa`.

### `GET /challenges/me`
Paginado — todos tus intentos (`usuario_retos`), todos los periodos, más reciente primero.

### `GET /challenges/{id}/my-progress`
Tu intento `ACTIVO` actual para ese reto. `404` si no tenés uno.

### `POST /challenges/{id}/progress` *(no estaba en el diseño original)*
**Auth:** usuario autenticado (dueño del intento `ACTIVO`). El diseño original nunca definía **cómo** avanzaba `progreso`/`cantidad` — sin este endpoint, ningún intento podía completarse nunca. Body:
```json
{ "incremento": 1, "detalle": "poi-id-opcional-de-que-generó-el-avance" }
```
Suma `incremento` a `progreso.cantidad` (tope en `cantidad_requerida`), agrega `detalle` a `progreso.completados` si vino. Al alcanzar `cantidad_requerida`, el intento pasa a `FINALIZADO` en la misma llamada y dispara, en este orden:
1. Puntos por completar el reto (busca `reglas_puntos` con `evento=RETO`; sin regla sembrada, usa 50 por defecto — no hay ejemplo en el diseño original para calibrar este número contra nada, a diferencia de VISITA/COMPRA).
2. Si `recurrencia != UNICA`: `racha_actual += 1`, `racha_maxima = GREATEST(...)`, y por cada `hitos_racha` cuyo `racha_requerida` coincida exactamente con la racha alcanzada, se inserta `hitos_racha_alcanzados` (dispara `fn_otorgar_recompensa_hito`) y se acreditan sus `puntos_bonus`.
3. Si `modo_recompensa` es `GARANTIZADA` o `LIMITADA`: emite un `canje` (`origen=RETO`). **Importante:** este paso corre en una transacción separada de los dos anteriores — si el canje falla (stock agotado en modo `LIMITADA`), el rollback solo afecta al canje, nunca a los puntos/racha/hitos ya otorgados ("nunca bloquear el logro, solo omitir el premio físico", ver `doc/logica_negocio.md`).

Verificado end-to-end: reto `SIN_RECOMPENSA` completado en dos llamadas (50%→100%) acreditó 50 puntos; reto `GARANTIZADA` completado emitió el canje sin volver a descontar stock (el trigger de canjes salta el descuento cuando ya se reservó al inscribirse); reto `SEMANAL` con un hito en `racha_requerida=1` otorgó la insignia y sus puntos de bono en la misma llamada.

### `GET /challenges/{id}/my-streak`
```json
{ "racha_actual": 3, "racha_maxima": 7 }
```
`0`/`0` si nunca participaste. Verificado el caso de "hueco": si te uniste dejando pasar un periodo completo sin jugar, `racha_actual` vuelve a `0` en el siguiente `join` (no en el `progress`), mientras `racha_maxima` conserva el récord histórico.

### `POST /challenges/{id}/sessions` *(solo `tipo = RECORRIDO`)*
Inicia una sesión de tracking en vivo (el stream punto-a-punto vive en Redis, fuera de esta API; esta tabla solo guarda el marco inicio/fin/estado). `422` si el reto no es `RECORRIDO`, `404` si `usuario_reto_id` no es tuyo o no es de este reto.
```json
{ "usuario_reto_id": "ur559a..." }
```
Response `201`: `{"id": "ss11a...", "usuario_reto_id": "ur559a...", "inicio": "2026-07-14T16:40:00-05:00", "fin": null, "estado": "ACTIVO"}`.

### `PATCH /challenges/{id}/sessions/{session_id}/finish`
Body opcional `{"estado": "FINALIZADO"}` (es el default). `409` si la sesión ya estaba cerrada.

---

## 12. Recompensas (`/rewards`) — ✅ implementado

Implementado en [app/routers/recompensas.py](../app/routers/recompensas.py), [app/services/recompensas_service.py](../app/services/recompensas_service.py). `GET /rewards` pagina igual que el resto de la API (`page`/`page_size`, sobre `{items,total,page,page_size}`) — inicialmente se implementó con `limit`/`offset` y un array plano; **corregido** para ser consistente.

### `POST /rewards`
**Auth:** ADMIN. Crea una recompensa con `estado` fijo `APROBADO` (no hay flujo de moderación para recompensas).
```json
{ "poi_id": null, "nombre": "Entrada gratis planetario", "descripcion": "Válida 1 vez por usuario.", "stock": 14, "puntos": 500 }
```
`poi_id` es opcional (nullable a propósito, ver `doc/logica_negocio.md` módulo 15-18).

### `GET /rewards`
**Auth:** pública (usuario común solo ve `estado = APROBADO`; ADMIN ve todo y puede filtrar por `estado`). Query: `poi_id`, `estado`, `page`, `page_size`.
```json
{
  "items": [
    { "id": "rc10a...", "poi_id": "e5a1...", "nombre": "Entrada gratis planetario", "descripcion": "Válida 1 vez por usuario.", "stock": 14, "puntos": 500, "estado": "APROBADO", "disponible": true }
  ],
  "total": 9, "page": 1, "page_size": 20
}
```

### `GET /rewards/{id}`
Detalle, mismo shape. `disponible` es `stock > 0`.

### `PATCH /rewards/{id}`
**Auth:** ADMIN. Actualización parcial (`nombre`, `descripcion`, `stock`, `puntos`, `poi_id`).

### `POST /rewards/{id}/redeem`
**Auth:** usuario autenticado. Sin body (todo se resuelve del token + `{id}` en la URL). Crea un `canje` con `origen = PUNTOS`; el backend valida `saldo_puntos_usuario >= recompensas.puntos` antes de insertar, y el trigger `fn_descontar_stock_canje` descuenta stock atómicamente.

Response `201`:
```json
{
  "id": "cj10a1b2-...",
  "recompensa": { "id": "rc10a...", "poi_id": null, "nombre": "Entrada gratis planetario", "descripcion": "...", "stock": 13, "puntos": 500, "estado": "APROBADO", "disponible": true },
  "origen": "PUNTOS",
  "codigo_qr": "TP-CANJE-<token>",
  "estado": "PENDIENTE",
  "fecha_expira": "2026-08-14T00:00:00-05:00",
  "created_at": "2026-07-14T16:45:00-05:00"
}
```
Errores: `409` puntos insuficientes o sin stock disponible.

---

## 13. Canjes y validación QR (`/redemptions`) — ✅ implementado

Implementado en [app/routers/canjes.py](../app/routers/canjes.py), [app/services/recompensas_service.py](../app/services/recompensas_service.py) (mismo service que `/rewards`, comparte `CanjeRepository`/`RecompensaRepository`). La creación del canje vive en `POST /rewards/{id}/redeem` (sección 12) — este módulo cubre el resto del ciclo de vida.

### `GET /redemptions/me`
**Auth:** usuario autenticado. Paginado (`page`/`page_size`) — historial de canjes propios, más reciente primero. Mismo shape que `CanjeOut` (sin `usuario`, ya sabes quién eres).

### `GET /redemptions/{id}`
**Auth:** dueño del canje, ADMIN, o staff (cualquier `cargo`) del establecimiento dueño de la recompensa — vía `establecimiento_usuarios`, pertenencia real, no rol global. Devuelve `404` (no `403`) si ninguna de las tres aplica — no revela que el canje existe, mismo criterio que `GET /poi/{id}`. Shape `CanjeValidacionOut` (incluye `usuario` y `fecha_redencion`, útil para cualquiera de los casos de uso).

Si la recompensa no tiene `poi_id` (nullable a propósito, ver `doc/logica_negocio.md` — no toda recompensa depende de un aliado comercial), no hay establecimiento que pueda reclamarla: solo dueño-o-ADMIN.

### `POST /redemptions/validate-qr`
**Auth:** ADMIN, o staff del establecimiento dueño de la recompensa del canje — mismo criterio de pertenencia que arriba. **Corregido**: antes bastaba con tener `rol_id = establecimiento` en cualquier negocio; ahora se resuelve `recompensa.poi_id → establecimientos → establecimiento_usuarios` y se exige pertenencia al negocio específico dueño de *esa* recompensa (`app/services/recompensas_service.py:_ensure_puede_gestionar_canje`, reutiliza `ComercialRepository.es_staff` del módulo Comercial). Verificado contra la BD real: un usuario con rol `establecimiento` pero sin vínculo al negocio dueño de la recompensa ahora recibe `403` (antes pasaba); el dueño real del negocio sí puede validar aunque no haya sido quien compró el canje; una recompensa sin `poi_id` solo la puede validar un ADMIN, ni siquiera el dueño de un negocio no relacionado.
```json
{ "codigo_qr": "TP-CANJE-9C41F0" }
```
El backend busca el `canje` por `codigo_qr`:
- `404` si el código no existe.
- Si está `PENDIENTE` pero `fecha_expira` ya pasó: lo marca `EXPIRADO` en el momento (expiración perezosa, no hay cron todavía) y responde `409` ("Este código ya expiró").
- Si ya estaba `REDIMIDO` o `EXPIRADO`: `409` ("Este código ya fue redimido/expirado").
- Si está `PENDIENTE` y vigente: lo marca `REDIMIDO` con `fecha_redencion = now()` y responde `200`.

Response `200` (shape `CanjeValidacionOut`):
```json
{
  "id": "3f0a6232-...",
  "recompensa": { "id": "a0000000-...", "poi_id": null, "nombre": "Café en el Paseo Bolívar", "descripcion": "...", "stock": 42, "puntos": 150, "estado": "APROBADO", "disponible": true },
  "usuario": { "id": "5cecf5a7-...", "nombre": "QA" },
  "origen": "PUNTOS",
  "estado": "REDIMIDO",
  "fecha_expira": "2026-08-15T23:55:03Z",
  "fecha_redencion": "2026-07-17T03:06:05Z",
  "created_at": "2026-07-16T23:55:03Z"
}
```

**Validado contra la base de datos real:** `trg_descontar_stock_canje` solo dispara en `BEFORE INSERT` sobre `canjes` — las transiciones `PENDIENTE → REDIMIDO` y `PENDIENTE → EXPIRADO` son `UPDATE`s planos, no reactivan ningún trigger de stock (correcto: el stock ya se descontó al crear el canje). Probado end-to-end: 404 código inexistente, 403 rol no autorizado, 200 redención válida, 409 doble redención, 409 código vencido (con transición perezosa a `EXPIRADO` verificada en la fila).

---

## 14. Puntos (`/points`) — ✅ implementado

El saldo agregado vive en `GET /visits/me/balance` (sección 9) — no se duplica aquí. Implementado en [app/routers/puntos.py](../app/routers/puntos.py), [app/services/puntos_service.py](../app/services/puntos_service.py). Libro mayor append-only (`movimientos_puntos`) — nunca se expone escritura directa al frontend, solo lectura; los movimientos los genera el backend al validar visitas, compras, retos y canjes.

### `GET /points/me/movements`
**Auth:** usuario autenticado. Paginado, más reciente primero.
```json
{
  "items": [
    { "id": 4021, "tipo_movimiento": "VISITA", "referencia_id": "v7712a10-...", "puntos": 120, "created_at": "2026-07-14T16:20:00-05:00" },
    { "id": 4022, "tipo_movimiento": "CANJE", "referencia_id": null, "puntos": -500, "created_at": "2026-07-14T16:45:00-05:00" }
  ],
  "total": 87, "page": 1, "page_size": 20
}
```
`tipo_movimiento` es siempre uno de `VISITA|COMPRA|RETO|CANJE` (columna generada por la base de datos a partir de cuál FK está llena, ver `doc/logica_negocio.md`). `referencia_id` **no estaba en el diseño original** — se agregó devolviendo la FK que esté informada (`visita_id`/`compra_id`/`usuario_reto_id`/`canje_id`, según `tipo_movimiento`), para que el frontend pueda enlazar cada movimiento a su origen sin pedir cuatro campos separados casi siempre `null`. Verificado end-to-end contra la BD real: el total coincide exacto con `COUNT(*)` filtrado por usuario, la paginación no repite ni salta filas entre páginas, y se ve correctamente el movimiento negativo de una compra cancelada (sección 10) junto a los positivos de retos completados (sección 11).

---

## 15. Gamificación adicional: insignias y rachas — ✅ implementado

Se implementó junto con el resto de Retos (sección 11) en vez de como módulo aparte — `GET /challenges/{id}/my-streak` y `GET /users/me/badges` están documentados ahí, con el flujo completo de cómo se otorgan (`POST /challenges/{id}/progress`). Solo lectura desde afuera: la escritura la maneja la aplicación internamente al procesar el progreso de un reto, no vía endpoints públicos separados.

---

## 16. Notas y decisiones pendientes

### Resueltas durante la implementación de POI / Catálogos / Social

- **Auditoría de moderación de POI:** se agregó la tabla `poi_moderaciones` (migración `5e0ac9f7b8ed`, modelo `PoiModeracionLog`) — no estaba en el diseño original. Cada transición de estado (`submit-for-review`, `moderation`, `retry`) queda registrada con `usuario_id`, `estado_anterior`, `estado_nuevo`, `motivo` y `created_at`. `motivo` ya se persiste (antes se aceptaba en el body y se descartaba).
- **`RECHAZADO → BORRADOR` sin endpoint:** el diagrama de `doc/logica_negocio.md` lo contemplaba pero ningún endpoint lo implementaba. Se agregó `POST /poi/{id}/retry`.
- **Imágenes de POI:** ✅ resuelto en el backend — al subir una imagen con `principal=true`, el servicio desmarca explícitamente la anterior (no hay `CHECK` en la base de datos que lo garantice, como ya anticipaba esta nota). **Gestión completa:** se agregaron `PATCH /poi/{id}/images/{imagen_id}` (cambiar `principal`/`orden` sin resubir) y `DELETE /poi/{id}/images/{imagen_id}` (borra fila + asset en Cloudinary, promueve automáticamente la siguiente imagen a `principal` si borrás la que lo era). El `public_id` de Cloudinary no se guarda en una columna — se deriva de la `url` con una regex (`app/services/cloudinary_service.py:extraer_public_id`) porque `imagenes_poi` no tiene ese campo.
- **`GET /countries` y `GET /departments`:** ✅ agregados (sección 4), mismo patrón que `/cities` (paginado, filtro `q`, `/departments` además filtra por `pais_id`). Completa el combo país→departamento→ciudad en cascada para el frontend — probado encadenado: `GET /countries` → `GET /departments?pais_id=1` → `GET /cities?departamento_id=1`.
- **Foto de perfil de usuario:** se agregaron `POST /users/me/photo` y `DELETE /users/me/photo` (sección 3). La columna `usuarios.foto_url` y el helper `upload_usuario_foto` en `cloudinary_service.py` ya existían, pero **nada los conectaba** — se auditó la BD (los 7 usuarios reales tenían `foto_url = NULL`) y se confirmó que la única forma de setearlo era pegar una URL arbitraria a mano vía `PATCH /users/me`, sin subir nada de verdad. `ALLOWED_IMAGE_CONTENT_TYPES` se movió a `app/utils/media.py` para compartirlo entre POI y usuarios en vez de duplicarlo.
- **`ST_X`/`ST_Y` sobre `geography`:** esta instancia de PostGIS no resuelve `ST_X`/`ST_Y` directo sobre columnas `Geography` — hay que castear a `geometry` primero (`cast(columna, Geometry)`). Relevante para cualquier futuro endpoint que necesite leer lat/lng de vuelta (ej. el `ubicacion_usuario` de `POST /visits`, sección 9).
- **Todas las rutas se unificaron a inglés.** Antes `usuarios`, `visitas` y `recompensas` estaban en inglés (`/users`, `/visits`, `/rewards`) mientras POI, catálogos y social usaban español (`/ciudades`, `/categorias-poi`, `/favoritos`, `/comentarios`, `/poi/{id}/mi-calificacion`, etc.) — esa inconsistencia ya no existe. Se renombraron todos los paths en español a su equivalente en inglés (`/cities`, `/poi-categories`, `/favorites`, `/comments`, `/poi/{id}/my-rating`, `/poi/{id}/submit-for-review`, `/poi/{id}/moderation`, `/poi/{id}/retry`, `/poi/{id}/moderation-log`, `/poi/{id}/images`, `/rewards/{id}/redeem`, `/visits/me/balance`) y las secciones de diseño pendientes (Comercial, Retos, Canjes, Puntos, Gamificación) se actualizaron con nombres en inglés para que cualquier implementación futura ya nazca consistente. Los nombres de campos dentro del JSON (`nombre`, `estado`, `calificacion`...) **no** cambiaron — siguen en español, igual que las columnas de la base de datos.
- **Visitas y Recompensas ya no son "🚧 pendiente"** — quedaron marcadas así por error de desactualización; ambos módulos están implementados y probados end-to-end (secciones 9 y 12).
- **Resuelto: Visitas soporta `GPS`/`QR`/`MIXTA` de verdad, y `GET /visits/me`** (sección 9) — antes solo funcionaba `GPS` y no había historial. Se agregó `GET /poi/{id}/qr-code` (dueño/ADMIN) como complemento: el código es un HMAC determinístico sobre `poi_id`, sin columna nueva en la base de datos.
- **Resuelto: paginación de `GET /rewards`** — pagina ahora con `page`/`page_size` sobre `{items,total,page,page_size}`, igual que el resto de la API (antes usaba `limit`/`offset` y devolvía un array plano). Se agregó `RecompensaRepository.contar` (antes no existía) y `PaginatedRecompensasResponse`. Verificado contra la BD real: `total` coincide con el conteo directo en la tabla, paginación página 1/página 2 correcta, `GET /rewards/{id}` (no paginado) sin cambios.
- **Bug corregido:** `RecordNotFoundErrorHandler` y `DBErrorHandler` en [app/core/exception_handlers.py](../app/core/exception_handlers.py) hacían `str(exc)` sobre una `HTTPException` — `str()` de una `HTTPException` de Starlette devuelve `"{status_code}: {detail}"`, no solo el mensaje. Afectaba **todo** `404` y `500` de la API (no solo canjes — `GET /poi/{id}`, `GET /users/{id}`, etc. devolvían `{"detail": "404: <mensaje real>"}`). Cambiado a `exc.detail` en ambos handlers; verificado que ningún test dependía del formato viejo.
- **Resuelto: `POST /redemptions/validate-qr`** (sección 13) — el ciclo de vida completo del canje (`PENDIENTE → REDIMIDO`, con expiración perezosa a `EXPIRADO`) ya está implementado, junto con `GET /redemptions/me` y `GET /redemptions/{id}`.
- **Resuelto: autorización de `validate-qr`/`GET /redemptions/{id}` por pertenencia real** — dejó de bastar con `rol_id = establecimiento` en cualquier negocio; ahora se exige pertenencia al establecimiento específico dueño de la recompensa (`establecimiento_usuarios`, vía `ComercialRepository.es_staff`), igual que el resto de Comercial (sección 10). Se eliminó la dependencia `get_admin_or_establecimiento_user` (rol global) por quedar sin uso. Verificado contra la BD real: un usuario `establecimiento` sin vínculo al negocio dueño ahora recibe `403`/`404` donde antes pasaba; una recompensa sin `poi_id` (no todas dependen de un aliado comercial) solo la gestiona un ADMIN.
- **Resuelto: Comercial completo** (sección 10) — `establecimientos`, `compras` (con cálculo de puntos vía `reglas_puntos` y reversión al cancelar) y `promociones` (con moderación agregada, no estaba en el diseño original). Es el primer módulo con autorización real por pertenencia (`establecimiento_usuarios`), no por rol global — probado explícitamente que un usuario con `rol_id=establecimiento` pero sin vínculo al negocio específico recibe `403`.
- **Resuelto: Retos completo** (secciones 11 y 15) — plantillas, inscripción con cálculo de periodo por recurrencia, `POST /challenges/{id}/progress` (no estaba en el diseño original — sin él nada podía completar un reto), rachas, hitos, insignias y sesiones de `RECORRIDO`. Se agregó también `POST /challenges/{id}/abandon` (tampoco en el diseño original) para liberar stock `GARANTIZADA` al instante en vez de esperar la corrida horaria de `fn_expirar_retos_vencidos` (ver nota siguiente). Probados los 4 triggers de disponibilidad por stock contra la BD real: reserva al inscribirse, liberación al abandonar, no-doble-descuento al canjear una `GARANTIZADA`, y omisión de premio sin bloquear el logro en `LIMITADA`.
- **Resuelto: `fn_expirar_retos_vencidos()` ahora corre sola, cada hora.** Se confirmó primero que `pg_cron` no es viable en este proyecto de Neon: `CREATE EXTENSION pg_cron` falla incluso en la base `postgres` del mismo proyecto (`permission denied to create extension`) — Neon exige habilitarlo desde su panel de control, no vía SQL, y no está habilitado acá. Se implementó en su lugar un scheduler in-process con `APScheduler` ([app/core/scheduler.py](../app/core/scheduler.py)), arrancado/detenido en los eventos `startup`/`shutdown` de FastAPI (mismo patrón que ya usaba el seed de roles en `app/main.py`), corriendo `fn_expirar_retos_vencidos()` cada hora en punto. Es la opción de menor fricción para el despliegue actual (un solo contenedor, un solo proceso `uvicorn`, ver `docker-compose.yml`); si en el futuro se escala a varias réplicas, cada una correría su propio scheduler — no rompe nada (el `UPDATE` es idempotente), pero sería redundante, y ahí convendría moverse a un cron externo pegándole a un endpoint dedicado. Verificado end-to-end contra la BD real: se armó un intento `GARANTIZADA` `ACTIVO` con `periodo_fin` vencido hace 3 días (stock ya reservado en `0`), se corrió el job manualmente, y quedó `CANCELADO` con el stock devuelto a `1` — confirmando que también dispara `trg_liberar_reserva_si_no_completa` correctamente. Se verificó además que el job queda registrado en el scheduler con el trigger cron correcto durante el ciclo de vida real de la app (`TestClient` como context manager, dispara `startup`/`shutdown` de verdad).
- **Resuelto: Puntos completo** (sección 14) — `GET /points/me/movements`, historial paginado del ledger. Se agregó `referencia_id` (no estaba en el diseño original) para no depender de que el frontend conozca las cuatro FK posibles. Con esto, **todos los módulos que este documento describía como diseño quedaron implementados** — no queda ningún "🚧 pendiente" en el índice.

### Notas transversales que siguen abiertas (no bloquean ningún endpoint existente)

- **Sin refresh token:** `app/config.py` solo define `access_token_expire_minutes` (60 min por defecto), no hay secreto/expiración separada para refresh. Si se necesita sesión persistente, es una decisión de producto pendiente, no un detalle de implementación.
- **Autorización hoy vive en la aplicación, no en la base de datos:** no hay RLS activo (ver "Decisiones abiertas" en `doc/logica_negocio.md`), así que cada endpoint listado como ADMIN/ESTABLECIMIENTO/dueño debe validarse explícitamente en los routers/dependencias de FastAPI — así se hizo para POI/social vía `app/auth/dependencies.py` (`is_admin_user`, `get_role_nombre`, `get_optional_user`), reutilizable para los módulos que faltan.
- **`poi_estado_enum` compartido** entre `poi`, `establecimientos`, `promociones` y `recompensas`: los valores `RECHAZADO`/`INACTIVO` no siempre tienen sentido semántico idéntico en las cuatro entidades (ej. "rechazar" una recompensa vs. un POI) — los endpoints de moderación de cada una deberían restringir qué transiciones aceptan (como se hizo para POI con `VALID_MODERATION_TRANSITIONS` en `app/services/poi_service.py`), aunque la base de datos no lo fuerce.
- **Reglas de puntos:** cuánto otorga cada evento (visita, compra, reto) vive en `reglas_puntos.configuracion` (JSONB libre), no está hardcodeado — los endpoints que otorgan puntos deben resolverlo contra esa tabla, no contra una constante.
- **Stock de recompensas:** los triggers de la base de datos (`fn_reservar_o_bloquear_reto`, `fn_descontar_stock_canje`) son la fuente de verdad del stock — los endpoints deben capturar las excepciones que lancen (stock agotado) y traducirlas a `409`, no reimplementar la validación en Python de forma separada.
