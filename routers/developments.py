
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from auth import get_current_user_email
import models, schemas
import uuid
from . import ai_service

router = APIRouter()

def sync_development_ai(db: Session, dev: models.Development):
    """
    Genera el string de contexto y obtiene el embedding de Gemini para proyectos.
    """
    context_str = ai_service.generate_development_context_string(dev)
    vector = ai_service.get_embedding(context_str)
    if vector:
        dev.embedding_proyecto = vector
        db.commit()

@router.get("", response_model=List[schemas.DevelopmentResponse])
def list_developments(db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    return db.query(models.Development).filter(models.Development.tenant_id == user.tenant_id).order_by(models.Development.id.desc()).all()

@router.get("/{dev_id}", response_model=schemas.DevelopmentResponse)
def get_development(dev_id: int, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    dev = db.query(models.Development).filter(models.Development.id == dev_id, models.Development.tenant_id == user.tenant_id).first()
    if not dev: raise HTTPException(404, "Emprendimiento no encontrado")
    return dev

@router.post("", response_model=schemas.DevelopmentResponse)
def create_development(dev: schemas.DevelopmentCreate, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    new_code = f"URB-D{uuid.uuid4().hex[:5].upper()}"
    
    db_dev = models.Development(**dev.dict(exclude={"typologies", "units"}), code=new_code, tenant_id=user.tenant_id)
    db.add(db_dev)
    db.commit()
    db.refresh(db_dev)
    
    for t in dev.typologies:
        db.add(models.Typology(**t.dict(), development_id=db_dev.id))
    
    db.commit()
    db.refresh(db_dev)

    # Pipeline IA
    sync_development_ai(db, db_dev)
    
    db.add(models.ActivityLog(user_id=user.id, action="CREATE", entity_type="DEVELOPMENT", entity_id=db_dev.id, description=f"Creó emprendimiento: {db_dev.name}"))
    db.commit()
    return db_dev

@router.delete("/{dev_id}")
def delete_development(dev_id: int, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    dev = db.query(models.Development).filter(models.Development.id == dev_id, models.Development.tenant_id == user.tenant_id).first()
    if not dev: raise HTTPException(404)
    db.delete(dev)
    db.commit()
    return {"status": "ok"}
