from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime
from uuid import UUID


class UsuarioBase(BaseModel):
    """Base schema with common user fields"""
    nombre: str = Field(..., min_length=1, max_length=50)
    apellido: str = Field(..., min_length=1, max_length=50)
    email: EmailStr
    telefono: Optional[str] = Field(None, max_length=20)


class UsuarioCreate(UsuarioBase):
    """Schema for creating a user (registration)"""
    password: str = Field(..., min_length=8, max_length=100)
    rol_id: Optional[int] = Field(None, description="Role to assign (only an admin can set this)")


class UsuarioResponse(UsuarioBase):
    """Schema for a user response (excludes password)"""
    id: UUID
    rol_id: int
    estado: str
    foto_url: Optional[str] = None
    configuracion: dict
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True  # Allows creation from an ORM object


class PaginatedUsuariosResponse(BaseModel):
    """Pagination wrapper consistent with the rest of the listings (POI, cities, categories)."""
    items: List[UsuarioResponse]
    total: int
    page: int
    page_size: int


class UsuarioLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str = Field(..., min_length=1)


class Token(BaseModel):
    """Schema for a token response"""
    access_token: str
    token_type: str = "bearer"
