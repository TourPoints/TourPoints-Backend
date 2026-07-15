from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.usuario import Usuario, Rol
from app.schemas.usuario import UsuarioCreate, UsuarioResponse, UsuarioLogin, Token
from app.auth.security import hash_password, verify_password, create_access_token
from app.auth.dependencies import get_current_user
from app.core.exceptions import CredentialsException

router = APIRouter()

@router.post("/registro", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
def registrar_usuario(usuario: UsuarioCreate, db: Session = Depends(get_db)):
    """
    Endpoint para registrar un nuevo usuario

    Flujo:
    1. Verificar si el email ya está registrado
    2. Hashear la contraseña
    3. Asignar rol por defecto (usuario común)
    4. Crear y guardar el usuario
    5. Retornar los datos del usuario (sin password)
    """
    # Verificar si el email ya existe
    db_usuario = db.query(Usuario).filter(Usuario.email == usuario.email).first()
    if db_usuario:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email ya está registrado"
        )

    # Hashear la contraseña antes de almacenarla
    hashed_password = hash_password(usuario.password)

    # Obtener rol por defecto (asumiendo que rol_id=2 es "usuario")
    rol_predeterminado = db.query(Rol).filter(Rol.nombre == "usuario").first()
    rol_id = rol_predeterminado.id if rol_predeterminado else 1  # fallback a rol_id=1

    # Crear instancia del usuario
    db_usuario = Usuario(
        **usuario.model_dump(exclude={"password"}),
        password_hash=hashed_password,
        rol_id=rol_id
    )

    db.add(db_usuario)
    db.commit()
    db.refresh(db_usuario)

    return db_usuario

@router.post("/login", response_model=Token)
def login_usuario(usuario: UsuarioLogin, db: Session = Depends(get_db)):
    """
    Endpoint para autenticar usuario y generar token de acceso

    Flujo:
    1. Buscar usuario por email
    2. Verificar que el usuario existe
    3. Verificar la contraseña contra el hash almacenado
    4. Generar token JWT con el ID del usuario como subject
    5. Retornar el token
    """
    # Buscar usuario por email
    db_usuario = db.query(Usuario).filter(Usuario.email == usuario.email).first()
    if not db_usuario:
        raise CredentialsException()  # Usamos la excepción personalizada para consistencia

    # Verificar contraseña
    if not verify_password(usuario.password, db_usuario.password_hash):
        raise CredentialsException()

    # Crear token de acceso
    access_token = create_access_token(
        data={"sub": str(db_usuario.id)}  # El subject es el ID del usuario
    )

    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UsuarioResponse)
def leer_usuario_actual(current_user: Usuario = Depends(get_current_user)):
    """
    Endpoint protegido para obtener los datos del usuario autenticado

    Demuestra cómo usar la dependencia get_current_user para proteger rutas
    """
    return current_user