from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from app.models.usuario import Usuario

class UsuarioBase(BaseModel):
    """Esquema base con campos comunes de usuario"""
    nombre: str = Field(..., min_length=1, max_length=50)
    apellido: str = Field(..., min_length=1, max_length=50)
    email: EmailStr  # Validación automática de email
    telefono: Optional[str] = Field(None, max_length=20)

class UsuarioCreate(UsuarioBase):
    """Esquema para creación de usuario (registro)"""
    password: str = Field(..., min_length=8, max_length=100)

class UsuarioResponse(UsuarioBase):
    """Esquema para respuesta de usuario (excluye password)"""
    id: str  # UUID convertido a string para JSON
    rol_id: str
    fecha_creacion: datetime
    fecha_actualizacion: datetime

    class Config:
        from_attributes = True  # Permite crear desde objeto ORM

class UsuarioLogin(BaseModel):
    """Esquema para login de usuario"""
    email: EmailStr
    password: str = Field(..., min_length=1)

class Token(BaseModel):
    """Esquema para respuesta de token"""
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    """Esquema para datos dentro del token"""
    user_id: str | None = None