import cloudinary
import cloudinary.uploader

from app.config import settings

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
