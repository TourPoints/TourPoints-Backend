import re

import cloudinary
import cloudinary.uploader

from app.config import settings

# Captura todo entre "/upload/" (saltando el "v<version>/" si está) y la
# extensión final. No guardamos public_id en la BD (imagenes_poi.url es lo
# único que persiste) así que hay que derivarlo de la URL para poder borrar
# el asset en Cloudinary.
_PUBLIC_ID_RE = re.compile(r"/upload/(?:v\d+/)?(.+)\.[a-zA-Z0-9]+$")

cloudinary.config(
    cloud_name=settings.cloudinary_cloud_name,
    api_key=settings.cloudinary_api_key,
    api_secret=settings.cloudinary_api_secret,
    secure=True,
)


def upload_usuario_foto(file, usuario_id: str) -> dict:
    return cloudinary.uploader.upload(file, folder=f"tourpoints/usuarios/{usuario_id}")


def upload_poi_imagen(file, poi_id: str) -> dict:
    return cloudinary.uploader.upload(file, folder=f"tourpoints/pois/{poi_id}")


def delete_imagen(public_id: str) -> None:
    cloudinary.uploader.destroy(public_id)


def extraer_public_id(url: str) -> "str | None":
    """Deriva el public_id de Cloudinary a partir de la secure_url guardada."""
    match = _PUBLIC_ID_RE.search(url)
    return match.group(1) if match else None
