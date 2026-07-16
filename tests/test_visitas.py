from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException

from app.models.enums import MetodoValidacion
from app.schemas.visita import VisitaCreate
from app.services.visitas_service import VisitasService


def _regla(id_, prioridad, configuracion):
    return SimpleNamespace(id=id_, prioridad=prioridad, configuracion=configuracion)


class VisitasServiceTests(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        query = self.db.query.return_value
        query.filter.return_value = query
        query.order_by.return_value = query
        self.service = VisitasService(self.db)
        self.reglas = [
            _regla("base", 0, {"evento": "VISITA", "puntos": 100}),
            _regla(
                "cultura", 10, {"evento": "VISITA", "categoria": "Cultura", "puntos": 220}
            ),
            _regla(
                "bocas",
                20,
                {"evento": "VISITA", "poi_slug": "bocas-de-ceniza", "puntos": 320},
            ),
        ]
        query.all.return_value = self.reglas[::-1]

    def test_regla_categoria_gana_a_la_base(self):
        poi = SimpleNamespace(slug="museo-del-caribe")

        puntos, regla_id = self.service._puntos_para_visita(poi, "Cultura")

        self.assertEqual((puntos, regla_id), (220, "cultura"))

    def test_regla_poi_slug_gana_a_la_categoria(self):
        poi = SimpleNamespace(slug="bocas-de-ceniza")

        puntos, regla_id = self.service._puntos_para_visita(poi, "Naturaleza")

        self.assertEqual((puntos, regla_id), (320, "bocas"))

    def test_regla_base_es_fallback_del_seed(self):
        poi = SimpleNamespace(slug="otro-poi")

        puntos, regla_id = self.service._puntos_para_visita(poi, "Otra")

        self.assertEqual((puntos, regla_id), (100, "base"))

    def test_qr_se_rechaza_hasta_tener_validacion_real(self):
        datos = VisitaCreate(
            poi_id="00000000-0000-0000-0000-000000000001",
            ubicacion_usuario="POINT(-74.0 4.0)",
            precision_metros=15,
            metodo_validacion=MetodoValidacion.QR,
        )

        with self.assertRaisesRegex(HTTPException, "Solo se admite metodo_validacion=GPS") as error:
            self.service.registrar("usuario", datos)

        self.assertEqual(error.exception.status_code, 422)
