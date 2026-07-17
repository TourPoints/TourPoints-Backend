from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock
from uuid import UUID

from app.services.puntos_service import PuntosService


def _movimiento(mov_id, tipo, puntos, created_at):
    """Movimiento fake con los atributos que usa MovimientoOut."""
    return SimpleNamespace(
        id=mov_id,
        tipo_movimiento=tipo,
        puntos=puntos,
        created_at=created_at,
    )


class PuntosServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.service = PuntosService(self.db)
        self.usuario_id = UUID("00000000-0000-0000-0000-000000000001")

    def test_obtener_saldo_devuelve_saldo_y_usuario_id(self):
        self.service.puntos_repo.obtener_saldo = MagicMock(return_value=150)
        out = self.service.obtener_saldo(str(self.usuario_id))
        self.service.puntos_repo.obtener_saldo.assert_called_once_with(str(self.usuario_id))
        self.assertEqual(out.saldo, 150)
        self.assertEqual(out.usuario_id, str(self.usuario_id))

    def test_obtener_saldo_usuario_sin_movimientos_es_cero(self):
        self.service.puntos_repo.obtener_saldo = MagicMock(return_value=0)
        out = self.service.obtener_saldo(str(self.usuario_id))
        self.assertEqual(out.saldo, 0)

    def test_listar_movimientos_devuelve_lista_plana_mapeada(self):
        fecha = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)
        movs = [
            _movimiento(1, "VISITA", 10, fecha),
            _movimiento(2, "CANJE", -30, fecha),
        ]
        self.service.movimiento_repo.listar = MagicMock(return_value=movs)
        items = self.service.listar_movimientos(str(self.usuario_id))

        self.service.movimiento_repo.listar.assert_called_once_with(
            str(self.usuario_id), limit=20, offset=0
        )
        self.assertIsInstance(items, list)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].id, 1)
        self.assertEqual(items[0].tipo_movimiento, "VISITA")
        self.assertEqual(items[0].puntos, 10)
        self.assertEqual(items[1].puntos, -30)

    def test_listar_movimientos_reenvia_limit_y_offset_al_repo(self):
        self.service.movimiento_repo.listar = MagicMock(return_value=[])
        self.service.listar_movimientos(str(self.usuario_id), limit=5, offset=50)
        self.service.movimiento_repo.listar.assert_called_once_with(
            str(self.usuario_id), limit=5, offset=50
        )

    def test_listar_movimientos_sin_resultados_devuelve_lista_vacia(self):
        self.service.movimiento_repo.listar = MagicMock(return_value=[])
        items = self.service.listar_movimientos(str(self.usuario_id))
        self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()