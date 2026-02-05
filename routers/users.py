
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import models, schemas, auth
from database import get_db
from auth import get_current_user_email, get_password_hash, verify_password
import uuid

router = APIRouter()

@router.get("/profile", response_model=schemas.UserResponse)
def get_profile(email: str = Depends(get_current_user_email), db: Session = Depends(get_db)): 
    user = db.query(models.User).filter(models.User.email == email).first()
    # Generar token si por alguna razón no tiene (fail-safe)
    if user and not user.monitoring_token:
        user.monitoring_token = f"URB-MON-{uuid.uuid4().hex[:12].upper()}"
        db.commit()
    return user

@router.put("/profile", response_model=schemas.UserResponse)
def update_profile(data: schemas.UserProfileUpdate, email: str = Depends(get_current_user_email), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    for k, v in data.dict(exclude_unset=True).items(): setattr(user, k, v)
    db.commit()
    db.refresh(user)
    return user

@router.post("/regenerate-monitoring-token")
def regenerate_monitoring_token(email: str = Depends(get_current_user_email), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user: raise HTTPException(404)
    
    new_token = f"URB-MON-{uuid.uuid4().hex[:12].upper()}"
    user.monitoring_token = new_token
    db.commit()
    return {"monitoring_token": new_token}

@router.post("/change-password")
def change_password(data: schemas.PasswordUpdate, email: str = Depends(get_current_user_email), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user: raise HTTPException(404)
    
    if user.hashed_password and not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(400, "La contraseña actual es incorrecta")
    
    user.hashed_password = get_password_hash(data.new_password)
    db.commit()
    return {"status": "ok", "message": "Contraseña actualizada"}

@router.get("/activity", response_model=List[schemas.ActivityLogResponse])
def get_activity(
    entity_type: str = None, 
    entity_id: int = None, 
    email: str = Depends(get_current_user_email), 
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.email == email).first()
    query = db.query(models.ActivityLog).filter(models.ActivityLog.user_id == user.id)
    
    if entity_type:
        query = query.filter(models.ActivityLog.entity_type == entity_type)
    if entity_id:
        query = query.filter(models.ActivityLog.entity_id == entity_id)
        
    return query.order_by(models.ActivityLog.timestamp.desc()).all()
