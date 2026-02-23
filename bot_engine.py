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

def search_properties(semantic_query: str = None, operation: str = None, property_type: str = None, budget_max: float = None, zone: str = None, rooms: int = None):
    """
    Busca propiedades disponibles en el CRM basándose en criterios o texto natural.
    Args:
        semantic_query: Búsqueda natural semántica (Ej: 'departamento luminoso tipo feng shui antiguo', 'patio con parrillero').
        operation: 'Sale' (venta) o 'Rent' (alquiler).
        property_type: 'House', 'Apartment', 'PH', 'Land'.
        budget_max: Presupuesto máximo estimado.
        zone: Barrio o zona de interés.
        rooms: Cantidad de ambientes.
    """
    db = SessionLocal()
    try:
        from sqlalchemy import text
        from routers import ai_service
        
        query = db.query(models.Property).filter(models.Property.status == "Active")
        if operation: query = query.filter(models.Property.operation.ilike(operation))
        if property_type: query = query.filter(models.Property.type.ilike(property_type))
        if budget_max: query = query.filter(models.Property.price <= budget_max)
        if zone: query = query.filter(models.Property.neighborhood.ilike(f"%{zone}%"))
        if rooms: query = query.filter(models.Property.rooms >= rooms)
        
        # SI el bot provee una búsqueda semántica, aplicamos pgvector sorting
        if semantic_query:
            query_vector = ai_service.get_embedding(semantic_query)
            if query_vector:
                # Filtrar nulos para no romper la distancia y ordenar por COSINE similarity inversa
                query = query.filter(models.Property.embedding_descripcion != None)
                query = query.order_by(text(f"(1 - (embedding_descripcion <=> '{query_vector}')) DESC"))
        else:
            query = query.order_by(models.Property.created_at.desc())
            
        results = query.limit(5).all()
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
                "link": f"https://app.inmobiliarias.ai/p/{p.code}" if p.code else None,
                "maps_link": f"https://www.google.com/maps/search/?api=1&query={p.lat},{p.lng}" if p.lat and p.lng else None,
                "features": ", ".join(p.attributes) if p.attributes else "",
                "description": (p.description or "")[:150] + "..."
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
        if not prop or prop.status == 'Deleted': return "Propiedad no encontrada o no disponible."
        
        bot = db.query(models.Bot).filter(models.Bot.user_id == prop.assigned_agent_id).first()
        if not bot: return "Agente no tiene bot activo."
        
        # Llamar a la lógica de disponibilidad (3 días por defecto)
        result = check_bot_availability(bot.instance_name, property_id=property_id, db=db)
        return result
    finally:
        db.close()

