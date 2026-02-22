
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import models, schemas
from database import get_db
from auth import get_current_user_email, get_password_hash
import uuid

router = APIRouter()

@router.get("", response_model=List[schemas.UserResponse])
def list_team(search: str = None, limit: int = 1000, db: Session = Depends(get_db), current_email: str = Depends(get_current_user_email)): 
    """Retorna todos los usuarios de la inmobiliaria."""
    user = db.query(models.User).filter(models.User.email == current_email).first()
    query = db.query(models.User).filter(
        models.User.tenant_id == user.tenant_id,
        models.User.is_active == True
    )
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (models.User.first_name.ilike(search_term)) | 
            (models.User.last_name.ilike(search_term)) |
            (models.User.email.ilike(search_term))
        )
        
    return query.order_by(models.User.id.asc()).limit(limit).all()

@router.put("/{user_id}", response_model=schemas.UserResponse)
def update_member(user_id: int, data: schemas.UserProfileUpdate, db: Session = Depends(get_db), current_admin: str = Depends(get_current_user_email)):
    # Verificar que el que edita es admin
    admin = db.query(models.User).filter(models.User.email == current_admin).first()
    if not admin or admin.role not in ["SUPER_ADMIN", "BROKER_ADMIN"]:
        raise HTTPException(403, "No tienes permisos para gestionar el equipo")
        
    user = db.query(models.User).filter(
        models.User.id == user_id, 
        models.User.tenant_id == admin.tenant_id,
        models.User.is_active == True
    ).first()
    if not user:
        raise HTTPException(404, "Miembro no encontrado")
        
    update_data = data.dict(exclude_unset=True)

    if "password" in update_data:
        password = update_data.pop("password")
        if password:
            update_data["hashed_password"] = get_password_hash(password)

    if "email" in update_data:
        new_email = update_data["email"]
        if new_email != user.email:
            existing = db.query(models.User).filter(models.User.email == new_email).first()
            if existing:
                raise HTTPException(400, "El email ya está en uso")

    for key, value in update_data.items():
        setattr(user, key, value)
        
    db.commit()
    db.refresh(user)
    return user

@router.post("/{user_id}/regenerate-token")
def admin_regenerate_token(user_id: int, db: Session = Depends(get_db), current_admin: str = Depends(get_current_user_email)):
    # Verificar permisos de administrador
    admin = db.query(models.User).filter(models.User.email == current_admin).first()
    if not admin or admin.role not in ["SUPER_ADMIN", "BROKER_ADMIN"]:
        raise HTTPException(403, "No autorizado para regenerar tokens ajenos")
        
    user = db.query(models.User).filter(
        models.User.id == user_id, 
        models.User.tenant_id == admin.tenant_id,
        models.User.is_active == True
    ).first()
    if not user:
        raise HTTPException(404, "Usuario no encontrado")
    
    new_token = f"URB-MON-{uuid.uuid4().hex[:12].upper()}"
    user.monitoring_token = new_token
    
    db.add(models.ActivityLog(
        user_id=admin.id,
        action="UPDATE",
        entity_type="USER",
        entity_id=user_id,
        description=f"Regeneró el token de monitoreo para {user.email}"
    ))
    
    db.commit()
    return {"monitoring_token": new_token}

@router.delete("/{user_id}")
def delete_member(user_id: int, db: Session = Depends(get_db), current_email: str = Depends(get_current_user_email)):
    admin = db.query(models.User).filter(models.User.email == current_email).first()
    user = db.query(models.User).filter(
        models.User.id == user_id, 
        models.User.tenant_id == admin.tenant_id,
        models.User.is_active == True
    ).first()
    
    if not user: raise HTTPException(404)
    
    user.is_active = False
    
    db.add(models.ActivityLog(
        user_id=admin.id,
        action="DELETE",
        entity_type="USER",
        entity_id=user_id,
        description=f"Eliminó miembro (Soft Delete): {user.email}"
    ))
    db.commit()
    return {"status": "ok", "message": "Miembro desactivado correctamente"}
