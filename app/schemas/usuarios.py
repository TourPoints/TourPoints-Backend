from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class UsuarioUpdate(BaseModel):
    """Schema for updating a user (all fields optional)"""
    nombre: Optional[str] = Field(None, min_length=1, max_length=50)
    apellido: Optional[str] = Field(None, min_length=1, max_length=50)
    email: Optional[EmailStr] = None
    telefono: Optional[str] = Field(None, max_length=20)
    password: Optional[str] = Field(None, min_length=8, max_length=100)
    foto_url: Optional[str] = None
    estado: Optional[str] = None
    configuracion: Optional[dict] = None
    rol_id: Optional[int] = Field(None, description="Role to assign (only an admin can set this)")


class ChangePasswordRequest(BaseModel):
    """Schema for changing the authenticated user's password"""
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=100)