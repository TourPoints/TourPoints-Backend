from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


class UsuarioBase(BaseModel):
    """Esquema base con campos comunes de usuario"""
    nombre: str = Field(..., min_length=1, max_length=50)
    apellido: str = Field(..., min_length=1, max_length=50)
    email: EmailStr
    telefono: Optional[str] = Field(None, max_length=20)


class UsuarioCreate(UsuarioBase):
    """Esquema para creación de usuario (registro)"""
    password: str = Field(..., min_length=8, max_length=100)
    rol_id: Optional[int] = Field(None, description="Rol a asignar (solo admin puede definirlo)")


class UsuarioResponse(UsuarioBase):
    """Esquema para respuesta de usuario (excluye password)"""
    id: UUID
    rol_id: int
    estado: str
    foto_url: Optional[str] = None
    configuracion: dict
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

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
