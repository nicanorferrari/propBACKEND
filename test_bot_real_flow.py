import os
import json
import time
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Reemplazar postgres:// por postgresql:// antes de importar modelos
load_dotenv()
db_url = os.getenv("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
os.environ["DATABASE_URL"] = db_url # Para que SessionLocal lo tome

import models

# Mocking Pydantic classes for the simulation tool
class MockObj:
    pass

def mock_pydantic():
    import schemas
    # Creamos mocks mínimos de lo que DealResponse espera para serializarse si fuera necesario
    # Pero el engine usa modelos de SQLAlchemy directamente. El problema es bot_engine.py.
    pass

from bot_engine import BotEngine

# Configuración de DB
engine = create_engine(db_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def simulate_real_flow():
    db = SessionLocal()
    try:
        # 0. Limpiar el desorden previo si existe
        phone = "5493415559900"
        instance_name = "urbano_crm_user_11"
        
        # Eliminar registros previos de este teléfono para una prueba limpia
        test_contact = db.query(models.Contact).filter(models.Contact.phone == phone).first()
        if test_contact:
            db.query(models.CalendarEvent).filter(models.CalendarEvent.contact_id == test_contact.id).delete()
            db.query(models.Deal).filter(models.Deal.contact_id == test_contact.id).delete()
            db.query(models.ContactInteraction).filter(models.ContactInteraction.contact_id == test_contact.id).delete()
            db.query(models.ChatHistory).filter(models.ChatHistory.sender_id == phone).delete()
            db.delete(test_contact)
            db.commit()

        # Asegurar que el contacto existe (el bot lo requiere en schedule_visit)
        contact = models.Contact(
            name="Lead Simulación",
            phone=phone,
            tenant_id=1,
            source="WHATSAPP",
            created_at=datetime.now(timezone.utc)
        )
        db.add(contact)
        db.commit()

        print(f"\n🚀 INICIANDO SIMULACIÓN REAL - Teléfono: {phone}")
        print(f"🤖 Bot Instance: {instance_name}")
        
        # Inicializar el motor del bot
        bot = BotEngine(instance_name)
        
        # --- FLUJO DE CONVERSACIÓN ---
        # 1. Consulta el bot
        print(f"\n👤 USUARIO: Quiero ver el de San Lorenzo 1047.")
        resp_1 = bot.process_message(phone, "Quiero ver el de San Lorenzo 1047.")
        print(f"🤖 AGUSTINA: {resp_1}")

        # 2. Agenda (Usamos el lunes 16 Feb 2026 que sabemos que está habilitado)
        print(f"\n👤 USUARIO: Agendame para el lunes 16 de febrero a las 9:30hs.")
        resp_2 = bot.process_message(phone, "Agendame para el lunes 16 de febrero a las 9:30hs.")
        print(f"🤖 AGUSTINA: {resp_2}")

        print("\n" + "="*50)
        print("🔍 COMPROBANDO REGISTROS EN BASE DE DATOS...")
        
        db.expire_all()

        # 1. Comprobar Evento
        event = db.query(models.CalendarEvent).filter(models.CalendarEvent.contact_id == contact.id).first()
        if event:
            print(f"✅ Evento Agendado: {event.title} ({event.start_time})")
        else:
            print("❌ Evento NO encontrado.")

        # 2. Comprobar Oportunidad (NUEVA LÓGICA)
        deal = db.query(models.Deal).filter(models.Deal.contact_id == contact.id).first()
        if deal:
            print(f"✅ Oportunidad Creada: {deal.title} - Monto: {deal.value}")
            # Ver etapa
            stage = db.query(models.PipelineStage).get(deal.pipeline_stage_id)
            print(f"   Etapa: {stage.name if stage else deal.pipeline_stage_id}")
        else:
            print("❌ Oportunidad NO creada automáticamente.")

        print("="*50)

    except Exception as e:
        print(f"❌ ERROR EN SIMULACIÓN: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    simulate_real_flow()
