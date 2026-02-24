
import os
import requests
import logging
import re
from fastapi import APIRouter, Depends, HTTPException, Body, Request, BackgroundTasks
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_user_email
from datetime import datetime, timedelta, timezone
import time
import models
import json

def json_dumps(obj):
    return json.dumps(obj, ensure_ascii=True)

router = APIRouter()
logger = logging.getLogger("urbanocrm.whatsapp")

EVO_URL = os.getenv("EVO_URL", "").strip().rstrip("/")
EVO_KEY = os.getenv("EVO_KEY", "").strip()
INSTANCE_PREFIX = os.getenv("WHATSAPP_INSTANCE_PREFIX", "user_").strip()

# Se toma la URL del webhook desde variables de entorno para mayor flexibilidad
WEBHOOK_URL = os.getenv(
    "WHATSAPP_WEBHOOK_URL", 
    "https://XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXsdXXXXXXXXXXXXXXXX00XXXXXXXXXXXXXXXXXXXXXXx.easypanel.host/api/whatsapp/webhook"
)

def get_evo_instance(user_id: int):
    prefix = INSTANCE_PREFIX if INSTANCE_PREFIX.endswith(('_', '-')) else f"{INSTANCE_PREFIX}_"
    return f"{prefix}{user_id}_crm"

def call_evo(method: str, endpoint: str, data: dict = None):
    if not EVO_URL:
        logger.error("Evolution API Error: EVO_URL is not set")
        return None
    if not EVO_KEY:
        logger.error("Evolution API Error: EVO_KEY is not set")
        return None
        
    headers = {"apikey": EVO_KEY, "Content-Type": "application/json"}
    url = f"{EVO_URL}{endpoint}"
    
    logger.info(f"Evolution API Request: {method} {url}")
    try:
        response = requests.request(method, url, headers=headers, json=data, timeout=30)
        logger.info(f"Evolution API Response Status: {response.status_code}")
        # Retornamos la respuesta independientemente del status code para que el llamador lo maneje
        if response.status_code >= 400:
            logger.error(f"Evolution API Error Body: {response.text}")
        return response
    except requests.exceptions.RequestException as e:
        logger.error(f"Evolution API Connection error calling {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error calling Evolution API: {e}")
        return None

def setup_webhook(instance: str):
    """Configura el webhook para una instancia específica (Fallback/Update)"""
    return call_evo("POST", f"/webhook/set/{instance}", {
        "enabled": True,
        "url": WEBHOOK_URL,
        "byEvents": False,
        "base64": False,
        "events": [
            "MESSAGES_UPSERT", 
            "CONNECTION_UPDATE",
            "MESSAGES_UPDATE",
            "SEND_MESSAGE",
            "CONTACTS_UPSERT", 
            "CONTACTS_UPDATE"
        ]
    })

@router.get("/status")
def get_status(email: str = Depends(get_current_user_email), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    instance = get_evo_instance(user.id)
    
    # Verificar si la instancia existe
    resp = call_evo("GET", f"/instance/connectionState/{instance}")
    
    if resp is None or resp.status_code == 404:
        # CREACIÓN CON WEBHOOK INTEGRADO (Recomendado para v2)
        create_payload = {
            "instanceName": instance, 
            "token": f"tk_{user.id}", 
            "qrcode": True, 
            "integration": "WHATSAPP-BAILEYS",
            "webhook": {
                "enabled": True,
                "url": WEBHOOK_URL,
                "byEvents": False,
                "base64": False,
                "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE"]
            }
        }
        create_resp = call_evo("POST", "/instance/create", create_payload)
        
        if create_resp and create_resp.status_code in [201, 200]:
            data = create_resp.json()
            # Doble check: asegurar webhook por si el API ignoró el payload inicial
            setup_webhook(instance)
            return {
                "state": "DISCONNECTED", 
                "qr": data.get("qrcode", {}).get("base64") or data.get("base64"), 
                "instanceName": instance
            }
        raise HTTPException(500, f"Error creando instancia: {create_resp.text if create_resp else 'Sin respuesta'}")

    state_data = resp.json()
    current_state = state_data.get("instance", {}).get("state") or state_data.get("state")
    
    # Si la cuenta está conectada, reforzamos que el Webhook esté activo
    if current_state == "open":
        setup_webhook(instance)
        return {
            "state": "CONNECTED", 
            "pushName": state_data.get("instance", {}).get("owner") or "Usuario", 
            "number": state_data.get("instance", {}).get("number") or "", 
            "instanceName": instance
        }
    
    # Si está desconectado, intentamos reconectar para obtener el QR
    connect_resp = call_evo("GET", f"/instance/connect/{instance}")
    qr = connect_resp.json().get("base64") if connect_resp else None
    return {"state": "DISCONNECTED", "qr": qr, "instanceName": instance}

