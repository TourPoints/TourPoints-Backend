"""Generadores de codigo QR: canjes (token aleatorio) y check-in de POI (HMAC).

Para el MVP no se renderiza un PNG: se genera un token unico por canje que el
aliado comercial puede validar. El token se genera ANTES del insert (no
depende del id del canje) porque la columna codigo_qr es NOT NULL y UNIQUE,
y el trigger de stock se ejecuta BEFORE INSERT."""
import hmac
import secrets
from hashlib import sha256

from app.config import settings


def generar_qr_canje() -> str:
    """Devuelve un string unico y no adivinable para un canje nuevo."""
    token = secrets.token_urlsafe(32)
    return f"TP-CANJE-{token}"


def generar_qr_checkin_poi(poi_id: str) -> str:
    """Código QR de check-in de un POI: HMAC(SECRET_KEY, poi_id), determinístico.

    No requiere columna nueva en `poi` — se deriva siempre igual a partir del
    `poi_id` (que no cambia) y el secreto del backend, así que es seguro
    imprimirlo una sola vez en el sitio físico y no volver a generarlo.
    Solo alguien con acceso a SECRET_KEY puede producir un código válido para
    un poi_id dado, así que no sirve conocer el poi_id (público) para falsear
    un check-in por QR.
    """
    digest = hmac.new(settings.secret_key.encode(), str(poi_id).encode(), sha256).hexdigest()[:20]
    return f"TP-POI-{digest}"


def verificar_qr_checkin_poi(poi_id: str, codigo_qr: str) -> bool:
    """Compara en tiempo constante contra el código esperado para ese POI."""
    esperado = generar_qr_checkin_poi(poi_id)
    return hmac.compare_digest(esperado, codigo_qr or "")
