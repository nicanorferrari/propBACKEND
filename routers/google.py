
import os, requests, base64
from email.mime.text import MIMEText
from typing import Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_user_email
import models, schemas

router = APIRouter()

# Intentamos obtener las variables con y sin prefijo VITE_ para mayor flexibilidad
from dotenv import load_dotenv, find_dotenv
# Forzamos recarga explícita del .env local si existe
load_dotenv(find_dotenv(), override=True)

GOOGLE_CLIENT_ID = os.getenv("VITE_GOOGLE_CLIENT_ID") or os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("VITE_GOOGLE_REDIRECT_URI") or os.getenv("GOOGLE_REDIRECT_URI") or "https://propcrm-web.rjcuax.easypanel.host/"

google_id_log = GOOGLE_CLIENT_ID[:10] if GOOGLE_CLIENT_ID else "NULL"
print(f"GOOGLE CONF: ID={google_id_log}... Secret={'SET' if GOOGLE_CLIENT_SECRET else 'NULL'}")

def get_valid_google_token(user: models.User, db: Session):
    if not user.google_refresh_token: return None
    now = datetime.now()
    expiry = datetime.fromisoformat(user.google_token_expiry) if user.google_token_expiry else now
    if now < (expiry - timedelta(minutes=1)): return user.google_access_token
    
    res = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET, 
        "refresh_token": user.google_refresh_token, "grant_type": "refresh_token"
    })
    if not res.ok:
        print(f"Failed to refresh Google Token. Status: {res.status_code}, Body: {res.text}")
        # Si el token es inválido (revocado, expirado, etc.), desconectamos al usuario para que se entere.
        try:
            err_data = res.json()
            if err_data.get("error") == "invalid_grant":
                print("⚠️ Invalid Grant detected (Refresh Token expired/revoked). Disconnecting user...")
                user.google_access_token = None
                user.google_refresh_token = None
                user.google_token_expiry = None
                user.google_email = None
                db.commit()
        except Exception as e:
            print(f"Error handling invalid_grant: {e}")
            
        return None
    
    tokens = res.json()
    user.google_access_token = tokens["access_token"]
    user.google_token_expiry = str(datetime.now() + timedelta(seconds=tokens.get("expires_in", 3600)))
    db.commit()
    return user.google_access_token

@router.get("/status")
def get_integration_status(current_email: str = Depends(get_current_user_email), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == current_email).first()
    if not user: raise HTTPException(404, "User not found")
    
    # Auto-healing: If connected but no email saved, try to fetch it
    if user.google_access_token and not user.google_email:
        try:
             # Refresh token if needed
             token = get_valid_google_token(user, db)
             if token:
                 print("Intento de auto-recuperación de email de Google...")
                 user_info = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", headers={"Authorization": f"Bearer {token}"}).json()
                 if user_info.get("email"):
                     user.google_email = user_info.get("email")
                     db.commit()
        except Exception as e:
            print(f"Error fetching google email: {e}")

    return {
        "google": bool(user.google_access_token),
        "google_email": user.google_email, # Will be None if not connected or fetch failed
        "outlook": bool(user.outlook_access_token),
        "outlook_email": user.outlook_email
    }

@router.get("/calendar/events")
def get_google_calendar_events(current_email: str = Depends(get_current_user_email), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == current_email).first()
    token = get_valid_google_token(user, db)
    if not token:
        return {"items": []}
    
    # Llamada a la API de Google Calendar
    res = requests.get(
        "https://www.googleapis.com/calendar/v3/calendars/primary/events",
        headers={"Authorization": f"Bearer {token}"},
        params={"timeMin": datetime.now(timezone.utc).isoformat(), "maxResults": 50, "singleEvents": True, "orderBy": "startTime"}
    )
    if not res.ok:
        return {"items": []}
    return res.json()

