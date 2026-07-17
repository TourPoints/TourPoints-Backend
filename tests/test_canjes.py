from datetime import datetime, timezone
from hashlib import sha1
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock
from uuid import UUID

from app.core.exceptions import InternalServiceError
from app.services.recompensas_service import RecompensasService


class CanjearServiceTests(unittest.TestCase):
    def test_canjear_uses_two_signed_integer_advisory_lock_keys(self):
        db = MagicMock()
        db.get_bind.return_value = SimpleNamespace(
            dialect=SimpleNamespace(name="postgresql")
        )
        service = RecompensasService(db)

        recompensa = SimpleNamespace(
            id=UUID("00000000-0000-0000-0000-000000000011"),
            poi_id=None,
            nombre="Café",
            descripcion=None,
            stock=2,
            puntos=10,
            estado="APROBADO",
        )
        canje = SimpleNamespace(
            id=UUID("00000000-0000-0000-0000-000000000022"),
            origen="PUNTOS",
            codigo_qr="qr-de-prueba",
            estado="PENDIENTE",
            fecha_expira=datetime(2026, 1, 2, tzinfo=timezone.utc),
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        service.recompensa_repo.obtener_con_lock = MagicMock(return_value=recompensa)
        service.puntos_repo.obtener_saldo = MagicMock(return_value=20)
        service.canje_repo.crear = MagicMock(return_value=canje)
        service.movimiento_repo.crear = MagicMock()

        usuario_id = "00000000-0000-0000-0000-000000000001"
        service.canjear(usuario_id, str(recompensa.id))

        statement, params = db.execute.call_args.args
        digest = sha1(usuario_id.encode()).digest()
        self.assertEqual(str(statement), "SELECT pg_advisory_xact_lock(:key1, :key2)")
        self.assertEqual(
            params,
            {
                "key1": int.from_bytes(digest[:4], byteorder="big", signed=True),
                "key2": int.from_bytes(digest[4:8], byteorder="big", signed=True),
            },
        )
        db.commit.assert_called_once()


    def test_canjear_rolls_back_and_translates_unexpected_errors(self):
        db = MagicMock()
        service = RecompensasService(db)
        service._canjear = MagicMock(side_effect=RuntimeError("fallo inesperado"))

        with self.assertRaisesRegex(InternalServiceError, "Error en el proceso de canje"):
            service.canjear("usuario", "recompensa")

        db.rollback.assert_called_once()
