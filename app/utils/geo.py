from sqlalchemy import func


def point_from_coords(lat: float, lng: float):
    """Punto PostGIS (SRID 4326) para asignar directo a una columna Geography."""
    return func.ST_GeogFromText(f"SRID=4326;POINT({float(lng)} {float(lat)})")