def get_property_requisites(property_id: int):
    """
    Consulta los requisitos de alquiler o venta (garantías, expensas, condiciones) de una propiedad específica.
    Usar esta herramienta cuando el cliente pregunte por requisitos para ingresar, garantías aceptadas o condiciones comerciales.
    Args:
        property_id: El ID numérico de la propiedad.
    """
    db = SessionLocal()
    try:
        prop = db.query(models.Property).get(property_id)
        if not prop or prop.status == 'Deleted': 
            return "Propiedad no encontrada o no disponible."
        
        reqs = prop.transaction_requirements or "No hay requisitos especiales documentados. Por favor, consultar directo con el agente para más detalles."
        
        return f"Requisitos y condiciones para propiedad {prop.code or prop.title}:\n{reqs}"
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
            tools=[search_properties, get_availability, get_property_requisites, self.schedule_visit, self.update_lead_preferences],
            system_instruction=self.bot.system_prompt or "Eres una asesora inmobiliaria llamada Agustina."
        )
        self.current_phone = None

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
        
        self.current_phone = phone
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

    def update_lead_preferences(self, budget: float = None, zone: str = None, property_type: str = None, operation: str = None, notes: str = None):
        """
        Actualiza el perfil y preferencias del cliente en el CRM.
        Utiliza esta herramienta proactivamente cuando el cliente mencione su presupuesto, la zona donde busca, si quiere comprar/alquilar, o cualquier dato útil para el vendedor.
        Args:
            budget: Presupuesto máximo estimado (solo número).
            zone: Zonas, barrios o ciudades de preferencia (ej: 'Palermo, Recoleta').
            property_type: Tipo de propiedad buscada ('Casa', 'Departamento', 'Lote').
            operation: Operación deseada ('Venta', 'Alquiler').
            notes: Cosas importantes. Ej: 'Busca con balcón', 'Acepta 2 mascotas', 'Busca dueño directo'.
        """
        logger.info(f"Bot Tool: Updating lead preferences for {self.current_phone}")
        
        if not self.current_phone:
            return "No pude identificar tu número."
            
        try:
            contact = self.db.query(models.Contact).filter(models.Contact.phone == self.current_phone).first()
            if not contact:
                return "No encontré tu contacto en la base de datos."
                
            new_info = []
            if operation: new_info.append(f"Op: {operation}")
            if property_type: new_info.append(f"Tipo: {property_type}")
            if zone: new_info.append(f"Zona: {zone}")
            if budget: new_info.append(f"Presupuesto max: {budget}")
            if notes: new_info.append(f"Extra: {notes}")
            
            if not new_info:
                return "No hay preferencias valiosas para guardar."
                
            update_str = f"[{datetime.now().strftime('%d/%m/%Y')} INFO IA] " + " | ".join(new_info)
            
            # Chequeo preventivo: solo agregar si no dijimos exactamente eso hace poco
            if contact.notes:
                if update_str not in contact.notes:
                    contact.notes = f"{contact.notes}\n{update_str}"
            else:
                contact.notes = update_str
                
            # Bonus: Actualizar el lead score si nos da muchas pistas (+5 por info)
            if contact.lead_score < 100:
                contact.lead_score = min(contact.lead_score + 5, 100)
                
            # Generar embedding del nuevo perfil para Reverse Matching
            try:
                from routers import ai_service
                pref_vec = ai_service.get_embedding(contact.notes)
                if pref_vec:
                    contact.embedding_preferences = pref_vec
            except Exception as e:
                logger.error(f"Error generating embedding for lead pref: {e}")
                
            self.db.commit()
            return "Perfil de cliente enriquecido en el CRM exitosamente. Ahora el sistema de IA emparejará estas preferencias con el catálogo."
        except Exception as e:
            logger.error(f"Lead Pref Update Error: {e}")
            return "Error al guardar el perfil en el CRM."

    def schedule_visit(self, property_id: int, date: str, time: str):
        """
        Agenda una visita para una propiedad en el CRM.
        Args:
            property_id: ID de la propiedad a visitar.
            date: Fecha en formato exacto YYYY-MM-DD (Ej: 2024-02-15).
            time: Hora en formato HH:MM (Ej: 15:30).
        """
        logger.info(f"Bot Tool: Scheduling visit for prop {property_id} at {date} {time} for {self.current_phone}")
        
        if not self.current_phone:
            return "Error: No pude identificar tu número."

        try:
            # 1. Contact
            contact = self.db.query(models.Contact).filter(models.Contact.phone == self.current_phone).first()
            if not contact:
                return "No encontré tu contacto registrado."

            # 2. Property
            prop = self.db.query(models.Property).get(property_id)
            if not prop:
                return "Propiedad no encontrada."

            # 3. Parse Date
            try:
                start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
            except ValueError:
                return "Formato de fecha u hora incorrecto. Usa YYYY-MM-DD y HH:MM."

            end_dt = start_dt + timedelta(minutes=30)

            # 4. Create Event
            event = models.CalendarEvent(
                title=f"Visita: {prop.code or prop.title}",
                start_time=start_dt,
                end_time=end_dt,
                type="VISIT",
                source="CRM",
                agent_id=prop.assigned_agent_id,
                contact_id=contact.id,
                contact_name=contact.name,
                property_id=prop.id,
                tenant_id=prop.tenant_id or contact.tenant_id,
                status="CONFIRMED",
                description=f"Agendado por Bot WhatsApp para propiedad {prop.code}."
            )
            
            self.db.add(event)
            self.db.commit()

            # 5. Create Deal (Lead) automatically
            try:
                # Find stage "Visita Agendada" or first stage
                stage = self.db.query(models.PipelineStage).filter(
                    models.PipelineStage.name.ilike("%Visita Agendada%")
                ).first()
                if not stage:
                    stage = self.db.query(models.PipelineStage).order_by(models.PipelineStage.id).first()
                
                if stage:
                    new_deal = models.Deal(
                        tenant_id=prop.tenant_id or contact.tenant_id,
                        title=f"Visita: {contact.name} - {prop.title[:20]}",
                        value=prop.price,
                        currency=prop.currency,
                        pipeline_stage_id=stage.id,
                        property_id=prop.id,
                        contact_id=contact.id,
                        assigned_agent_id=prop.assigned_agent_id,
                        priority="HIGH",
                        status="OPEN",
                        requirements=f"Interesado en {prop.title}. Agendó visita via Bot para {date} {time}."
                    )
                    self.db.add(new_deal)
                    self.db.commit()
                    logger.info(f"Bot Engine: Deal created for visit: {new_deal.id}")
            except Exception as de:
                logger.error(f"Error creating auto-deal: {de}")
            
            # Log Activity
            self.db.add(models.ActivityLog(
                user_id=prop.assigned_agent_id,
                action="CREATE",
                entity_type="EVENT",
                entity_id=event.id,
                description=f"Bot agendó visita para {contact.name}"
            ))
            self.db.commit()

            # --- Google Sync ---
            try:
                from routers.google import get_valid_google_token, get_valid_agency_token, create_google_event
                
                agent = self.db.query(models.User).get(event.agent_id) if event.agent_id else None
                agency = self.db.query(models.AgencyConfig).first()
                
                organizer_token = None
                attendees = []
                
                # 1. Check Agent (Primary Priority)
                if agent and agent.google_refresh_token:
                    organizer_token = get_valid_google_token(agent, self.db)
                    # Invite Agency if configured
                    if agency and agency.google_email:
                        attendees.append({"email": agency.google_email})

                # 2. Check Agency (Fallback Priority)
                if not organizer_token and agency and agency.google_refresh_token:
                    organizer_token = get_valid_agency_token(agency, self.db)
                    # Invite Agent if exists
                    if agent and agent.email:
                        attendees.append({"email": agent.email})
                
                if organizer_token:
                    g_event = {
                        "summary": event.title,
                        "location": event.property_address or prop.address or "Ubicación a confirmar",
                        "description": event.description or "",
                        "start": {"dateTime": start_dt.isoformat(), "timeZone": "America/Argentina/Buenos_Aires"},
                        "end": {"dateTime": end_dt.isoformat(), "timeZone": "America/Argentina/Buenos_Aires"},
                        "attendees": attendees
                    }
                    
                    res = create_google_event(organizer_token, g_event)
                    if res.ok:
                        data = res.json()
                        event.google_event_id = data.get("id")
                        self.db.commit()
                        logger.info(f"Google Sync Success: {data.get('id')}")
                    else:
                        logger.error(f"Google Sync Failed: {res.text}")
                else:
                    logger.warning("Skipping Google Sync: No connected accounts found.")

            except Exception as e:
                logger.error(f"Google Sync Logic Error: {e}")
            # -------------------

            return f"¡Listo! Visita agendada para el {date} a las {time}. Te esperamos en {prop.address}."

        except Exception as e:
            logger.error(f"Schedule Error: {e}")
            return "Ocurrió un error al agendar la visita."
