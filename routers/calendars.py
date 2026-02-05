
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from auth import get_current_user_email
import models, schemas

from routers.google import get_valid_google_token
import requests
import os
from datetime import datetime

router = APIRouter()

@router.get("/events", response_model=List[schemas.EventResponse])
def list_events(db: Session = Depends(get_db), current_email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == current_email).first()
    if user.role in ["SUPER_ADMIN", "BROKER_ADMIN"]: 
        return db.query(models.CalendarEvent).filter(models.CalendarEvent.status != 'CANCELLED', models.CalendarEvent.tenant_id == user.tenant_id).all()
    return db.query(models.CalendarEvent).filter(models.CalendarEvent.agent_id == user.id, models.CalendarEvent.status != 'CANCELLED').all()

@router.post("/events", response_model=schemas.EventResponse)
def create_event(data: schemas.EventCreate, db: Session = Depends(get_db), current_email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == current_email).first()
    db_event = models.CalendarEvent(**data.dict(), agent_id=user.id, tenant_id=user.tenant_id)
    db.add(db_event)
    db.add(models.ActivityLog(user_id=user.id, action="CREATE", entity_type="EVENT", entity_id=None, description=f"Agendó: {db_event.title}"))
    
    # Update last_contact_date logic
    if data.contact_id:
        contact = db.query(models.Contact).filter(models.Contact.id == data.contact_id).first()
        if contact:
            contact.last_contact_date = datetime.utcnow()
            db.add(contact)
            
    db.commit()
    db.refresh(db_event)
    
    # INTENTO SYNC GOOGLE
    try:
        token = get_valid_google_token(user, db)
        if token:
            print(f"Syncing event {db_event.id} to Google Calendar...")
            google_body = {
                "summary": db_event.title,
                "description": db_event.description or "",
                "start": {
                    "dateTime": db_event.start_time.isoformat(),
                    "timeZone": "America/Argentina/Buenos_Aires"
                },
                "end": {
                    "dateTime": db_event.end_time.isoformat(),
                    "timeZone": "America/Argentina/Buenos_Aires"
                },
                # location: data.property_address <-- si lo tuviéramos
            }
            res = requests.post(
                "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                headers={"Authorization": f"Bearer {token}"},
                json=google_body
            )
            if res.ok:
                g_id = res.json().get("id")
                db_event.google_event_id = g_id
                db.commit()
                print(f"Synced! Google ID: {g_id}")
            else:
                print(f"Failed to sync Google: {res.text}")
    except Exception as e:
        print(f"Error syncing to Google: {e}")

    return db_event

@router.delete("/events/{id}")
def delete_event(id: int, db: Session = Depends(get_db), current_email: str = Depends(get_current_user_email)):
    # Necesitamos current_email para obtener el usuario y su token para borrar en Google
    user = db.query(models.User).filter(models.User.email == current_email).first()
    
    event = db.query(models.CalendarEvent).filter(models.CalendarEvent.id == id).first()
    if not event: raise HTTPException(404)
    
    # INTENTO DELETE GOOGLE
    if event.google_event_id:
        try:
            token = get_valid_google_token(user, db)
            if token:
                requests.delete(
                    f"https://www.googleapis.com/calendar/v3/calendars/primary/events/{event.google_event_id}",
                    headers={"Authorization": f"Bearer {token}"}
                )
        except Exception as e:
            print(f"Error deleting from Google: {e}")

    db.delete(event)
    db.commit()
    return {"status": "ok"}
