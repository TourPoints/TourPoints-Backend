# SDD Progress Ledger — Módulo de Puntos

Branch: main
Plan: GET /api/v1/points/me/saldo y GET /api/v1/points/me/movimientos

## Tareas

- [x] Task 1: Schemas Pydantic — app/schemas/puntos.py (SaldoPuntosOut, MovimientoPuntosOut, MovimientosPuntosPage)
- [x] Task 2: Service — app/services/puntos_service.py (PuntosService: obtener_saldo, listar_movimientos)
- [x] Task 3: Repository — listar_por_usuario en MovimientoPuntosRepository
- [x] Task 4: Router — app/routers/points_router.py (factory get_puntos_service, 2 endpoints GET)
- [x] Task 5: Wiring — __init__.py + main.py (include_router points_router, prefix=/points)
- [x] Task 6: Tests + Verificación — tests/test_puntos.py (4 tests, unittest ok); rutas /api/v1/points/me/{saldo,movimientos} verificadas vía OpenAPI

## Verificación

- `python -m unittest tests.test_puntos -v` → 4 passed (OK)
- OpenAPI paths: `/api/v1/points/me/saldo` (get), `/api/v1/points/me/movimientos` (get)
- Arranque de app.main bloqueado por `ModuleNotFoundError: cloudinary` (preexistente en poi_service, ajeno a este módulo).
