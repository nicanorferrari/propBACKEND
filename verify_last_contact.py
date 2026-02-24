import urllib3
urllib3.disable_warnings()
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
import models
from auth import get_current_user_email
import datetime
import time

import sys
fastapi_app = app.other_asgi_app if hasattr(app, "other_asgi_app") else app
client = TestClient(fastapi_app)
test_email = "testuser@urbanocrm.com"
fastapi_app.dependency_overrides[get_current_user_email] = lambda: test_email


db = SessionLocal()
user = db.query(models.User).filter_by(email=test_email).first()

if not user:
    print("Error: testuser@urbanocrm.com no existe. Ejecuta un script de llenado antes.")
    exit(1)

def run_test(name, func):
    print(f"\n--- Probando: {name} ---")
    try:
        func()
        print("  \033[92m[EXITO]\033[0m Funciona correctamente.")
    except Exception as e:
        print(f"  \033[91m[ERROR]\033[0m Falló la prueba: {e}")

def create_temp_contact():
    import uuid
    suffix = uuid.uuid4().hex[:6]
    res = client.post("/api/contacts", json={

        "name": f"Contacto de Prueba {suffix}",
        "phone": f"555000{suffix[-4:]}",
        "email": f"test{suffix}@test.com",
        "source": "MANUAL",
        "status": "COLD",
        "type": "CLIENT"
    })
    if res.status_code != 200:
        raise Exception(f"Failed creating contact: {res.text}")
    return res.json()["id"]

def get_last_contact_date(contact_id):
    db.expire_all()
    c = db.query(models.Contact).filter(models.Contact.id == contact_id).first()
    return c.last_contact_date

# 1. POST /contacts/{id}/interactions
def test_manual_interaction():
    cid = create_temp_contact()
    before = get_last_contact_date(cid)
    print(f"  Antes: {before}")
    
    # Pausamos 1 seg para asegurar diferencia de ticks en BD
    time.sleep(1)
    
    res = client.post(f"/api/contacts/{cid}/interactions", json={
        "type": "CALL",
        "notes": "Llamada de test.",
        "date": datetime.datetime.now(datetime.timezone.utc).isoformat()
    })
    if res.status_code != 200:
        raise Exception(f"Failed to add interaction: {res.text}")
        
    after = get_last_contact_date(cid)
    print(f"  Después: {after}")
    
    if before == after or not after:
        raise Exception(f"last_contact_date no se actualizó (sigue siendo {before})")

# 2. POST /opportunities
def test_opportunity_creation():
    cid = create_temp_contact()
    before = get_last_contact_date(cid)
    print(f"  Antes: {before}")
    
    time.sleep(1)
    res = client.post("/api/opportunities/deals", json={
        "contact_id": cid,
        "title": "Op Test",
        "pipeline_stage_id": 1,
        "value": 1000,
        "source": "MANUAL"
    })
    if res.status_code != 200:
        raise Exception(f"Failed to add opportunity: {res.text}")
        
    after = get_last_contact_date(cid)
    print(f"  Después: {after}")
    if before == after or not after:
        raise Exception(f"last_contact_date no se actualizó tras crear Op")

# 3. PUT /opportunities/{id} status change
def test_opportunity_status_change():
    cid = create_temp_contact()
    res = client.post("/api/opportunities/deals", json={
        "contact_id": cid,
        "title": "Op Test Update",
        "pipeline_stage_id": 1,
        "value": 1000,
        "source": "MANUAL"
    })
    op_id = res.json()["id"]
    
    time.sleep(1)
    before = get_last_contact_date(cid)
    print(f"  Antes update Op: {before}")
    
    time.sleep(1)
    res = client.put(f"/api/opportunities/deals/{op_id}", json={
        "value": 2000
    })
    
    after = get_last_contact_date(cid)
    print(f"  Después update Op: {after}")
    if before == after:
        raise Exception(f"last_contact_date no se actualizó tras cambiar fase de Op")

# 4. POST /calendars
def test_calendar_creation():
    cid = create_temp_contact()
    before = get_last_contact_date(cid)
    print(f"  Antes: {before}")
    
    time.sleep(1)
    res = client.post("/api/calendar/events", json={
        "contact_id": cid,
        "title": "Visita Test",
        "start_time": (datetime.datetime.now() + datetime.timedelta(days=1)).isoformat(),
        "end_time": (datetime.datetime.now() + datetime.timedelta(days=1, hours=1)).isoformat(),
        "type": "VISIT",
        "status": "SCHEDULED"
    })
    if res.status_code != 200:
        raise Exception(f"Failed to add calendar: {res.text}")
        
    after = get_last_contact_date(cid)
    print(f"  Después: {after}")
    if before == after or not after:
        raise Exception(f"last_contact_date no se actualizó tras crear Evento")

# 5. POST /whatsapp/webhook 
def test_whatsapp_webhook():
    cid = create_temp_contact()
    contact = db.query(models.Contact).filter(models.Contact.id == cid).first()
    clean_phone = "".join(filter(str.isdigit, contact.phone))
    
    before = get_last_contact_date(cid)
    print(f"  Antes webhook WA: {before}")
    time.sleep(1)
    
    # Simulate an incoming message webhook
    payload = {
        "event": "messages.upsert",
        "instance": f"user_{user.id}_crm",
        "data": {
            "message": {"conversation": "Hola probando webhook"},
            "key": {
                "fromMe": False,
                "remoteJid": f"{clean_phone}@s.whatsapp.net"
            },
            "pushName": "Contacto WA Demo"
        }
    }
    res = client.post("/api/whatsapp/webhook", json=payload)
    if res.status_code != 200:
        raise Exception(f"Failed to hit webhook: {res.text}")
        
    after = get_last_contact_date(cid)
    print(f"  Después webhook WA: {after}")
    if before == after or not after:
        raise Exception(f"last_contact_date no se actualizó con mensaje WA")

# Run all
if __name__ == "__main__":
    print(f"Corriendo en BBDD para {test_email}")
    run_test("1. Crear Interaccion Manual", test_manual_interaction)
    run_test("2. Crear Oportunidad", test_opportunity_creation)
    run_test("3. Mover Oportunidad de Etapa", test_opportunity_status_change)
    run_test("4. Agendar Visita (Calendario)", test_calendar_creation)
    run_test("5. Recibir mensaje WhatsApp", test_whatsapp_webhook)
    
    # Cleanup contacts added in test 
    # db.query(models.Contact).filter(models.Contact.name.like("Contacto de Prueba %")).delete(synchronize_session=False)
    # db.commit()
