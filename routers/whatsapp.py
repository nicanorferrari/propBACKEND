import os
import requests
import logging
import re
from fastapi import APIRouter, Depends, HTTPException, Body, Request, BackgroundTasks
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_user_email
from datetime import datetime, timedelta, timezone
import models
import json

def json_dumps(obj):
    return json.dumps(obj, ensure_ascii=True)

router = APIRouter()
logger = logging.getLogger("urbanocrm.whatsapp")

WA_ACCESS_TOKEN = os.getenv("WA_ACCESS_TOKEN", "").strip()
WA_PHONE_NUMBER_ID = os.getenv("WA_PHONE_NUMBER_ID", "").strip()

def call_wa_cloud(endpoint: str, payload: dict = None, method: str = "POST"):
    if not WA_ACCESS_TOKEN or not WA_PHONE_NUMBER_ID:
        logger.error("WhatsApp Cloud API credentials not configured.")
        return None
        
    url = f"https://graph.facebook.com/v19.0/{WA_PHONE_NUMBER_ID}{endpoint}"
    headers = {
        "Authorization": f"Bearer {WA_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.request(method, url, headers=headers, json=payload, timeout=30)
        logger.info(f"WA Cloud API Response Status: {response.status_code}")
        if response.status_code >= 400:
            logger.error(f"WA Cloud API Error Body: {response.text}")
        return response
    except Exception as e:
        logger.error(f"WA Cloud API Connection error: {e}")
        return None

@router.get("/status")
def get_status(email: str = Depends(get_current_user_email), db: Session = Depends(get_db)):
    if WA_ACCESS_TOKEN and WA_PHONE_NUMBER_ID:
        return {
            "state": "CONNECTED", 
            "pushName": "WhatsApp Cloud API", 
            "number": WA_PHONE_NUMBER_ID, 
            "instanceName": "cloud_api"
        }
    return {"state": "DISCONNECTED", "qr": None, "instanceName": "cloud_api"}

@router.post("/send")
def send_whatsapp_message(
    contact_id: int = Body(...), 
    text: str = Body(None), 
    media_url: str = Body(None),
    media_type: str = Body("image"), # image, video, document
    contact_vcard: dict = Body(None), # { "fullName": "...", "wuid": "..." }
    email: str = Depends(get_current_user_email), 
    db: Session = Depends(get_db)
):
    user = db.query(models.User).filter(models.User.email == email).first()
    contact = db.query(models.Contact).filter(models.Contact.id == contact_id, models.Contact.tenant_id == user.tenant_id).first()
    if not contact or not contact.phone: raise HTTPException(404, "Contacto sin teléfono o no encontrado")

    clean_phone = "".join(filter(str.isdigit, contact.phone))
    
    payload = {
        "messaging_product": "whatsapp",
        "to": clean_phone,
    }
    
    if contact_vcard:
        payload["type"] = "contacts"
        payload["contacts"] = [{
            "name": { "formatted_name": contact_vcard.get("fullName", ""), "first_name": contact_vcard.get("fullName", "") },
            "phones": [ { "phone": contact_vcard.get("wuid", ""), "type": "WORK" } ]
        }]
    elif media_url:
        fb_type = "image" if media_type not in ["video", "document"] else media_type
        payload["type"] = fb_type
        payload[fb_type] = { "link": media_url }
        if text: payload[fb_type]["caption"] = text
    else:
        payload["type"] = "text"
        payload["text"] = { "body": text or "" }

    resp = call_wa_cloud("/messages", payload)
    
    if resp and resp.status_code in [200, 201]:
        if contact_vcard:
            log_desc = f"WhatsApp enviado (Contacto: {contact_vcard.get('fullName')})"
        elif media_url:
            log_desc = f"WhatsApp enviado (Media {media_type}: {media_url}): {text or ''}"
        else:
            log_desc = f"WhatsApp enviado: {text}"
            
        db.add(models.ActivityLog(
            user_id=user.id, 
            action="WHATSAPP_SENT", 
            entity_type="CONTACT", 
            entity_id=contact.id, 
            description=log_desc
        ))
        
        contact.last_contact_date = datetime.now(timezone.utc)
        db.add(contact)
        db.commit()
        return {"status": "ok"}
    
    error_msg = "Unknown Error"
    if resp is not None:
        try:
            error_msg = resp.json()
        except:
            error_msg = resp.text or f"Status {resp.status_code}"
            
    logger.error(f"WA Cloud API send failed: {error_msg}")
    raise HTTPException(500, f"Error enviando mensaje: {error_msg}")

@router.get("/contacts")
def get_whatsapp_contacts(email: str = Depends(get_current_user_email), db: Session = Depends(get_db)):
    # Cloud API cannot just fetch a contact list of everything in the phone
    return []

@router.post("/logout")
def logout_whatsapp(email: str = Depends(get_current_user_email), db: Session = Depends(get_db)):
    return {"status": "ok"}

@router.get("/messages/{contact_id}")
def get_contact_messages(contact_id: int, email: str = Depends(get_current_user_email), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    
    # First verify the contact belongs to the tenant
    contact = db.query(models.Contact).filter(models.Contact.id == contact_id, models.Contact.tenant_id == user.tenant_id).first()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact not found")
        
    logs = db.query(models.ActivityLog).filter(
        models.ActivityLog.entity_type == "CONTACT",
        models.ActivityLog.entity_id == contact_id,
        models.ActivityLog.action.in_(["WHATSAPP_SENT", "WHATSAPP_RECEIVED"])
        # We don't necessarily filter by user.id here, because a contact's messages could be from any agent in the same tenant
    ).order_by(models.ActivityLog.timestamp.asc()).all()

    def parse_message(log):
        desc = log.description
        media_url = None
        media_type = "image"
        text = desc
        
        if desc.startswith("WhatsApp enviado (Media"):
            import re
            match = re.search(r'WhatsApp enviado \(Media (.*?): (.*?)\): (.*)', desc, re.DOTALL)
            if match:
                media_type = match.group(1)
                media_url = match.group(2)
                text = match.group(3)
        elif desc.startswith("WhatsApp enviado: "):
            text = desc.replace("WhatsApp enviado: ", "")
        elif desc.startswith("Recibido: "):
            text = desc.replace("Recibido: ", "")
            
        return {
            "id": log.id,
            "fromMe": log.action == "WHATSAPP_SENT",
            "text": text,
            "media_url": media_url,
            "media_type": media_type,
            "timestamp": log.timestamp
        }

    return [parse_message(l) for l in logs]
