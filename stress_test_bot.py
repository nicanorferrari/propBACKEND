import os
import json
import time
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Reemplazar postgres:// por postgresql:// antes de importar modelos
load_dotenv()
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
os.environ["DATABASE_URL"] = db_url 

import models
from bot_engine import BotEngine

# Configuración de DB
engine = create_engine(db_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# FORZAR AÑO 2026 en la simulación si es posible, o simplemente verificar la salida del bot.
# El bot debería saber que hoy es 11 de Feb 2026 si el system prompt o el contexto se lo dice.

def simulate_flow(phone, contact_name, conversation_steps, instance_name="urbano_crm_user_11"):
    db = SessionLocal()
    try:
        print(f"\n--- INICIANDO SIMULACIÓN: {contact_name} ({phone}) ---")
        
        # Limpieza Previa
        test_contact = db.query(models.Contact).filter(models.Contact.phone == phone).first()
        if test_contact:
            db.query(models.CalendarEvent).filter(models.CalendarEvent.contact_id == test_contact.id).delete()
            db.query(models.Deal).filter(models.Deal.contact_id == test_contact.id).delete()
            db.query(models.ContactInteraction).filter(models.ContactInteraction.contact_id == test_contact.id).delete()
            db.query(models.ChatHistory).filter(models.ChatHistory.sender_id == phone).delete()
            db.delete(test_contact)
            db.commit()

        # Asegurar contacto
        contact = models.Contact(name=contact_name, phone=phone, tenant_id=1, source="WHATSAPP")
        db.add(contact)
        db.commit()

        bot = BotEngine(instance_name)
        
        for step_msg in conversation_steps:
            print(f"👤 {contact_name}: {step_msg}")
            resp = bot.process_message(phone, step_msg)
            print(f"🤖 AGUSTINA: {resp}")
            time.sleep(1)

        # Verificación
        db.expire_all()
        contact = db.query(models.Contact).filter(models.Contact.phone == phone).first()
        event = db.query(models.CalendarEvent).filter(
            models.CalendarEvent.contact_id == contact.id,
            models.CalendarEvent.property_id.in_([314, 375])
        ).first()
        deal = db.query(models.Deal).filter(models.Deal.contact_id == contact.id).first()
        
        print("\n📊 RESULTADOS:")
        if event:
            print(f"✅ EVENTO OK: {event.title} ({event.start_time}) - Prop: {event.property_id}")
            if event.google_event_id:
                print(f"   ☁️ Sincronizado a Google: {event.google_event_id}")
        else:
            print("❌ EVENTO NO ENCONTRADO para San Lorenzo 1000")
            
        if deal:
            print(f"✅ DEAL OK: {deal.id}")
        else:
            print("❌ DEAL NO ENCONTRADO")
            
        return event is not None

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False
    finally:
        db.close()

def main():
    flows = [
        {
            "phone": "5493410000001",
            "name": "Juan Perez",
            "msgs": [
                "Hola, estoy buscando algo por Rosario, zona centro.",
                "Me interesa especialmente el departamento en San Lorenzo al 1000, ¿esta disponible?",
                "Dale, ¿podemos ir el lunes que viene a las 9:30? Avisame si podes agendarme."
            ]
        },
        {
            "phone": "5493410000002",
            "name": "Maria Garcia",
            "msgs": [
                "Buenas! Vi una oficina o depto en San Lorenzo 1047, tenes info?",
                "Me gusta. ¿A que hora se puede visitar el lunes?",
                "Ok, agendame para el lunes a las 9:00 porfa."
            ]
        },
        {
            "phone": "5493410000003",
            "name": "Carlos Rodriguez",
            "msgs": [
                "Hola, busco depto de 2 dormitorios.",
                "El que esta en San Lorenzo al 1000 me sirve. ¿Tiene balcon?",
                "Bárbaro. Quiero coordinar una visita para el lunes 16 de febrero a las 9:30. ¿Se puede?"
            ]
        },
        {
            "phone": "5493410000004",
            "name": "Ana Lopez",
            "msgs": [
                "Hola Agustina! Quiero ir a ver el de San Lorenzo 1047.",
                "¿Tenes lugar el lunes a las 9:00?",
                "Excelente, agendame."
            ]
        }
    ]

    success = 0
    for f in flows:
        if simulate_flow(f["phone"], f["name"], f["msgs"]):
            success += 1
            
    print(f"\nFinalizado. Exitosos: {success}/4")

if __name__ == "__main__":
    main()
