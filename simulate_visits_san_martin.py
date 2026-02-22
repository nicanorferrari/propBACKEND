import os
import time
import json
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Setup DB and Environment
load_dotenv()
db_url = os.getenv("DATABASE_URL").replace("postgres://", "postgresql://")
os.environ["DATABASE_URL"] = db_url

import models
from bot_engine import BotEngine

engine = create_engine(db_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def run_simulation():
    db = SessionLocal()
    instance_name = "urbano_crm_user_11" # Standard instance name
    
    # 1. Clean up potential previous test data for these numbers
    test_phones = [f"54934100000{i}" for i in range(11, 17)]
    for phone in test_phones:
        contact = db.query(models.Contact).filter(models.Contact.phone == phone).first()
        if contact:
            db.query(models.CalendarEvent).filter(models.CalendarEvent.contact_id == contact.id).delete()
            db.query(models.Deal).filter(models.Deal.contact_id == contact.id).delete()
            db.query(models.ChatHistory).filter(models.ChatHistory.sender_id == phone).delete()
            db.delete(contact)
    db.commit()

    # 2. Define personas
    personas = [
        {"name": "Pedro Gomez", "phone": "5493410000011", "msgs": ["Hola, estoy interesado en la oficina de San Martin 500.", "Me gustaria verla este lunes a las 9 am si se puede."]},
        {"name": "Laura Torres", "phone": "5493410000012", "msgs": ["Buen dia, vi una oficina en San Martin al 500. Tenes disponibilidad?", "Ok, agendame para el lunes a las 9:00 por favor."]},
        {"name": "Miguel Angel", "phone": "5493410000013", "msgs": ["Hola Agustina! Quiero visitar la oficina de San Martin 500 equipada.", "El lunes a las 9:30 podria ir?"]},
        {"name": "Sofia Ricci", "phone": "5493410000014", "msgs": ["Hola, consulto por la oficina de San Martin 500.", "Dale, quiero ir el lunes las 9:30."]},
        {"name": "Roberto Carlos", "phone": "5493410000015", "msgs": ["Hola, me interesa la oficina de San Martin 500.", "Tenes lugar para el lunes a las 9?"]},
        {"name": "Elena K", "phone": "5493410000016", "msgs": ["Hola, quiero ver la oficina equipada de San Martin.", "El lunes a las 9:30 tenes lugar?"]}
    ]

    report_content = "# Informe de Simulación de Visitas: San Martin 500\n\n"
    report_content += f"**Fecha de simulación:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    report_content += "**Propiedad:** Moderna oficina totalmente equipada (ID 378)\n"
    report_content += "**Reglas:** Lunes 09:00 - 10:00, Duración 30 min, Máx 2 simultáneos.\n\n"

    bot = BotEngine(instance_name)

    for p in personas:
        contact = models.Contact(name=p["name"], phone=p["phone"], tenant_id=1, source="SIMULATION")
        db.add(contact)
        db.commit()
        
        report_content += f"## Conversación con {p['name']} ({p['phone']})\n\n"
        
        for m in p["msgs"]:
            report_content += f"👤 **Usuario:** {m}\n\n"
            response = bot.process_message(p["phone"], m)
            report_content += f"🤖 **Agustina:** {response}\n\n"
            time.sleep(1) # Small delay for realism
        
        report_content += "---\n\n"

    # Final check on DB
    events = db.query(models.CalendarEvent).filter(models.CalendarEvent.property_id == 378).all()
    report_content += "## Resumen de Agenda en DB\n\n"
    if not events:
        report_content += "No se registraron eventos en la base de datos.\n"
    else:
        for e in events:
            report_content += f"- **{e.contact_name}**: {e.start_time.strftime('%Y-%m-%d %H:%M')} (Status: {e.status})\n"

    with open("c:/Users/Public/Documents/Inmobiliarias.ai/backend/informe_visitas_san_martin.md", "w", encoding="utf-8") as f:
        f.write(report_content)
    
    db.close()
    print("Simulación completada. Informe generado.")

if __name__ == "__main__":
    run_simulation()
