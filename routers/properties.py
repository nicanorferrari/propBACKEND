
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session, joinedload, defer
from typing import List
import models, schemas
from database import get_db
from auth import get_current_user_email
import datetime
from . import ai_service
from background_tasks import background_sync_property_ai

router = APIRouter()


def sync_property_ai(db: Session, property: models.Property):
    """
    Genera el string de contexto y obtiene el embedding de Gemini.
    """
    context_str = ai_service.generate_property_context_string(property)
    property.search_content = context_str
    vector = ai_service.get_embedding(context_str)
    if vector:
        property.embedding_descripcion = vector
        db.commit()

@router.get("/public/{code}", response_model=schemas.PropertyResponse)
def get_public_property(code: str, db: Session = Depends(get_db)):
    # Try ID first if it looks like an int to support legacy links or direct ID access
    query = db.query(models.Property).filter(models.Property.status != "Deleted")
    
    if code.isdigit():
        prop = query.filter(models.Property.id == int(code)).first()
        if prop: return prop
        
    prop = query.filter(models.Property.code == code).first()
    if not prop:
        raise HTTPException(404, "Propiedad no encontrada")
    return prop
@router.get("/minimal")
def list_minimal_properties(db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user: return []
    props = db.query(models.Property.id, models.Property.address, models.Property.owner_id).filter(
        models.Property.tenant_id == user.tenant_id,
        models.Property.status != "Deleted",
        models.Property.owner_id != None
    ).all()
    return [{"id": p.id, "address": p.address, "owner_id": p.owner_id} for p in props]

@router.get("", response_model=List[schemas.PropertyResponse])
def list_properties(
    limit: int = 100, 
    offset: int = 0, 
    search: str = None, 
    operation: str = None, 
    property_type: str = None, 
    min_price: float = None, 
    max_price: float = None, 
    bedrooms: int = None,
    db: Session = Depends(get_db), 
    email: str = Depends(get_current_user_email)
):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user: return []
    
    query = db.query(models.Property).options(
        defer(models.Property.embedding_descripcion),
        defer(models.Property.search_content),
        defer(models.Property.description)
    ).filter(
        models.Property.tenant_id == user.tenant_id,
        models.Property.status != "Deleted"
    )

    # Server-side Filtering
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (models.Property.address.ilike(search_term)) | 
            (models.Property.title.ilike(search_term)) |
            (models.Property.code.ilike(search_term))
        )
    
    if operation and operation != 'All':
        query = query.filter(models.Property.operation == operation)
        
    if property_type and property_type != 'All':
        query = query.filter(models.Property.type == property_type)
        
    if min_price:
        query = query.filter(models.Property.price >= min_price)
        
    if max_price:
        query = query.filter(models.Property.price <= max_price)
        
    if bedrooms and bedrooms != 'All': 
        if str(bedrooms) == '4': # Logic for 4+
            query = query.filter(models.Property.bedrooms >= 4)
        else:
            query = query.filter(models.Property.bedrooms == bedrooms)

    return query.options(joinedload(models.Property.assigned_agent)).order_by(models.Property.id.desc()).limit(limit).offset(offset).all()

@router.get("/{prop_id}", response_model=schemas.PropertyResponse)
def get_property(prop_id: int, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    prop = db.query(models.Property).filter(
        models.Property.id == prop_id, 
        models.Property.tenant_id == user.tenant_id,
        models.Property.status != "Deleted"
    ).first()
    if not prop:
        raise HTTPException(404, "Propiedad no encontrada")
    return prop

@router.post("", response_model=schemas.PropertyResponse)
def create_property(prop: schemas.PropertyCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    code = f"URB-{uuid.uuid4().hex[:6].upper()}"
    
    db_prop = models.Property(**prop.dict(), code=code, tenant_id=user.tenant_id)
    db.add(db_prop)
    db.commit()
    db.refresh(db_prop)
    
    # Pipeline IA en Background
    background_tasks.add_task(background_sync_property_ai, db_prop.id)
    
    db.add(models.ActivityLog(
        user_id=user.id, 
        action="CREATE", 
        entity_type="PROPERTY", 
        entity_id=db_prop.id, 
        description=f"Creó propiedad: {db_prop.address}"
    ))
    db.commit()
    return db_prop

@router.put("/{prop_id}", response_model=schemas.PropertyResponse)
def update_property(prop_id: int, data: schemas.PropertyCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    prop = db.query(models.Property).filter(models.Property.id == prop_id, models.Property.tenant_id == user.tenant_id).first()
    if not prop: raise HTTPException(404)
    
    for k, v in data.dict().items(): 
        setattr(prop, k, v)
    
    db.commit()
    
    # Actualizar Pipeline IA en Background
    background_tasks.add_task(background_sync_property_ai, prop.id)
        
    db.add(models.ActivityLog(user_id=user.id, action="UPDATE", entity_type="PROPERTY", entity_id=prop.id, description=f"Actualizó propiedad: {prop.address}"))
    db.commit()
    db.refresh(prop)
    return prop

@router.delete("/{prop_id}")
def delete_property(prop_id: int, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    prop = db.query(models.Property).filter(models.Property.id == prop_id, models.Property.tenant_id == user.tenant_id).first()
    if not prop: raise HTTPException(404, "Propiedad no encontrada")
    
    try:
        # SOFT DELETE: Only change status
        prop.status = "Deleted"
        
        # Opcional: Podríamos querer borrar el embedding para que no salga en búsquedas vectoriales sucias
        # prop.embedding_descripcion = None
        # prop.search_content = None 
        # Pero mejor dejemos el status manejarlo y filtremos por status en todos lados.
        
        addr = prop.address
        db.add(models.ActivityLog(user_id=user.id, action="DELETE", entity_type="PROPERTY", entity_id=prop.id, description=f"Eliminó propiedad (Soft Delete): {addr}"))
        db.commit()
        return {"status": "ok", "message": "Propiedad eliminada correctamente (lógico)"}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Error eliminando propiedad: {str(e)}")

@router.patch("/{prop_id}")
def patch_property(prop_id: int, data: dict, background_tasks: BackgroundTasks, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    prop = db.query(models.Property).filter(models.Property.id == prop_id, models.Property.tenant_id == user.tenant_id).first()
    if not prop: raise HTTPException(404, "Propiedad no encontrada")
    
    for k, v in data.items():
        if hasattr(prop, k):
            setattr(prop, k, v)
    
    db.commit()
    db.refresh(prop)
    
    # Trigger AI sync si title o description cambia
    if "description" in data or "title" in data:
        background_tasks.add_task(background_sync_property_ai, prop.id)
        
    db.add(models.ActivityLog(user_id=user.id, action="PATCH", entity_type="PROPERTY", entity_id=prop.id, description=f"Actualización parcial de propiedad: {prop.address}"))
    db.commit()
    return prop
