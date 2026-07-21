from math import asin, cos, radians, sin, sqrt

from sqlalchemy import func

_RADIO_TIERRA_METROS = 6_371_000


def point_from_coords(lat: float, lng: float):
    """Punto PostGIS (SRID 4326) para asignar directo a una columna Geography."""
    return func.ST_GeogFromText(f"SRID=4326;POINT({float(lng)} {float(lat)})")


def haversine_metros(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distancia en metros entre dos puntos GPS (fórmula de Haversine, sin ir a la DB).
    Usada para sumar la distancia de un tracking punto-a-punto (ver sesiones de retos RECORRIDO)."""
    lat1_r, lng1_r, lat2_r, lng2_r = map(radians, (lat1, lng1, lat2, lng2))
    delta_lat = lat2_r - lat1_r
    delta_lng = lng2_r - lng1_r
    a = sin(delta_lat / 2) ** 2 + cos(lat1_r) * cos(lat2_r) * sin(delta_lng / 2) ** 2
    return 2 * _RADIO_TIERRA_METROS * asin(sqrt(a))
