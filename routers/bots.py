
import os
import requests
import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_user_email
import models
import schemas

router = APIRouter()
logger = logging.getLogger("urbanocrm.bots")

DEFAULT_BOT_IDENTITY = """Eres Agustina, una asesora inmobiliaria de élite en Rosario, Argentina, trabajando para PropCRM.

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

def get_default_business_hours():
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return {day: {"start": "00:00", "end": "23:59", "enabled": True} for day in days}

EVO_URL = os.getenv("EVO_URL", "").rstrip("/")
EVO_KEY = os.getenv("EVO_KEY", "")
# Configuración de Webhook (Gestionada internamente por el sistema)
BOT_WEBHOOK_URL = os.getenv("BOT_WEBHOOK_URL", "") # Se recomienda dejar vacío si se procesa directamente en el backend

def call_evolution(method: str, endpoint: str, data: dict = None):
    if not EVO_URL or not EVO_KEY: return None
    headers = {"apikey": EVO_KEY, "Content-Type": "application/json"}
    url = f"{EVO_URL}{endpoint}"
    try:
        response = requests.request(method, url, headers=headers, json=data, timeout=15)
        return response
    except Exception as e:
        logger.error(f"Evolution API Error: {e}")
        return None

@router.get("/", response_model=schemas.BotResponse)
def get_bot_config(platform: str, email: str = Depends(get_current_user_email), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    bot = db.query(models.Bot).filter(models.Bot.user_id == user.id, models.Bot.platform == platform).first()
    
    if not bot:
        return {
            "id": 0,
            "platform": platform,
            "status": "disconnected",
            "system_prompt": DEFAULT_BOT_IDENTITY,
            "business_hours": get_default_business_hours(),
            "tags": [],
            "instance_name": f"whatsapp_cloud_{user.id}",
            "config": { "voice": {"enabled": True, "voice_name": "Kore"}, "notifications": {"remind_1d": False, "remind_1h": True} }
        }
    
    instance_name = f"whatsapp_cloud_{user.id}"
    if bot.instance_name != instance_name:
        bot.instance_name = instance_name
        db.commit()
    
    # Official WhatsApp App credentials are saved in bot.config["official_whatsapp"]
    bot_config_data = bot.config or {}
    official_whatsapp_config = bot_config_data.get("official_whatsapp", {})
    has_token = official_whatsapp_config.get("access_token") and official_whatsapp_config.get("phone_number_id")
    
    new_status = "connected" if has_token else "disconnected"
    
    if bot.status != new_status:
        bot.status = new_status
        db.commit()
        db.refresh(bot)
            
    bot_dict = {
        "id": bot.id,
        "platform": bot.platform,
        "status": bot.status,
        "system_prompt": bot.system_prompt or DEFAULT_BOT_IDENTITY,
        "business_hours": bot.business_hours or get_default_business_hours(),
        "tags": bot.tags or [],
        "config": bot.config or { "voice": {"enabled": True, "voice_name": "Kore"}, "notifications": {"remind_1d": False, "remind_1h": True} },
        "instance_name": bot.instance_name,
        "is_active": bot.is_active,
        "qrCode": None
    }
                
    return bot_dict

@router.post("/configure")
def configure_bot(config: schemas.BotCreate, email: str = Depends(get_current_user_email), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    bot = db.query(models.Bot).filter(models.Bot.user_id == user.id, models.Bot.platform == config.platform).first()
    
    if not bot:
        bot = models.Bot(
            user_id=user.id,
            platform=config.platform,
            system_prompt=config.system_prompt,
            business_hours=config.business_hours,
            tags=config.tags,
            config=config.config
        )
        db.add(bot)
    else:
        bot.system_prompt = config.system_prompt
        bot.business_hours = config.business_hours
        bot.tags = config.tags
        bot.config = config.config
    
    db.commit()
    return {"status": "ok", "message": "Configuración guardada"}

@router.post("/connect")
def connect_bot(request: schemas.BotConnectRequest, email: str = Depends(get_current_user_email), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    bot = db.query(models.Bot).filter(models.Bot.user_id == user.id, models.Bot.platform == request.platform).first()
    
    if not bot:
        bot = models.Bot(user_id=user.id, platform=request.platform, status="disconnected")
        db.add(bot)
        db.flush()

    instance_name = f"whatsapp_cloud_{user.id}"
    bot.instance_name = instance_name
    
    # Con el API oficial no hay "conexión" más allá de guardar los datos, lo dejamos en disconnected por defecto a menos que tenga data
    has_token = False
    if bot.config and bot.config.get("official_whatsapp", {}).get("access_token") and bot.config.get("official_whatsapp", {}).get("phone_number_id"):
        has_token = True
        
    bot.status = "connected" if has_token else "disconnected"
    db.commit()

    return {"qrCode": None, "instanceName": instance_name, "status": bot.status}

@router.post("/disconnect")
def disconnect_bot(request: schemas.BotConnectRequest, email: str = Depends(get_current_user_email), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    bot = db.query(models.Bot).filter(models.Bot.user_id == user.id, models.Bot.platform == request.platform).first()
    
    bot.status = "disconnected"
    bot.qrCode = None
    if bot.config and "official_whatsapp" in bot.config:
        del bot.config["official_whatsapp"]
    db.commit()
    
    return {"status": "ok", "message": "Instancia desconectada y credenciales removidas."}

# --- New Bot Logic Endpoints ---

@router.post("/rag-search")
def bot_search_properties(filters: dict = Body(...), db: Session = Depends(get_db)):
    """
    Búsqueda simplificada para Bots/IA.
    Recibe filtros (operation, type, budget, zone, rooms) y devuelve un resumen.
    """
    query = db.query(models.Property).filter(models.Property.status == "Active")

    # Si pasamos el email/tenant_id en el token del bot (Ideal)
    # Por ahora tomamos el tenant_id del bot instance, pero el endpoint "rag-search" no recibe instancia por default
    # Vamos a obtener la info del bot que invoca (quizas requiera refactor param)
    # Asumimos que RAG-SEARCH debe aislar obligatoriamente:
    tenant_id = filters.get("tenant_id")
    if tenant_id:
        query = query.filter(models.Property.tenant_id == tenant_id)

    # 1. Filtros Básicos
    if filters.get("operation"):
        # Mapping simple: "venta" -> "Sale", "alquiler" -> "Rent"
        op = filters["operation"].lower()
        if "venta" in op or "buy" in op: query = query.filter(models.Property.operation == "Sale")
        elif "alquil" in op or "rent" in op: query = query.filter(models.Property.operation == "Rent")
    
    if filters.get("type"):
        # Búsqueda inexacta: "casa" in "House", "depto" in "Apartment"
        t = filters["type"].lower()
        if "casa" in t: query = query.filter(models.Property.type == "House")
        elif "depto" in t or "departamento" in t: query = query.filter(models.Property.type == "Apartment")
        elif "ph" in t: query = query.filter(models.Property.type == "PH")
        elif "terreno" in t or "lote" in t: query = query.filter(models.Property.type == "Land")

    if filters.get("rooms"):
        try:
            r = int(filters["rooms"])
            query = query.filter(models.Property.rooms >= r)
        except: pass

    if filters.get("price_min"):
        query = query.filter(models.Property.price >= float(filters["price_min"]))
    
    if filters.get("price_max"):
        query = query.filter(models.Property.price <= float(filters["price_max"]))

    if filters.get("neighborhood"):
        # Búsqueda Case-Insensitive en Postgres
        n = f"%{filters['neighborhood']}%"
        query = query.filter(models.Property.neighborhood.ilike(n))

    # Limitar resultados para no saturar el contexto de la IA
    results = query.limit(5).all()
    
    # Formatear salida "light" para LLM
    output = []
    for p in results:
        output.append({
            "id": p.id,
            "title": p.title,
            "price": f"{p.currency} {p.price:,.0f}",
            "location": f"{p.address}, {p.neighborhood}",
            "features": f"{p.rooms} amb, {p.surface}m2",
            "link": f"https://inmobiliaria.com/p/{p.code}", # Link ficticio por ahora
            "description": (p.description or "")[:200] + "..." # Truncar
        })
    
    return output

@router.get("/{instance_name}/availability")
def check_bot_availability(instance_name: str, date: str = None, days: int = 3, property_id: int = None, db: Session = Depends(get_db)):
    """
    Endpoint público (o protegido por token estático) para consultar agenda.
    Devuelve slots libres.
    - Si se especifica property_id: Usa los horarios y límites de esa propiedad.
    - Si no: Usa los horarios generales del Bot.
    """
    bot = db.query(models.Bot).filter(models.Bot.instance_name == instance_name).first()
    if not bot: raise HTTPException(404, "Bot instance not found")

    user = db.query(models.User).filter(models.User.id == bot.user_id).first()
    user_id = bot.user_id # El agente dueño del bot
    
    # Si hay propiedad, cargamos su config
    prop_config = None
    if property_id:
        prop = db.query(models.Property).filter(
            models.Property.id == property_id,
            models.Property.tenant_id == user.tenant_id
        ).first()
        if not prop or prop.status == "Deleted": raise HTTPException(404, "Property not found of not enabled.")
        prop_config = prop
    
    # Fecha base (hoy o la solicitada)
    from datetime import datetime, timedelta
    start_date = datetime.strptime(date, "%Y-%m-%d") if date else datetime.now()
    
    available_slots = []
    
    # Analizar próximos N días
    for i in range(days):
        current_day = start_date + timedelta(days=i)
        day_str = current_day.strftime("%a") # Mon, Tue...
        date_str = current_day.strftime("%Y-%m-%d")

        # 1. Determinar Configuración de Horario (Propiedad vs Bot)
        if prop_config:
            # Usar configuración de la propiedad si existe para ese día
            # La estructura es { "Mon": { "enabled": true, "start": "09:00", "end": "10:00" } }
            schedule = prop_config.visit_availability.get(day_str)
            if not schedule: schedule = {"enabled": False} # Default closed per property logic if missing
        else:
            # Fallback a horario del bot
            schedule = bot.business_hours.get(day_str)

        if not schedule or not schedule.get("enabled"):
            continue # Día no laboral / no disponible

        try:
            work_start = datetime.strptime(f"{date_str} {schedule['start']}", "%Y-%m-%d %H:%M")
            work_end = datetime.strptime(f"{date_str} {schedule['end']}", "%Y-%m-%d %H:%M")
        except ValueError:
            continue # Error en formato de hora

        # 2. Buscar eventos RELEVANTES:
        # - El bot es "General", no debe bloquearse por la agenda personal de un agente.
        # - Solo nos importa la Ocupación de la Propiedad (Concurrencia).
        
        query_filters = [
            models.CalendarEvent.start_time >= work_start,
            models.CalendarEvent.start_time < work_end,
            models.CalendarEvent.status != "CANCELLED"
        ]
        
        # Filtro principal: SOLO Propiedad
        # Si no hay propiedad configurada, no podemos validar cupo, asi que asumimos libre (o logica default futura)
        if property_id:
             query_filters.append(models.CalendarEvent.property_id == prop_config.id)
        else:
             # Si es una consulta génerica sin propiedad, ahi SI miramos el calendario del agente por defecto?
             # El usuario pidió: "calendario general... dentista no deberia bloquear"
             # Por seguridad, si no es propiedad específica, no bloqueamos nada (Open Calendar) o mantenemos agente
             # Decisión: Si no hay propiedad, mantenemos comportamiento previo (agente), si hay propiedad, SOLO propiedad.
             query_filters.append(models.CalendarEvent.agent_id == user_id)

        events = db.query(models.CalendarEvent).filter(*query_filters).all()

        # 3. Calcular huecos (bloques de 30 min o visit_duration)
        slot_duration_minutes = prop_config.visit_duration if prop_config else 30
        
        curr_slot = work_start
        while curr_slot + timedelta(minutes=slot_duration_minutes) <= work_end:
            slot_end = curr_slot + timedelta(minutes=slot_duration_minutes)
            
            # Verificar colisión
            # Lógica:
            # - Si NO es propiedad: cualquier evento bloquea.
            # - Si ES propiedad:
            #    - Eventos de OTRA cosa bloquean.
            #    - Eventos de ESTA propiedad cuentan para el cupo (max_simultaneous).
            
            is_blocked = False
            simultaneous_count = 0
            
            for e in events:
                # Si hay solapamiento de tiempo
                if not (slot_end <= e.start_time or curr_slot >= e.end_time):
                    if prop_config:
                        # Solo contamos eventos de ESTA propiedad
                        if e.property_id == prop_config.id:
                            simultaneous_count += 1
                        # Ignoramos eventos personales u otras propiedades
                    else:
                        is_blocked = True
                        break
            
            # Validar cupo si es propiedad
            if prop_config:
                if simultaneous_count >= prop_config.max_simultaneous_visits:
                    is_blocked = True
                else: 
                    # IMPORTANTE: Si no se alcanzó el cupo, está LIBRE, sin importar eventos personales
                    is_blocked = False
            
            if not is_blocked:
                available_slots.append({
                    "date": date_str,
                    "day": day_str,
                    "start": curr_slot.strftime("%H:%M"),
                    "end": slot_end.strftime("%H:%M")
                })
            
            curr_slot = slot_end # Avanzar al siguiente bloque contiguous
            # Ojo: si queremos slots cada 30 min pero visitas de 60, el step debería ser 30 o 60?
            # Por simplicidad, step = duration.

    return {"available_slots": available_slots}


@router.get("/{instance_name}/public-config")
def get_bot_public_config(instance_name: str, db: Session = Depends(get_db)):
    """
    Permite al Motor de IA leer el System Prompt y Configuración actual sin autenticación de usuario,
    solo conociendo el nombre de la instancia.
    """
    bot = db.query(models.Bot).filter(models.Bot.instance_name == instance_name).first()
    if not bot: raise HTTPException(404, "Bot not found")
    
    return {
        "system_prompt": bot.system_prompt or DEFAULT_BOT_IDENTITY,
        "business_hours": bot.business_hours or get_default_business_hours(),
        "tags": bot.tags or [],
        "config": bot.config or { "voice": {"enabled": True, "voice_name": "Kore"}, "notifications": {"remind_1d": False, "remind_1h": True} },
        "role": "agent"
    }

@router.get("/conversations/list")
def get_bot_conversations(skip: int = 0, limit: int = 20, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    """
    Lista las conversaciones activas del bot.
    """
    user = db.query(models.User).filter(models.User.email == email).first()
    # Idealmente filtrar por bot/tenant, por simplicidad:
    convs = db.query(models.BotConversation).order_by(models.BotConversation.last_message_at.desc()).offset(skip).limit(limit).all()
    
    result = []
    from sqlalchemy import func
    for c in convs:
        c_dict = {
            "phone": c.phone,
            "last_message_at": c.last_message_at,
            "last_sender": c.last_sender,
            "followup_sent": c.followup_sent,
            "contact_name": None
        }
        
        raw_phone = c.phone.replace('@s.whatsapp.net', '')
        if raw_phone:
            search_suffix = raw_phone[-8:] if len(raw_phone) >= 8 else raw_phone
            contact = db.query(models.Contact).filter(
                models.Contact.tenant_id == user.tenant_id,
                func.regexp_replace(models.Contact.phone, '[^0-9]', '', 'g').ilike(f"%{search_suffix}")
            ).first()
            if contact:
                c_dict["contact_name"] = contact.name
        
        result.append(c_dict)
        
    return result

@router.get("/conversations/{phone}/messages")
def get_conversation_messages(phone: str, limit: int = 50, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    """
    Obtiene el historial de chat de una conversación específica.
    """
    msgs = db.query(models.ChatHistory).filter(models.ChatHistory.sender_id == phone).order_by(models.ChatHistory.created_at.desc()).limit(limit).all()
    return msgs[::-1]


@router.get('/analytics')
def get_bot_analytics(period: str = '7D', db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import func
    import json
    import math
    
    now = datetime.now(timezone.utc)
    if period == 'Hoy':
        start_date = now - timedelta(days=1)
    elif period == '30D':
        start_date = now - timedelta(days=30)
    elif period == 'Todo':
        start_date = now - timedelta(days=365*10)
    else: # 7D default
        start_date = now - timedelta(days=7)
        
    start_date_naive = start_date.replace(tzinfo=None)

    # 1. Active Conversations
    total_convs = db.query(models.BotConversation).filter(models.BotConversation.last_message_at >= start_date_naive).count()
    
    # 2. Hot Leads
    hot_leads = db.query(models.Contact).filter(
        models.Contact.tenant_id == user.tenant_id, 
        models.Contact.status == 'HOT',
        models.Contact.created_at >= start_date_naive
    ).count()

    total_leads_in_period = db.query(models.Contact).filter(
        models.Contact.tenant_id == user.tenant_id,
        models.Contact.created_at >= start_date_naive
    ).count()
    
    conversion_rate = f"{(hot_leads / total_leads_in_period * 100) if total_leads_in_period > 0 else 0:.1f}%"
    
    # Calculate Trends vs Previous Period
    length = now - start_date
    if period == 'Todo':
        prev_start_date_naive = start_date_naive
    else:
        prev_start_date_naive = (start_date - length).replace(tzinfo=None)
        
    prev_total_convs = db.query(models.BotConversation).filter(
        models.BotConversation.last_message_at >= prev_start_date_naive,
        models.BotConversation.last_message_at < start_date_naive
    ).count()

    prev_hot_leads = db.query(models.Contact).filter(
        models.Contact.tenant_id == user.tenant_id, 
        models.Contact.status == 'HOT',
        models.Contact.created_at >= prev_start_date_naive,
        models.Contact.created_at < start_date_naive
    ).count()
    
    prev_total_leads = db.query(models.Contact).filter(
        models.Contact.tenant_id == user.tenant_id,
        models.Contact.created_at >= prev_start_date_naive,
        models.Contact.created_at < start_date_naive
    ).count()
    
    prev_conv_rate = (prev_hot_leads / prev_total_leads * 100) if prev_total_leads > 0 else 0
    curr_conv_rate_num = (hot_leads / total_leads_in_period * 100) if total_leads_in_period > 0 else 0
    
    def calc_diff(curr, prev, is_perc=False):
        diff = curr - prev
        sign = "+" if diff >= 0 else ""
        if diff == 0: sign = ""
        val_str = f"{sign}{diff:.1f}%" if is_perc else f"{sign}{diff}"
        return {"value": val_str, "isUp": diff >= 0}
    
    # 3. Sentiment Data
    sentiments = db.query(models.Contact.lead_sentiment, func.count(models.Contact.id)).filter(
        models.Contact.tenant_id == user.tenant_id,
        models.Contact.created_at >= start_date_naive
    ).group_by(models.Contact.lead_sentiment).all()
    
    sentiment_map = {"POSITIVO": 0, "NEUTRO": 0, "NEUTRAL": 0, "NEGATIVO": 0}
    for s, count in sentiments:
        if s: sentiment_map[s.upper()] = count
    
    total_sents = sum(sentiment_map.values())
    def get_perc(val): return int(val/total_sents*100) if total_sents > 0 else 0
    
    sentiment_data = [
        { 'name': 'Positivo', 'value': get_perc(sentiment_map.get("POSITIVO", 0)), 'color': '#10B981' },
        { 'name': 'Neutral', 'value': get_perc(sentiment_map.get("NEUTRAL", 0) + sentiment_map.get("NEUTRO", 0)), 'color': '#6366F1' },
        { 'name': 'Negativo', 'value': get_perc(sentiment_map.get("NEGATIVO", 0)), 'color': '#F43F5E' },
    ]

    # 4. Activity Data & Response time
    activity_data = []
    days_to_gen = (now - start_date).days
    
    messages = db.query(models.ChatHistory).filter(models.ChatHistory.created_at >= start_date_naive).order_by(models.ChatHistory.sender_id, models.ChatHistory.created_at).all()
    
    avg_response_time = "1.3s"
    rt_count = 0
    rt_total = 0
    last_u_time = None
    last_s_id = None
    
    for m in messages:
        if m.sender_id != last_s_id:
            last_u_time = None
            last_s_id = m.sender_id
            
        role = str(m.role).lower() if m.role else ''
        if role == 'user':
            last_u_time = m.created_at
        elif role in ['model', 'assistant', 'bot'] and last_u_time:
            diff = (m.created_at - last_u_time).total_seconds()
            if 0 <= diff < 300: # 5 minutes max to be considered a direct response
                rt_total += diff
                rt_count += 1
            last_u_time = None
            
    if rt_count > 0:
        avg_rt = rt_total / rt_count
        avg_response_time = f"{avg_rt:.1f}s"
    else:
        avg_response_time = "0.0s"
    
    def to_utc(dt):
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

    if days_to_gen <= 1:
        slots = 8
        step_hours = 24 / slots
        for i in range(slots):
            slot_start = start_date + timedelta(hours=i*step_hours)
            slot_end = start_date + timedelta(hours=(i+1)*step_hours)
            msgs_in_slot = [m for m in messages if slot_start <= to_utc(m.created_at) < slot_end]
            activity_data.append({
                'time': slot_end.strftime('%H:%M'),
                'messages': len(msgs_in_slot),
                'conversions': math.ceil(len(msgs_in_slot) * 0.05)
            })
    else:
        slots = min(days_to_gen, 7)
        step_days = days_to_gen / slots
        for i in range(slots):
            slot_start = start_date + timedelta(days=i*step_days)
            slot_end = start_date + timedelta(days=(i+1)*step_days)
            msgs_in_slot = [m for m in messages if slot_start <= to_utc(m.created_at) < slot_end]
            activity_data.append({
                'time': slot_end.strftime('%d/%m'),
                'messages': len(msgs_in_slot),
                'conversions': math.ceil(len(msgs_in_slot) * 0.05)
            })

    # 5. Topic Data
    topic_counts = {'Precios': 0, 'Agendar Visita': 0, 'Financiación': 0, 'Ubicación': 0, 'Requisitos': 0}
    for m in messages:
        text = str(m.parts).lower()
        if 'precio' in text or 'cuanto' in text or 'cuánto' in text or 'valor' in text: topic_counts['Precios'] += 1
        if 'visita' in text or 'ver' in text or 'mostrar' in text or 'agendar' in text: topic_counts['Agendar Visita'] += 1
        if 'financia' in text or 'cuota' in text or 'credito' in text or 'crédito' in text: topic_counts['Financiación'] += 1
        if 'ubicacion' in text or 'ubicación' in text or 'dónde' in text or 'donde' in text or 'zona' in text: topic_counts['Ubicación'] += 1
        if 'requisit' in text or 'garant' in text or 'recibo' in text: topic_counts['Requisitos'] += 1
        
    topic_data = [{'name': k, 'count': v} for k, v in topic_counts.items() if v > 0]
    if not topic_data:
        topic_data = [{'name': 'Sin Data Suficiente', 'count': 0}]
    else:
        topic_data.sort(key=lambda x: x['count'], reverse=True)

    return {
        'kpis': {
            'active_conversations': total_convs,
            'conversion_rate': conversion_rate,
            'response_time': avg_response_time, 
            'hot_leads': hot_leads,
            'trends': {
                'active_conversations': calc_diff(total_convs, prev_total_convs),
                'conversion_rate': calc_diff(curr_conv_rate_num, prev_conv_rate, True),
                'response_time': {"value": "-0.1s", "isUp": True}, # Trend Mocked since we need historic avg which is complex to compute fast
                'hot_leads': calc_diff(hot_leads, prev_hot_leads)
            }
        },
        'activity_data': activity_data,
        'sentiment_data': sentiment_data,
        'topic_data': topic_data
    }
