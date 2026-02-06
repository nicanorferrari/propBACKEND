from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
import models, schemas
from database import get_db
from auth import get_current_user_email
import datetime

class DealCommentCreate(schemas.BaseModel):
    content: str

router = APIRouter()

# --- PIPELINES ---

@router.get("/pipelines", response_model=List[schemas.PipelineResponse])
def list_pipelines(db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return db.query(models.Pipeline).filter(models.Pipeline.tenant_id == user.tenant_id).all()

@router.post("/pipelines", response_model=schemas.PipelineResponse)
def create_pipeline(pipeline: schemas.PipelineCreate, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db_pipeline = models.Pipeline(
        name=pipeline.name,
        is_active=pipeline.is_active,
        tenant_id=user.tenant_id
    )
    db.add(db_pipeline)
    db.commit()
    db.refresh(db_pipeline)
    
    # Add stages if provided
    for i, stage_data in enumerate(pipeline.stages):
        db_stage = models.PipelineStage(
            pipeline_id=db_pipeline.id,
            name=stage_data.name,
            order=stage_data.order or i,
            color=stage_data.color
        )
        db.add(db_stage)
    
    db.commit()
    db.refresh(db_pipeline)
    return db_pipeline

@router.patch("/stages/{stage_id}", response_model=schemas.PipelineStageResponse)
def update_stage(stage_id: int, stage_update: dict, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    db_stage = db.query(models.PipelineStage).join(models.Pipeline).filter(
        models.PipelineStage.id == stage_id,
        models.Pipeline.tenant_id == user.tenant_id
    ).first()
    
    if not db_stage:
        raise HTTPException(status_code=404, detail="Stage not found")
    
    for key, value in stage_update.items():
        if hasattr(db_stage, key):
            setattr(db_stage, key, value)
    
    db.commit()
    db.refresh(db_stage)
    return db_stage

# --- DEALS ---

@router.get("/deals", response_model=List[schemas.DealResponse])
def list_deals(
    stage_id: Optional[int] = None,
    status: Optional[str] = None,
    agent_id: Optional[int] = None,
    db: Session = Depends(get_db), 
    email: str = Depends(get_current_user_email)
):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    query = db.query(models.Deal).options(
        joinedload(models.Deal.property),
        joinedload(models.Deal.contact),
        joinedload(models.Deal.agent),
        joinedload(models.Deal.comments),
        joinedload(models.Deal.history)
    ).filter(models.Deal.tenant_id == user.tenant_id)
    
    if stage_id:
        query = query.filter(models.Deal.pipeline_stage_id == stage_id)
    if status:
        query = query.filter(models.Deal.status == status)
    if agent_id:
        query = query.filter(models.Deal.assigned_agent_id == agent_id)
        
    return query.order_by(models.Deal.created_at.desc()).all()

@router.post("/deals", response_model=schemas.DealResponse)
def create_deal(deal: schemas.DealCreate, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db_deal = models.Deal(**deal.dict(), tenant_id=user.tenant_id)
    db.add(db_deal)
    db.commit()
    db.refresh(db_deal)

    # Record Interaction in Contact's Bitácora
    if db_deal.contact_id:
        interaction_notes = f"Oportunidad generada: {db_deal.title}"
        if db_deal.value:
            interaction_notes += f" - Valor: {db_deal.currency} {db_deal.value}"
        
        if db_deal.requirements:
            interaction_notes += f"\nBúsqueda: {db_deal.requirements}"
        
        db_interaction = models.ContactInteraction(
            contact_id=db_deal.contact_id,
            user_id=user.id,
            type="LEAD_CREATED",
            notes=interaction_notes,
            deal_id=db_deal.id
        )
        db.add(db_interaction)
        
        # Update last_contact_date
        db_contact = db.query(models.Contact).filter(models.Contact.id == db_deal.contact_id).first()
        if db_contact:
            db_contact.last_contact_date = datetime.datetime.now(datetime.timezone.utc)
        
        db.commit()

    return db.query(models.Deal).options(
        joinedload(models.Deal.property),
        joinedload(models.Deal.contact),
        joinedload(models.Deal.agent),
        joinedload(models.Deal.comments),
        joinedload(models.Deal.history)
    ).filter(models.Deal.id == db_deal.id).first()

@router.put("/deals/{deal_id}/move", response_model=schemas.DealResponse)
def move_deal(deal_id: int, stage_id: int, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db_deal = db.query(models.Deal).filter(models.Deal.id == deal_id, models.Deal.tenant_id == user.tenant_id).first()
    
    if not db_deal:
        raise HTTPException(status_code=404, detail="Deal not found")
        
    # Verify stage exists and belongs to a pipeline (ideally check if same pipeline)
    stage = db.query(models.PipelineStage).filter(models.PipelineStage.id == stage_id).first()
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found")
        
    previous_stage_id = db_deal.pipeline_stage_id
    db_deal.pipeline_stage_id = stage_id
    db_deal.updated_at = datetime.datetime.utcnow()
    
    # Record History
    db_history = models.DealHistory(
        deal_id=deal_id,
        from_stage_id=previous_stage_id,
        to_stage_id=stage_id,
        user_id=user.id
    )
    db.add(db_history)
    
    db.commit()
    return db.query(models.Deal).options(
        joinedload(models.Deal.property),
        joinedload(models.Deal.contact),
        joinedload(models.Deal.agent),
        joinedload(models.Deal.comments),
        joinedload(models.Deal.history)
    ).filter(models.Deal.id == deal_id).first()

@router.post("/deals/{deal_id}/comments", response_model=schemas.DealCommentResponse)
def add_deal_comment(
    deal_id: int, 
    comment: DealCommentCreate, 
    db: Session = Depends(get_db), 
    email: str = Depends(get_current_user_email)
):
    user = db.query(models.User).filter(models.User.email == email).first()
    db_deal = db.query(models.Deal).filter(models.Deal.id == deal_id, models.Deal.tenant_id == user.tenant_id).first()
    if not db_deal:
        raise HTTPException(status_code=404, detail="Deal not found")
        
    db_comment = models.DealComment(
        deal_id=deal_id,
        user_id=user.id,
        content=comment.content
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    return db_comment

@router.post("/deals/{deal_id}/won", response_model=schemas.DealResponse)
def mark_deal_won(deal_id: int, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db_deal = db.query(models.Deal).filter(models.Deal.id == deal_id, models.Deal.tenant_id == user.tenant_id).first()
    
    if not db_deal:
        raise HTTPException(status_code=404, detail="Deal not found")
        
    db_deal.status = "WON"
    db_deal.updated_at = datetime.datetime.utcnow()
    db.commit()
    return db.query(models.Deal).options(
        joinedload(models.Deal.property),
        joinedload(models.Deal.contact),
        joinedload(models.Deal.agent),
        joinedload(models.Deal.comments),
        joinedload(models.Deal.history)
    ).filter(models.Deal.id == deal_id).first()

@router.post("/deals/{deal_id}/lost", response_model=schemas.DealResponse)
def mark_deal_lost(deal_id: int, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    db_deal = db.query(models.Deal).filter(models.Deal.id == deal_id, models.Deal.tenant_id == user.tenant_id).first()
    
    if not db_deal:
        raise HTTPException(status_code=404, detail="Deal not found")
        
    db_deal.status = "LOST"
    db_deal.updated_at = datetime.datetime.utcnow()
    db.commit()
    return db.query(models.Deal).options(
        joinedload(models.Deal.property),
        joinedload(models.Deal.contact),
        joinedload(models.Deal.agent),
        joinedload(models.Deal.comments),
        joinedload(models.Deal.history)
    ).filter(models.Deal.id == deal_id).first()

@router.delete("/deals/{deal_id}")
def delete_deal(deal_id: int, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    db_deal = db.query(models.Deal).filter(models.Deal.id == deal_id, models.Deal.tenant_id == user.tenant_id).first()
    
    if not db_deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    db.delete(db_deal)
    db.commit()
    return {"message": "Deal deleted successfully"}

@router.put("/deals/{deal_id}", response_model=schemas.DealResponse)
def update_deal(deal_id: int, deal_update: schemas.DealUpdate, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    db_deal = db.query(models.Deal).filter(models.Deal.id == deal_id, models.Deal.tenant_id == user.tenant_id).first()
    
    if not db_deal:
        raise HTTPException(status_code=404, detail="Deal not found")
    
    update_data = deal_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_deal, key, value)
    
    db_deal.updated_at = datetime.datetime.utcnow()
    db.commit()
    return db.query(models.Deal).options(
        joinedload(models.Deal.property),
        joinedload(models.Deal.contact),
        joinedload(models.Deal.agent),
        joinedload(models.Deal.comments),
        joinedload(models.Deal.history)
    ).filter(models.Deal.id == deal_id).first()
