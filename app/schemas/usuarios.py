from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class UsuarioUpdate(BaseModel):
    """Esquema para actualización de usuario (todos los campos opcionales)"""
    nombre: Optional[str] = Field(None, min_length=1, max_length=50)
    apellido: Optional[str] = Field(None, min_length=1, max_length=50)
    email: Optional[EmailStr] = None
    telefono: Optional[str] = Field(None, max_length=20)
    password: Optional[str] = Field(None, min_length=8, max_length=100)
    foto_url: Optional[str] = None
    estado: Optional[str] = None
    configuracion: Optional[dict] = None