
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict
import models, schemas
from database import get_db
from auth import get_current_user_email

router = APIRouter()

@router.get("", response_model=List[schemas.ContactResponse])
def list_contacts(search: str = None, limit: int = 1000, offset: int = 0, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    query = db.query(models.Contact).filter(models.Contact.tenant_id == user.tenant_id)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (models.Contact.name.ilike(search_term)) | 
            (models.Contact.email.ilike(search_term)) |
            (models.Contact.phone.ilike(search_term))
        )
        
    return query.order_by(models.Contact.id.desc()).limit(limit).offset(offset).all()

@router.post("", response_model=schemas.ContactResponse)
def create_contact(contact: schemas.ContactCreate, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    
    # Check duplicates
    from sqlalchemy import or_
    filters = []
    if contact.email:
        filters.append(models.Contact.email == contact.email)
    if contact.phone:
        filters.append(models.Contact.phone == contact.phone)
        
    if filters:
        existing = db.query(models.Contact).filter(
            models.Contact.tenant_id == user.tenant_id,
            or_(*filters)
        ).first()
        
        if existing:
            msg = "Contact already exists"
            if contact.email and existing.email == contact.email:
                msg = "Email already registered"
            elif contact.phone and existing.phone == contact.phone:
                msg = "Phone already registered"
            raise HTTPException(status_code=400, detail=msg)

    db_contact = models.Contact(**contact.model_dump(), created_by_id=user.id, tenant_id=user.tenant_id)
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    
    db.add(models.ActivityLog(
        user_id=user.id, 
        action="CREATE", 
        entity_type="CONTACT", 
        entity_id=db_contact.id, 
        description=f"Creó contacto: {db_contact.name}"
    ))
    db.commit()
    return db_contact

@router.get("/{id}", response_model=schemas.ContactResponse)
def get_contact(id: int, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    contact = db.query(models.Contact).filter(models.Contact.id == id, models.Contact.tenant_id == user.tenant_id).first()
    if not contact: raise HTTPException(404)
    return contact

@router.put("/{id}", response_model=schemas.ContactResponse)
def update_contact(id: int, data: schemas.ContactCreate, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    contact = db.query(models.Contact).filter(models.Contact.id == id, models.Contact.tenant_id == user.tenant_id).first()
    old_data = {k: getattr(contact, k) for k in data.dict(exclude_unset=True).keys()}
    for k, v in data.dict(exclude_unset=True).items(): 
        setattr(contact, k, v)
    
    changes = [f"{k}: {old_data[k]} -> {v}" for k, v in data.dict(exclude_unset=True).items() if old_data[k] != v]
    
    if changes:
        db.add(models.ActivityLog(
            user_id=user.id,
            action="UPDATE",
            entity_type="CONTACT",
            entity_id=id,
            description=f"Actualizó contacto ({len(changes)} cambios): " + ", ".join(changes[:3]) + ("..." if len(changes) > 3 else "")
        ))
    
    db.commit()
    db.refresh(contact)
    return contact

@router.delete("/{id}", status_code=204)
def delete_contact(id: int, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    contact = db.query(models.Contact).filter(models.Contact.id == id, models.Contact.tenant_id == user.tenant_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
    
    user = db.query(models.User).filter(models.User.email == email).first()
    
    # Log deletion
    db.add(models.ActivityLog(
        user_id=user.id, 
        action="DELETE", 
        entity_type="CONTACT", 
        entity_id=contact.id,
        description=f"Eliminó contacto: {contact.name}"
    ))
    
    db.delete(contact)
    db.commit()
    return None

@router.get("/{id}/interactions", response_model=List[schemas.InteractionResponse])
def list_interactions(id: int, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    contact = db.query(models.Contact).filter(models.Contact.id == id, models.Contact.tenant_id == user.tenant_id).first()
    if not contact: raise HTTPException(404, "Contact not found")
    
    return db.query(models.ContactInteraction).filter(models.ContactInteraction.contact_id == id).order_by(models.ContactInteraction.date.desc()).all()

@router.post("/{id}/interactions", response_model=schemas.InteractionResponse)
def create_interaction(id: int, interaction: schemas.InteractionCreate, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    contact = db.query(models.Contact).filter(models.Contact.id == id, models.Contact.tenant_id == user.tenant_id).first()
    if not contact: raise HTTPException(404, "Contact not found")
    
    data = interaction.model_dump(exclude_unset=True)
    if "contact_id" in data: del data["contact_id"]
    
    db_interaction = models.ContactInteraction(
        **data,
        contact_id=id,
        user_id=user.id
    )
    db.add(db_interaction)
    
    # Update last_contact_date on Contact
    contact.last_contact_date = db_interaction.date
    
    db.commit()
    db.refresh(db_interaction)
    return db_interaction

@router.post("/{id}/reminders", response_model=schemas.EventResponse)
def create_reminder(id: int, event: schemas.EventCreate, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    contact = db.query(models.Contact).filter(models.Contact.id == id, models.Contact.tenant_id == user.tenant_id).first()
    if not contact: raise HTTPException(404, "Contact not found")
    
    # Force reminder flags and association
    db_event = models.CalendarEvent(
        **event.dict(),
        contact_id=id,
        contact_name=contact.name,
        tenant_id=user.tenant_id,
        agent_id=user.id,
        is_reminder=True # Explicitly a reminder
    )
    
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event

@router.post("/import/google", response_model=Dict)
def import_contacts_from_google(db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    from .google import get_valid_google_token
    import requests
    
    user = db.query(models.User).filter(models.User.email == email).first()
    token = get_valid_google_token(user, db)
    
    if not token:
        raise HTTPException(400, "Google account not connected or token invalid")
        
    # Fetch connections
    # personFields: names,phoneNumbers,emailAddresses
    try:
        res = requests.get(
            "https://people.googleapis.com/v1/people/me/connections",
            headers={"Authorization": f"Bearer {token}"},
            params={"personFields": "names,phoneNumbers,emailAddresses", "pageSize": 1000}
        )
        
        if not res.ok:
            raise HTTPException(400, f"Google API Error: {res.text}")
            
        data = res.json()
        connections = data.get("connections", [])
        
        imported_count = 0
        skipped_count = 0
        
        for person in connections:
            names = person.get("names", [])
            phones = person.get("phoneNumbers", [])
            emails = person.get("emailAddresses", [])
            
            # Name
            contact_name = names[0].get("displayName") if names else "Sin Nombre"
            
            # Phones
            raw_phone = phones[0].get("value") if phones else None
            # Normalize Phone: Strip non-digits
            contact_phone = "".join(filter(str.isdigit, raw_phone)) if raw_phone else None
            
            # Emails
            contact_email = emails[0].get("value") if emails else None
            
            if not contact_phone and not contact_email:
                skipped_count += 1
                continue
                
            # Duplicate Check logic (similar to create_contact but softer)
            existing = None
            if contact_email:
                existing = db.query(models.Contact).filter(models.Contact.tenant_id == user.tenant_id, models.Contact.email == contact_email).first()
            if not existing and contact_phone:
                existing = db.query(models.Contact).filter(models.Contact.tenant_id == user.tenant_id, models.Contact.phone == contact_phone).first()
                
            if existing:
                skipped_count += 1
                continue
                
            # Create
            new_c = models.Contact(
                name=contact_name,
                phone=contact_phone,
                email=contact_email,
                source="GOOGLE_IMPORT",
                status="WARM", # Imported contacts start as WARM?
                type="CLIENT",
                notes="Importado desde Google Contacts",
                created_by_id=user.id,
                tenant_id=user.tenant_id
            )
            db.add(new_c)
            imported_count += 1
            
        db.commit()
        
        # Log activity
        if imported_count > 0:
            db.add(models.ActivityLog(
                user_id=user.id, 
                action="IMPORT", 
                entity_type="CONTACT", 
                entity_id=0, # Generic
                description=f"Importó {imported_count} contactos desde Google."
            ))
            db.commit()
            
        return {"imported": imported_count, "skipped": skipped_count, "total": len(connections)}
        
    except Exception as e:
        raise HTTPException(500, f"Import process failed: {str(e)}")
