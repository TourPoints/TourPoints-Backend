from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.security import authenticate_user, create_access_token, hash_password
from app.core.exceptions import CredentialsException
from app.core.rate_limit import limiter
from app.database import get_db
from app.models.usuario import Rol, Usuario
from app.schemas.usuario import Token, UsuarioCreate, UsuarioLogin, UsuarioResponse

router = APIRouter(tags=["auth"])


@router.post("/register", response_model=UsuarioResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def register_user(request: Request, usuario: UsuarioCreate, db: Session = Depends(get_db)):
    """Registers a new user with the default role and a hashed password."""
    existing_user = db.query(Usuario).filter(Usuario.email == usuario.email).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El email ya está registrado")

    hashed_password = hash_password(usuario.password)
    role = db.query(Rol).filter(Rol.nombre.ilike("usuario")).first()
    role_id = role.id if role else 2

    db_user = Usuario(
        **usuario.model_dump(exclude={"password", "rol_id"}),
        password_hash=hashed_password,
        rol_id=role_id,
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
def login_user(request: Request, usuario: UsuarioLogin, db: Session = Depends(get_db)):
    """Authenticates the user and returns a JWT access token."""
    db_user = db.query(Usuario).filter(Usuario.email == usuario.email).filter(Usuario.deleted_at.is_(None)).first()
    if not db_user:
        raise CredentialsException("Credenciales inválidas")

    authenticate_user(db_user, usuario.password)

    access_token = create_access_token(
        data={"sub": str(db_user.id), "role": "admin" if db_user.rol_id == 1 else "user", "status": db_user.estado}
    )
    return {"access_token": access_token, "token_type": "bearer"}