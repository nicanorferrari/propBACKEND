import requests
import json
import time
import sys
import os

# Ensure we can import backend modules
sys.path.append(os.getcwd())

from database import SessionLocal
import models

# 1. Get Valid User
session = SessionLocal()
user = session.query(models.User).first()
if not user:
    print("ERROR: No users found in database!")
    sys.exit(1)

USER_ID = user.id
INSTANCE = f"urbano_crm_user_{USER_ID}"
# Assuming default setup or specific prefix from ENV?
# whatsapp.py uses WHATSAPP_INSTANCE_PREFIX which defaults to "user_"
# So "user_{id}_crm" is the format in get_evo_instance?
# Let's check whatsapp.py line 28: return f"{prefix}{user_id}_crm"
# Wait! whatsapp.py line 28: `return f"{prefix}{user_id}_crm"`
# If prefix is "user_", then "user_1_crm".
# But checking regex in webhook: `user_match = re.search(r'user_(\d+)', instance_name)`
# This regex matches "user_1". It doesn't enforce suffix.
# So "user_1" works. "urbano_crm_user_1" matches "user_1".
# BUT if logic expects "user_1" specifically...
# Let's stick to what whatsapp.py line 141 expects: `re.search(r'user_(\d+)', instance_name)`.
# My proposed instance "urbano_crm_user_{USER_ID}" will match "user_{IDs}".
# Wait. "urbano_crm_user_1" -> matches "user_1". Group 1 is "1".
# Correct.

print(f"[SETUP] Using Instance Name: {INSTANCE} (User ID: {USER_ID})")
session.close()

# Config
BASE_URL = "http://localhost:8000/api/whatsapp/webhook"
PHONE = "5493411112222"
JID = f"{PHONE}@s.whatsapp.net"

def send_msg(text):
    payload = {
        "event": "messages.upsert",
        "instance": INSTANCE,
        "data": {
            "key": {
                "remoteJid": JID,
                "fromMe": False,
                "id": f"MSG_TEST_{time.time()}"
            },
            "pushName": "Tester Bot",
            "message": {
                "conversation": text
            }
        }
    }
    print(f"\n[SIMULATION] Sending User Message: '{text}'")
    try:
        r = requests.post(BASE_URL, json=payload)
        print(f"[API] Status: {r.status_code}")
        if r.status_code != 200:
             print(f"[API] Response: {r.text}")
    except Exception as e:
        print(f"[API] Request Error: {e}")

def check_db():
    db = SessionLocal()
    try:
        print("--- Checking Database ---")
        # 1. Check Contact
        contact = db.query(models.Contact).filter(models.Contact.phone == PHONE).first()
        if contact:
            print(f"[DB] Contact FOUND: ID={contact.id}, Name={contact.name}, Source={contact.source}")
        else:
            print("[DB] Contact NOT found.")

        # 2. Check Chat History (Bot Response)
        history = db.query(models.ChatHistory).filter(models.ChatHistory.sender_id == PHONE).order_by(models.ChatHistory.created_at.desc()).all()
        if history:
            print(f"[DB] Chat History ({len(history)} msgs):")
            for h in history[:3]: # Show last 3
                print(f"  - [{h.role}]: {h.parts}")
        
        # 3. Check Calendar Events
        if contact:
            events = db.query(models.CalendarEvent).filter(models.CalendarEvent.contact_id == contact.id).all()
            if events:
                print(f"[DB] Calendar Events Found ({len(events)}):")
                for e in events:
                    print(f"  - Event: {e.title}, Start: {e.start_time}, Source: {e.source}")
            else:
                print("[DB] No Calendar Events found.")
    finally:
        db.close()

# --- RUN ---
print("--- STEP 1: Initialization ---")
send_msg("Hola, busco propiedad en Rosario")
time.sleep(5) 
check_db()

print("\n--- STEP 2: Request Visit ---")
send_msg("Me gustaría visitar la propiedad casa en funes mañana")
time.sleep(5)
check_db()
