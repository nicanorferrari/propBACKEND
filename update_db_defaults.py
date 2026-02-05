import sys
import os
import json

# Ensure we can import from the current directory (which should be backend)
sys.path.append(os.getcwd())

from database import SessionLocal
from models import Bot

# DEFAULT IDENTITY (Argentine Accent)
DEFAULT_IDENTITY = """Eres Agustina, una asesora inmobiliaria de élite en Rosario, Argentina, trabajando para PropCRM.

- IDENTIDAD:
  - No sos un robot, ni un asistente virtual genérico. Sos Agustina.
  - Hablas con acento argentino marcado, con entonación rioplatense ("Che", "Viste", "Te cuento", "Bárbaro", "Dale").
  - Tu tono es cálido, empático y proactivo. Te preocupas genuinamente por encontrar la propiedad ideal.
  - Conoces Rosario: mencionas detalles de zonas (Pichincha, Alberdi, Centro, Funes) como un local.

- REGLAS DE CONVERSACIÓN (HUMANIZACIÓN):
  1. **Cero Robot**: Evita frases como "He encontrado 3 resultados". Di: "Mira, justo entraron estas opciones que encajan con lo que buscás...".
  2. **Variedad**: No uses siempre la misma estructura. A veces sé breve, a veces explayate.
  3. **Memoria Activa**: Si el usuario mencionó antes que tiene hijos o perro, ÚSALO.
  4. **Honestidad Brutal**: Si no hay nada bueno, no inventes. "La verdad, por ese precio en esa zona está difícil hoy, pero ¿qué te parece si miramos en...?"
  5. **Call to Action Suave**: No presiones. Invita. "¿Te imaginás viviendo acá? Si querés la vamos a ver".
"""

def get_247_hours():
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return {day: {"start": "00:00", "end": "23:59", "enabled": True} for day in days}

def update():
    db = SessionLocal()
    try:
        # Find WhatsApp bot
        bot = db.query(Bot).filter(Bot.platform == "whatsapp").first()
        
        if not bot:
            print("No WhatsApp bot found in database.")
            return

        print(f"Updating Bot ID: {bot.id} (Instance: {bot.instance_name})")
        
        # 1. System Prompt
        if not bot.system_prompt:
            print("  - Setting default system_prompt.")
            bot.system_prompt = DEFAULT_IDENTITY
        else:
            print("  - system_prompt already set.")

        # 2. Business Hours
        if not bot.business_hours:
            print("  - Setting default 24/7 business_hours.")
            bot.business_hours = get_247_hours()
        else:
            print("  - business_hours already set.")

        # 3. Config (Voice & Notifications)
        # We need to be careful not to overwrite unrelated config
        current_config = dict(bot.config) if bot.config else {}
        changed_config = False

        # Voice
        if "voice" not in current_config:
            print("  - Setting default Voice config (Kore, Enabled).")
            current_config["voice"] = {"enabled": True, "voice_name": "Kore"}
            changed_config = True
        
        # Notifications
        if "notifications" not in current_config:
            print("  - Setting default Notifications config (24h/1h).")
            current_config["notifications"] = {"remind_1d": False, "remind_1h": True}
            changed_config = True

        if changed_config:
            bot.config = current_config
            print("  - Config updated.")
        else:
            print("  - Config already consistent.")

        db.commit()
        print("Database update complete.")

    except Exception as e:
        print(f"Error updating defaults: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    update()
