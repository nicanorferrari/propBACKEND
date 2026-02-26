
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import models, schemas
from database import get_db
from auth import create_access_token, verify_password, get_password_hash

router = APIRouter()

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user: raise HTTPException(401, "Usuario no encontrado")
    
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(401, "Contraseña incorrecta")
        
    token = create_access_token(data={"sub": user.email})
    return {
        "access_token": token, 
        "token_type": "bearer", 
        "user": {
            "id": user.id, 
            "email": user.email, 
            "role": user.role, 
            "tenant_id": user.tenant_id or 1,
            "name": f"{user.first_name} {user.last_name}", 
            "avatar_url": user.avatar_url
        }
    }

@router.post("/demo-login/{role_slug}")
def demo_login(role_slug: str, db: Session = Depends(get_db)):
    email = f"{role_slug.lower()}@urbano-crm.com"
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user: raise HTTPException(404, "Demo user not found")
    token = create_access_token(data={"sub": user.email})
    return {
        "access_token": token, 
        "token_type": "bearer", 
        "user": {
            "id": user.id, 
            "email": user.email, 
            "role": user.role, 
            "name": f"{user.first_name} {user.last_name}", 
            "avatar_url": user.avatar_url
        }
    }
@router.post("/register")
def register(user_data: schemas.UserCreate, db: Session = Depends(get_db)):
    # Check existing user
    existing_user = db.query(models.User).filter(models.User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="El email ya está registrado")
    
    # Create User
    new_user = models.User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        phone_mobile=user_data.phone_mobile,
        role="agent", # Default role for public registration
        avatar_url="https://i.pravatar.cc/150?u=" + user_data.email
    )
    db.add(new_user)
    db.commit()
    return {"message": "Usuario creado exitosamente"}

@router.post("/register-invited")
def register_invited(data: dict, db: Session = Depends(get_db)):
    # Mock validation of token
    if not data.get('token'):
        raise HTTPException(status_code=400, detail="Token requerido")
        
    return register(schemas.UserCreate(**data), db)
