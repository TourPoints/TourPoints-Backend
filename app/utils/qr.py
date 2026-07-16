"""Generador de codigo QR para canjes.

Para el MVP no se renderiza un PNG: se genera un token unico por canje que el
aliado comercial puede validar. El token se genera ANTES del insert (no
depende del id del canje) porque la columna codigo_qr es NOT NULL y UNIQUE,
y el trigger de stock se ejecuta BEFORE INSERT."""
import secrets


def generar_qr_canje() -> str:
    """Devuelve un string unico y no adivinable para un canje nuevo."""
    token = secrets.token_urlsafe(32)
    return f"TP-CANJE-{token}"
