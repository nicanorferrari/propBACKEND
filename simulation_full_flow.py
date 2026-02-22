import sys
import os
sys.path.append(os.getcwd())
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv(), override=True) # Ensure vars loaded

from bot_engine import BotEngine
from database import SessionLocal
import models
import datetime

# Setup
db = SessionLocal()
user = db.query(models.User).first()
if not user:
    print("FATAL: No user found.")
    exit(1)

# Ensure Bot Instance
instance = f"urbano_crm_user_{user.id}"
bot = db.query(models.Bot).filter(models.Bot.instance_name == instance).first()
if not bot:
    print(f"Creating dummy bot for {instance}")
    bot = models.Bot(instance_name=instance, user_id=user.id, platform="whatsapp", is_active=True)
    db.add(bot)
    db.commit()

# Tester Info
PHONE = "5493411112222"
# Ensure Contact Exists
contact = db.query(models.Contact).filter(models.Contact.phone == PHONE).first()
if not contact:
    print("Creating Contact: Tester Bot")
    contact = models.Contact(name="Tester Bot", phone=PHONE, tenant_id=user.tenant_id)
    db.add(contact)
    db.commit()

print(f"--- SIMULATION START: {datetime.datetime.now()} ---")
print(f"Bot Instance: {instance}")
print(f"User Phone: {PHONE}")

# Turn 1
msg1 = "Hola, busco departamento de 2 dormitorios en San Lorenzo 1000."
print(f"\n[USER]: {msg1}")
engine = BotEngine(instance)
response1 = engine.process_message(PHONE, msg1)
print(f"[BOT]: {response1}")

# Turn 2
msg2 = "Genial. Quiero agendar una visita para hoy a las 16hs."
print(f"\n[USER]: {msg2}")
engine = BotEngine(instance)
response2 = engine.process_message(PHONE, msg2)
print(f"[BOT]: {response2}")

# Verify DB
print("\n--- VERIFICATION ---")
today_str = datetime.date.today().strftime("%Y-%m-%d")
event = db.query(models.CalendarEvent).filter(
    models.CalendarEvent.contact_id == contact.id,
    models.CalendarEvent.start_time >= f"{today_str} 00:00:00"
).order_by(models.CalendarEvent.id.desc()).first()

if event:
    print(f"SUCCESS: Event Created!")
    print(f"  ID: {event.id}")
    print(f"  Title: {event.title}")
    print(f"  Start: {event.start_time}")
    print(f"  Agent ID: {event.agent_id}")
    print(f"  Google Event ID: {event.google_event_id}")
else:
    print("FAILURE: No event found for today.")

db.close()
