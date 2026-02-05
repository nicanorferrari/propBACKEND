import os
import logging
from datetime import datetime, timedelta
import google.generativeai as genai
from sqlalchemy.orm import Session
import models
from database import SessionLocal

logger = logging.getLogger("urbanocrm.bot_engine")

# Configurar API Key de Gemini
API_KEY = os.getenv("API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)

def get_bot_context(db: Session, bot_id: int):
    bot = db.query(models.Bot).get(bot_id)
    return bot

def search_properties(operation: str = None, property_type: str = None, budget_max: float = None, zone: str = None, rooms: int = None):
    """
    Busca propiedades disponibles en el CRM basándose en criterios.
    Args:
        operation: 'Sale' (venta) o 'Rent' (alquiler).
        property_type: 'House', 'Apartment', 'PH', 'Land'.
        budget_max: Presupuesto máximo estimado.
        zone: Barrio o zona de interés.
        rooms: Cantidad de ambientes.
    """
    db = SessionLocal()
    try:
        query = db.query(models.Property).filter(models.Property.status == "Active")
        if operation: query = query.filter(models.Property.operation.ilike(operation))
        if property_type: query = query.filter(models.Property.type.ilike(property_type))
        if budget_max: query = query.filter(models.Property.price <= budget_max)
        if zone: query = query.filter(models.Property.neighborhood.ilike(f"%{zone}%"))
        if rooms: query = query.filter(models.Property.rooms >= rooms)
        
        results = query.limit(4).all()
        return [
            {
                "id": p.id, 
                "title": p.title, 
                "price": f"{p.currency} {p.price:,.0f}", 
                "zone": p.neighborhood,
                "rooms": p.rooms,
                "code": p.code,
                "agent": f"{p.assigned_agent.first_name} {p.assigned_agent.last_name}" if p.assigned_agent else "Oficina",
                "agent_phone": p.assigned_agent.phone_mobile if p.assigned_agent else None,
                "maps_link": f"https://www.google.com/maps/search/?api=1&query={p.lat},{p.lng}" if p.lat and p.lng else None
            } for p in results
        ]
    finally:
        db.close()

def get_availability(property_id: int):
    """
    Consulta los días y horarios disponibles para visitar una propiedad específica.
    Args:
        property_id: El ID de la propiedad que el cliente quiere visitar.
    """
    # Usar lógica existente en routers/bots.py
    from routers.bots import check_bot_availability
    db = SessionLocal()
    try:
        # Buscamos la instancia del bot para esta propiedad (dueño)
        prop = db.query(models.Property).get(property_id)
        if not prop: return "Propiedad no encontrada."
        
        bot = db.query(models.Bot).filter(models.Bot.user_id == prop.assigned_agent_id).first()
        if not bot: return "Agente no tiene bot activo."
        
        # Llamar a la lógica de disponibilidad (3 días por defecto)
        result = check_bot_availability(bot.instance_name, property_id=property_id, db=db)
        return result
    finally:
        db.close()

class BotEngine:
    def __init__(self, bot_instance_name: str):
        self.instance_name = bot_instance_name
        self.db = SessionLocal()
        self.bot = self.db.query(models.Bot).filter(models.Bot.instance_name == bot_instance_name).first()
        
        if not self.bot:
            logger.error(f"Bot instance {bot_instance_name} not found in DB")
            return

        # Initialize Model with Tools
        model_name = os.getenv("CHATBOT_MODEL", "gemini-1.5-flash")
        logger.info(f"Bot Engine: Initializing model {model_name}")
        
        self.model = genai.GenerativeModel(
            model_name=model_name,
            tools=[search_properties, get_availability],
            system_instruction=self.bot.system_prompt or "Eres una asesora inmobiliaria llamada Agustina."
        )

    def get_history(self, phone: str):
        history = self.db.query(models.ChatHistory).filter(
            models.ChatHistory.sender_id == phone
        ).order_by(models.ChatHistory.created_at.desc()).limit(15).all()
        
        formatted_history = []
        for msg in reversed(history):
            formatted_history.append({
                "role": msg.role,
                "parts": msg.parts
            })
        return formatted_history

    def save_message(self, phone: str, role: str, text: str):
        new_msg = models.ChatHistory(
            sender_id=phone,
            role=role,
            parts=[text]
        )
        self.db.add(new_msg)
        self.db.commit()

    def process_message(self, phone: str, user_text: str):
        if not self.bot: return "Error: Bot no configurado."
        
        self.save_message(phone, "user", user_text)
        history = self.get_history(phone)
        
        # history[:-1] because start_chat expects history without the current message
        chat = self.model.start_chat(history=history[:-1], enable_automatic_function_calling=True)
        
        try:
            response = chat.send_message(user_text)
            bot_response = response.text
            self.save_message(phone, "model", bot_response)
            return bot_response
        except Exception as e:
            logger.error(f"Gemini Error for {phone}: {e}")
            return "Lo siento, tuve un problema técnico. ¿Podemos seguir en un ratito?"
        finally:
            self.db.close()