@router.get("/agency/calendar/events")
def get_agency_calendar_events(current_email: str = Depends(get_current_user_email), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == current_email).first()
    if not user: raise HTTPException(401)
    
    agency = db.query(models.AgencyConfig).first()
    if not agency or not agency.google_refresh_token:
         return {"items": []}

    # Refresh Logic
    token = agency.google_access_token
    now = datetime.now()
    expiry = datetime.fromisoformat(agency.google_token_expiry) if agency.google_token_expiry else now
    
    if now >= (expiry - timedelta(minutes=1)):
        # Refresh
        res = requests.post("https://oauth2.googleapis.com/token", data={
            "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET, 
            "refresh_token": agency.google_refresh_token, "grant_type": "refresh_token"
        })
        if res.ok:
            tokens = res.json()
            agency.google_access_token = tokens["access_token"]
            agency.google_token_expiry = str(datetime.now() + timedelta(seconds=tokens.get("expires_in", 3600)))
            db.commit()
            token = agency.google_access_token
        else:
            print(f"Agency Token Refresh Failed: {res.text}")
            try:
                err_data = res.json()
                if err_data.get("error") == "invalid_grant":
                     print("⚠️ Invalid Agency Grant detected. Clearing tokens...")
                     agency.google_access_token = None
                     agency.google_refresh_token = None
                     agency.google_token_expiry = None
                     # No tocamos google_email para que el user sepa qué cuenta estaba vinculada
                     db.commit()
            except:
                pass
            return {"items": []}
            
    # Fetch Events
    try:
        res = requests.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {token}"},
            params={"timeMin": datetime.now(timezone.utc).isoformat(), "maxResults": 50, "singleEvents": True, "orderBy": "startTime"}
        )
        if not res.ok:
            return {"items": []}
        return res.json()
    except Exception as e:
        print(f"Error fetching agency events: {e}")
        return {"items": []}

@router.post("/disconnect/{provider}")
def disconnect_provider(provider: str, current_email: str = Depends(get_current_user_email), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == current_email).first()
    if not user: raise HTTPException(404)
    
    if provider == 'google':
        user.google_access_token = None
        user.google_refresh_token = None
        user.google_token_expiry = None
        user.google_email = None
    elif provider == 'outlook':
        user.outlook_access_token = None
        user.outlook_refresh_token = None
        user.outlook_token_expiry = None
        user.outlook_email = None
    
    db.commit()
    return {"status": "success"}