@router.post("/webhook")
async def evolution_webhook(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Recibe mensajes de Evolution API y los inyecta en el CRM."""
    try:
        payload = await request.json()
        event_type = payload.get("event")
        instance_name = payload.get("instance")
        
        if event_type == "connection.update":
            logger.debug(f"--- WEBHOOK RECEIVED: {event_type} from {instance_name} ---")
            return {"status": "ignored_connection_update"}
            
        if event_type in ["contacts.upsert", "contacts.update"]:
             logger.info(f"--- WEBHOOK RECEIVED: {event_type} from {instance_name} ---")
             # Handle Contact Updates (e.g. name sync)
             contacts_data = payload.get("data", [])
             if not isinstance(contacts_data, list): 
                  contacts_data = [contacts_data] # Normalize to list
             
             user_match = re.search(r'user_(\d+)', instance_name)
             if not user_match: return {"status": "unknown_instance_format", "received": instance_name}
             owner_id = int(user_match.group(1))

             updated_count = 0
             for c in contacts_data:
                 raw_id = c.get("id") or c.get("remoteJid") or ""
                 phone = raw_id.split("@")[0]
                 # 'name' is the phonebook name, 'pushName' is the public profile name
                 new_name = c.get("name")
                 
                 if phone and new_name:
                     # Find existing contact to update
                     search_suffix = phone[-8:] if len(phone) >= 8 else phone
                     existing = db.query(models.Contact).filter(models.Contact.phone.ilike(f"%{search_suffix}")).first()
                     if existing:
                         # Update logical name
                         # We store authentic WA name in 'alias' or directly in 'name' if source is WA?
                         # Let's map it to 'contact_name' (usually for specific contact person) or 'alias' to override.
                         # Best approach: Update 'alias' so it takes precedence in ChatView logic.
                         existing.alias = new_name
                         existing.source = "WHATSAPP" # Ensure source is correct
                         updated_count += 1
             
             if updated_count > 0:
                 db.commit()
                  
             return {"status": "contacts_processed", "count": updated_count}

        if event_type != "messages.upsert":
            logger.debug(f"Webhook event ignored: {event_type}")
            return {"status": "ignored_event"}

        logger.info(f"--- WEBHOOK RECEIVED: {event_type} from {instance_name} ---")
        data = payload.get("data", {})
        message = data.get("message", {})
        key = data.get("key", {})
        
        # ... rest of message logic ...
        if not key: return {"status": "no_key_data"} # Safety check
        
        is_from_me = key.get("fromMe", False)
        remote_jid = key.get("remoteJid", "")
        phone_number = remote_jid.split("@")[0] # This is the OTHER party (contact)
        
        message_text = (
            message.get("conversation") or 
            message.get("extendedTextMessage", {}).get("text") or 
            message.get("imageMessage", {}).get("caption") or 
            "[Multimedia/Emoji]"
        )
        
        push_name = data.get("pushName") or "Contacto WhatsApp"

        user_match = re.search(r'user_(\d+)', instance_name)
        if not user_match:
            # Fallback for alternative naming?
            return {"status": "unknown_instance_format", "received": instance_name}
        
        owner_id = int(user_match.group(1))

        # Buscar o crear contacto usando MATCHING ROBUSTO (Ultimos 8 digitos)
        # Esto soluciona el problema de "+54 9 341..." vs "549341..."
        search_suffix = phone_number[-8:] if len(phone_number) >= 8 else phone_number
        
        from sqlalchemy import func
        contact = db.query(models.Contact).filter(
            func.regexp_replace(models.Contact.phone, '[^0-9]', '', 'g').ilike(f"%{search_suffix}")
        ).first()

        if not contact:
            # Si no existe, creamos uno nuevo con el numero limpio
            contact = models.Contact(
                name=push_name if not is_from_me else phone_number,
                phone=phone_number,
                source="WHATSAPP",
                status="HOT",
                type="CLIENT",
                notes=f"Lead auto-generado desde WhatsApp ({'Saliente' if is_from_me else 'Entrante'}).",
                created_by_id=owner_id
            )
            db.add(contact)
            db.flush()
        
        # Update Last Contact Date (ALWAYS)
        contact.last_contact_date = datetime.now(timezone.utc)
        db.add(contact)

        # Log Message
        action = "WHATSAPP_SENT" if is_from_me else "WHATSAPP_RECEIVED"
        desc_prefix = "WhatsApp enviado: " if is_from_me else "Recibido: "
        
        # Dedup check for SENT messages (to avoid double log with API send)
        should_log = True
        if is_from_me:
            recent_log = db.query(models.ActivityLog).filter(
                models.ActivityLog.entity_id == contact.id,
                models.ActivityLog.action == "WHATSAPP_SENT",
                models.ActivityLog.timestamp >= datetime.now(timezone.utc) - timedelta(seconds=10),
                models.ActivityLog.description == f"{desc_prefix}{message_text}"
            ).first()
            if recent_log:
                should_log = False
        
        if should_log:
            db.add(models.ActivityLog(
                user_id=owner_id,
                action=action,
                entity_type="CONTACT",
                entity_id=contact.id,
                description=f"{desc_prefix}{message_text}"
            ))
        
        db.commit()

        # Bot Logic Trigger (Solo si es mensaje entrante de un contacto y no del dueño)
        if not is_from_me and "@s.whatsapp.net" in remote_jid:
             # Verificar si el bot está activo para esta instancia
             bot = db.query(models.Bot).filter(models.Bot.instance_name == instance_name, models.Bot.is_active == True).first()
             if bot:
                  logger.info(f"Triggering Bot Engine for {remote_jid} on {instance_name}")
                  background_tasks.add_task(handle_bot_response, instance_name, remote_jid, message_text)

        return {"status": "success"}
        
    except Exception as e:
        logger.error(f"WEBHOOK ERROR: {str(e)}")
        return {"status": "error", "detail": str(e)}

async def handle_bot_response(instance_name: str, remote_jid: str, text: str):
    """Procesa la respuesta de la IA en segundo plano."""
    try:
        from bot_engine import BotEngine
        engine = BotEngine(instance_name)
        phone = remote_jid.split("@")[0]
        
        # 0. Set 'Typing...' presence
        presence_payload = { "number": phone, "presence": "composing", "delay": 15000 }
        call_evo("POST", f"/chat/sendPresence/{instance_name}", presence_payload)
        
        # 1. Obtener respuesta de Gemini
        bot_response = engine.process_message(phone, text)
        
        if bot_response:
            # 2. Enviar respuesta vía Evolution API
            # Se usa el delay para simular escritura humana
            payload = { 
                "number": phone, 
                "text": bot_response
                # "delay": 3000, # Comentado para evitar errores 400
                # "linkPreview": True 
            }
            # Use json.dumps with ensure_ascii=True to avoid UnicodeEncodeError in Windows Console
            logger.info(f"Bot Engine: Sending payload to {phone}: {json_dumps(payload)}")
            msg_resp = call_evo("POST", f"/message/sendText/{instance_name}", payload)
            
            # Retry logic for flaky connections
            if msg_resp is not None and msg_resp.status_code >= 400:
                error_body = msg_resp.text
                logger.warning(f"Evolution API Error ({msg_resp.status_code}) for {instance_name}: {error_body}")
                
                if "Connection Closed" in error_body or "Bad Request" in error_body:
                    logger.info(f"Attempting to refresh connection for {instance_name}...")
                    conn_resp = call_evo("GET", f"/instance/connect/{instance_name}")
                    
                    # Check if we got a QR code back (means fully disconnected)
                    is_disconnected = False
                    if conn_resp and conn_resp.status_code == 200:
                        data = conn_resp.json()
                        if "base64" in data or "qrcode" in data:
                            is_disconnected = True
                    
                    if is_disconnected:
                        logger.error(f"Instance {instance_name} is DISCONNECTED (QR required). Updating DB status.")
                        from database import SessionLocal
                        db = SessionLocal()
                        try:
                            bot = db.query(models.Bot).filter(models.Bot.instance_name == instance_name).first()
                            if bot:
                                bot.status = "disconnected"
                                db.commit()
                        finally:
                            db.close()
                        # Do not retry send, it will fail
                    else:
                        logger.info("Waiting 3s for reconnection...")
                        time.sleep(3)
                        
                        logger.info(f"Retrying send to {phone}...")
                        msg_resp = call_evo("POST", f"/message/sendText/{instance_name}", payload)

            if msg_resp is not None and msg_resp.status_code >= 400:
                logger.error(f"Failed to send bot response to {phone} after retry: {msg_resp.text}")
            
    except Exception as e:
        logger.error(f"BOT ENGINE ERROR: {e}")

@router.get("/messages/{contact_id}")
def get_contact_messages(contact_id: int, email: str = Depends(get_current_user_email), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    logs = db.query(models.ActivityLog).filter(
        models.ActivityLog.entity_type == "CONTACT",
        models.ActivityLog.entity_id == contact_id,
        models.ActivityLog.action.in_(["WHATSAPP_SENT", "WHATSAPP_RECEIVED"])
    ).order_by(models.ActivityLog.timestamp.asc()).all()

    def parse_message(log):
        desc = log.description
        media_url = None
        media_type = "image"
        text = desc
        
        if desc.startswith("WhatsApp enviado (Media"):
            # Extract URL, Type and remaining text
            import re
            # Match formats: "WhatsApp enviado (Media image: URL): text" or "WhatsApp enviado (Media document: URL): text"
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
    contact = db.query(models.Contact).filter(models.Contact.id == contact_id).first()
    if not contact or not contact.phone: raise HTTPException(404, "Contacto sin teléfono")

    instance = get_evo_instance(user.id)
    clean_phone = "".join(filter(str.isdigit, contact.phone))
    
    if contact_vcard:
        payload = {
            "number": clean_phone,
            "contact": [contact_vcard]
        }
        endpoint = f"/message/sendContact/{instance}"
    elif media_url:
        payload = {
            "number": clean_phone,
            "media": media_url,
            "mediatype": media_type,
            "caption": text or "",
            "delay": 1200
        }
        endpoint = f"/message/sendMedia/{instance}"
    else:
        payload = { "number": clean_phone, "text": text, "delay": 1200, "linkPreview": True }
        endpoint = f"/message/sendText/{instance}"

    resp = call_evo("POST", endpoint, payload)
    
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
        
        # Update last_contact_date
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
            
    logger.error(f"Evolution API send failed ({endpoint}): {error_msg}")
    raise HTTPException(500, f"Error enviando mensaje: {error_msg}")

@router.get("/contacts")
def get_whatsapp_contacts(email: str = Depends(get_current_user_email), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise HTTPException(401, "Usuario no encontrado")
    
    instance = get_evo_instance(user.id)
    
    # 1. Intentar obtener contactos de la base de datos de Evolution
    resp = call_evo("POST", f"/chat/findContacts/{instance}", {"where": {}})
    
    if resp and resp.status_code == 200:
        contacts = resp.json()
        # Normalizar respuesta si es necesario
        return contacts
        
    # 2. Fallback: Intentar /contact/find (algunas versiones)
    resp2 = call_evo("POST", f"/contact/find/{instance}", {})
    if resp2 and resp2.status_code == 200:
        return resp2.json()
        
    logger.warning(f"No se pudieron obtener contactos WA para {instance}")
    return []

@router.post("/logout")
def logout_whatsapp(email: str = Depends(get_current_user_email), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    instance = get_evo_instance(user.id)
    call_evo("DELETE", f"/instance/logout/{instance}")
    call_evo("DELETE", f"/instance/delete/{instance}")
    return {"status": "ok"}
