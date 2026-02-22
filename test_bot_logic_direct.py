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

# Configuración de DB
engine = create_engine(db_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def simulate_real_flow():
    db = SessionLocal()
    try:
        # 1. Configuración de prueba
        phone = "5493415559900"
        instance_name = "urbano_crm_user_11"
        property_id = 314 # San Lorenzo 1047
        
        # 2. Limpieza Previa
        test_contact = db.query(models.Contact).filter(models.Contact.phone == phone).first()
        if test_contact:
            db.query(models.CalendarEvent).filter(models.CalendarEvent.contact_id == test_contact.id).delete()
            db.query(models.Deal).filter(models.Deal.contact_id == test_contact.id).delete()
            db.query(models.ContactInteraction).filter(models.ContactInteraction.contact_id == test_contact.id).delete()
            db.query(models.ChatHistory).filter(models.ChatHistory.sender_id == phone).delete()
            db.delete(test_contact)
            db.commit()

        # 3. Crear Contacto
        contact = models.Contact(
            name="Lead Simulación",
            phone=phone,
            tenant_id=1,
            source="WHATSAPP"
        )
        db.add(contact)
        db.commit()

        print(f"\n🚀 SIMULACIÓN DE LLAMADA DIRECTA A schedule_visit")
        print(f"📞 Contacto: {phone} (ID: {contact.id})")
        print(f"🏠 Propiedad: {property_id}")
        
        # 4. Instanciar BotEngine y LLAMAR DIRECTAMENTE A LA HERRAMIENTA
        from bot_engine import BotEngine
        bot = BotEngine(instance_name)
        bot.current_phone = phone # Simular contexto del bot
        
        # Fecha habilitada: Próximo lunes (San Lorenzo 1047 solo lunes 9-10)
        # 2026-02-16 es lunes
        test_date = "2026-02-16"
        test_time = "09:30"
        
        print(f"📅 Intentando agendar para: {test_date} {test_time}")
        
        # Ejecutar la lógica de agendamiento
        result = bot.schedule_visit(property_id, test_date, test_time)
        print(f"🤖 RESULTADO TOOL: {result}")

        print("\n" + "="*50)
        print("🔍 COMPROBANDO REGISTROS EN BASE DE DATOS...")
        
        db.expire_all()

        # Check Event
        event = db.query(models.CalendarEvent).filter(models.CalendarEvent.contact_id == contact.id).first()
        if event:
            print(f"✅ Evento Agendado: {event.title} ({event.start_time})")
        else:
            print("❌ Evento NO encontrado.")

        # Check Deal
        deal = db.query(models.Deal).filter(models.Deal.contact_id == contact.id).first()
        if deal:
            print(f"✅ Oportunidad Creada: {deal.title} - Monto: {deal.value}")
            stage = db.query(models.PipelineStage).get(deal.pipeline_stage_id)
            print(f"   Etapa: {stage.name if stage else deal.pipeline_stage_id}")
        else:
            print("❌ Oportunidad NO creada.")

        print("="*50)

    except Exception as e:
        print(f"❌ ERROR EN SIMULACIÓN: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    simulate_real_flow()