@router.post("/mail/send")
def send_email(data: schemas.EmailSendRequest, email: str = Depends(get_current_user_email), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    # Para envío real se requiere token válido
    get_valid_google_token(user, db)
    db.add(models.ActivityLog(user_id=user.id, action="EMAIL_SENT", entity_type="CONTACT", entity_id=data.contact_id, description=f"Email: {data.subject}"))
    db.commit()
    return {"status": "success"}

@router.get("/agency/status")
def get_agency_integration_status(db: Session = Depends(get_db), current_email: str = Depends(get_current_user_email)):
    # Verify user is admin/broker
    user = db.query(models.User).filter(models.User.email == current_email).first()
    if not user or user.role not in ['SUPER_ADMIN', 'BROKER_ADMIN']:
        raise HTTPException(403, "Insufficient permissions")

    agency = db.query(models.AgencyConfig).first()
    if not agency:
        return {"google": False, "outlook": False}
        
    return {
        "google": bool(agency.google_access_token),
        "google_email": agency.google_email,
        "outlook": bool(agency.outlook_access_token),
        "outlook_email": agency.outlook_email
    }

@router.post("/agency/disconnect/{provider}")
def disconnect_agency_provider(provider: str, db: Session = Depends(get_db), current_email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == current_email).first()
    if not user or user.role not in ['SUPER_ADMIN', 'BROKER_ADMIN']:
        raise HTTPException(403, "Insufficient permissions")
        
    agency = db.query(models.AgencyConfig).first()
    if not agency: raise HTTPException(404, "Agency config not found")
    
    if provider == 'google':
        agency.google_access_token = None
        agency.google_refresh_token = None
        agency.google_token_expiry = None
        agency.google_email = None
    elif provider == 'outlook':
        agency.outlook_access_token = None
        agency.outlook_refresh_token = None
        agency.outlook_token_expiry = None
        agency.outlook_email = None
    
    db.commit()
    return {"status": "success"}

@router.post("/callback/google")
async def callback(request: Request, db: Session = Depends(get_db), current_email: str = Depends(get_current_user_email)):
    body = await request.json()
    code = body.get("code")
    state = body.get("state", "")
    
    # Permitimos que el Frontend nos diga qué redirect_uri usó (localhost o prod)
    # para que coincida en la validación del token.
    frontend_redirect_uri = body.get("redirect_uri") or GOOGLE_REDIRECT_URI
    
    res = requests.post("https://oauth2.googleapis.com/token", data={
        "code": code, 
        "client_id": GOOGLE_CLIENT_ID, 
        "client_secret": GOOGLE_CLIENT_SECRET, 
        "redirect_uri": frontend_redirect_uri, 
        "grant_type": "authorization_code"
    })
    
    if not res.ok:
        raise HTTPException(status_code=400, detail=f"Google OAuth Error: {res.text}")
        
    tokens = res.json()
    
    # Check if this is for Agency Integration
    if state == 'google_agency':
        user = db.query(models.User).filter(models.User.email == current_email).first()
        if not user or user.role not in ['SUPER_ADMIN', 'BROKER_ADMIN']:
             raise HTTPException(403, "Insufficient permissions for Agency Integration")
             
        agency = db.query(models.AgencyConfig).first()
        if not agency:
            agency = models.AgencyConfig()
            db.add(agency)
        
        agency.google_access_token = tokens.get("access_token")
        if tokens.get("refresh_token"): agency.google_refresh_token = tokens.get("refresh_token")
        agency.google_token_expiry = str(datetime.now() + timedelta(seconds=tokens.get("expires_in", 3600)))
        
        # Get Email to confirm identity
        try:
            user_info = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", headers={"Authorization": f"Bearer {agency.google_access_token}"}).json()
            agency.google_email = user_info.get("email")
        except:
            pass
            
        db.commit()
    else:
        # User Integration
        user = db.query(models.User).filter(models.User.email == current_email).first()
        if user:
            user.google_access_token = tokens.get("access_token")
            if tokens.get("refresh_token"): user.google_refresh_token = tokens.get("refresh_token")
            user.google_token_expiry = str(datetime.now() + timedelta(seconds=tokens.get("expires_in", 3600)))
            
            # Get Email
            try:
                user_info = requests.get("https://www.googleapis.com/oauth2/v2/userinfo", headers={"Authorization": f"Bearer {user.google_access_token}"}).json()
                user.google_email = user_info.get("email")
            except:
                pass
                
            db.commit()
            
    return {"status": "success"}

def get_valid_agency_token(agency: models.AgencyConfig, db: Session):
    if not agency.google_refresh_token: return None
    now = datetime.now()
    expiry = datetime.fromisoformat(agency.google_token_expiry) if agency.google_token_expiry else now
    
    if now < (expiry - timedelta(minutes=1)): return agency.google_access_token
    
    # Refresh
    res = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": GOOGLE_CLIENT_ID, "client_secret": GOOGLE_CLIENT_SECRET, 
        "refresh_token": agency.google_refresh_token, "grant_type": "refresh_token"
    })
    
    if res.ok:
        tokens = res.json()
        agency.google_access_token = tokens["access_token"]
        agency.google_token_expiry = str(datetime.now() + timedelta(seconds=tokens.get("expires_in", 3600)))
        db.commit()
        return agency.google_access_token
    else:
        print(f"Agency Refresh Failed: {res.text}")
        try:
            err_data = res.json()
            if err_data.get("error") == "invalid_grant":
                print("⚠️ Invalid Agency Grant detected. Clearing tokens...")
                agency.google_access_token = None
                agency.google_refresh_token = None
                agency.google_token_expiry = None
                db.commit()
        except:
            pass
        return None

def create_google_event(token: str, event_data: dict, calendar_id: str = "primary"):
    res = requests.post(
        f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events",
        headers={"Authorization": f"Bearer {token}"},
        json=event_data
    )
    return res
