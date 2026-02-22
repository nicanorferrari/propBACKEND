import sys
import os
sys.path.append(os.getcwd())
from bot_engine import BotEngine
from database import SessionLocal
import models
import logging

# Check User
db = SessionLocal()
user = db.query(models.User).first()
if not user:
    print("No user.")
    exit()

instance = f"urbano_crm_user_{user.id}"
# Ensure Bot exists for this user in DB, or BotEngine init fails (it tries to fetch Bot)
# BotEngine line 83: self.bot = ... filter(instance_name == ...)
# Check if bot exists
bot = db.query(models.Bot).filter(models.Bot.instance_name == instance).first()
if not bot:
    # Create dummy bot
    print("Creating dummy bot for test...")
    bot = models.Bot(instance_name=instance, user_id=user.id, platform="whatsapp", is_active=True)
    db.add(bot)
    db.commit()

phone = "5493411112222" # Tester Bot

print(f"Testing with Instance: {instance}, Phone: {phone}")

try:
    engine = BotEngine(instance)
    engine.current_phone = phone

    # Get Property
    prop = db.query(models.Property).first()
    if not prop:
        print("No properties.")
        exit()

    print(f"Scheduling for Property {prop.id}...")
    # Call tool directly
    result = engine.schedule_visit(prop.id, "2025-12-31", "10:00")
    print(f"Tool Result: {result}")

    # Verify DB
    event = db.query(models.CalendarEvent).filter(models.CalendarEvent.start_time == "2025-12-31 10:00:00").first()
    if event:
        print(f"SUCCESS: Event Created! ID: {event.id}, Msg: {event.description}, AgentID: {event.agent_id}")
    else:
        print("FAILURE: Event not found in DB.")

except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
