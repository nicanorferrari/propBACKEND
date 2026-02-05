
from sqlalchemy import Column, Integer, String, Boolean, Text, Float, ForeignKey, JSON, DateTime
from sqlalchemy.orm import relationship
from database import Base
import datetime
from pgvector.sqlalchemy import Vector

class Tenant(Base):
    __tablename__ = "tenants"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    domain = Column(String)

class User(Base):
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True} 

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    tax_id = Column(String, nullable=True)
    job_title = Column(String, nullable=True)
    
    phone_mobile = Column(String, nullable=True)
    phone_office = Column(String, nullable=True)
    has_whatsapp = Column(Boolean, default=False)
    email_alt = Column(String, nullable=True)
    
    role = Column(String, default="AGENT")
    avatar_url = Column(Text, nullable=True)
    language = Column(String, default="es")
    timezone = Column(String, default="America/Argentina/Buenos_Aires")
    
    social_instagram = Column(String, nullable=True)
    social_linkedin = Column(String, nullable=True)
    social_facebook = Column(String, nullable=True)
    social_web = Column(String, nullable=True)
    
    email_signature = Column(Text, nullable=True)
    monitoring_token = Column(String, unique=True, index=True, nullable=True)
    
    # Campos para jornada laboral y descansos
    work_schedule = Column(JSON, nullable=True)
    break_config = Column(JSON, nullable=True)

    google_access_token = Column(String, nullable=True)
    google_refresh_token = Column(String, nullable=True)
    google_token_expiry = Column(String, nullable=True)
    google_email = Column(String, nullable=True) 
    
    outlook_access_token = Column(String, nullable=True)
    outlook_refresh_token = Column(String, nullable=True)
    outlook_token_expiry = Column(String, nullable=True)
    outlook_email = Column(String, nullable=True)

class MonitoringLog(Base):
    __tablename__ = "monitoring_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    app_name = Column(String)
    window_title = Column(String)
    url = Column(String, nullable=True)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    duration_seconds = Column(Integer)
    is_idle = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

class Branch(Base):
    __tablename__ = "branches"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    address = Column(String)
    phone = Column(String, nullable=True)
    active = Column(Boolean, default=True)

class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String) # CREATE, UPDATE, DELETE, LOGIN
    entity_type = Column(String) # PROPERTY, CONTACT, EVENT, DEVELOPMENT
    entity_id = Column(Integer, nullable=True)
    description = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    title = Column(String)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    type = Column(String, default="VISIT") 
    color = Column(String, nullable=True)
    source = Column(String, default="CRM")
    agent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    contact_id = Column(Integer, nullable=True)
    contact_name = Column(String, nullable=True)
    property_id = Column(Integer, ForeignKey("properties.id", ondelete="CASCADE"), nullable=True)
    property_address = Column(String, nullable=True)
    status = Column(String, default="PENDING")
    description = Column(Text, nullable=True)
    google_event_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))
    
    # Reminder fields
    is_reminder = Column(Boolean, default=False)
    email_alert = Column(Boolean, default=False)
    alert_sent = Column(Boolean, default=False)
    alert_24h_sent = Column(Boolean, default=False)

class ContactInteraction(Base):
    __tablename__ = "contact_interactions"
    id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey("contacts.id"))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    type = Column(String) # CALL, WHATSAPP, EMAIL, MEETING, OTHER
    notes = Column(Text, nullable=True)
    date = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))

class Contact(Base):
    __tablename__ = "contacts"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    name = Column(String)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    status = Column(String, default="WARM") # COLD, WARM, HOT
    type = Column(String, default="CLIENT") # CLIENT, OWNER, BROKER
    source = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    last_contact_date = Column(DateTime(timezone=True), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc))

class Property(Base):
    __tablename__ = "properties"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    code = Column(String, unique=True, index=True)
    title = Column(String)
    address = Column(String)
    city = Column(String)
    neighborhood = Column(String, nullable=True)
    price = Column(Float)
    currency = Column(String, default="USD")
    type = Column(String) # Apartment, House, PH, etc.
    operation = Column(String) # Sale, Rent, Temporary
    
    # Specs
    rooms = Column(Integer, default=1)
    bedrooms = Column(Integer, default=0)
    bathrooms = Column(Integer, default=0)
    toilettes = Column(Integer, default=0)
    suites = Column(Integer, default=0)
    has_walk_in_closet = Column(Boolean, default=False)
    garages_total = Column(Integer, default=0)
    garages_covered = Column(Integer, default=0)
    garages_uncovered = Column(Integer, default=0)
    age_type = Column(String, default="New") # New, Years
    age_years = Column(Integer, default=0)
    
    # Dynamic/Building fields
    floor = Column(String, nullable=True)
    unit_number = Column(String, nullable=True)
    units_per_floor = Column(Integer, default=0)
    building_floors = Column(Integer, default=0)
    elevators = Column(Integer, default=0)
    levels = Column(Integer, default=1)
    zoning = Column(String, nullable=True)
    fot = Column(String, nullable=True)
    fos = Column(String, nullable=True)
    
    condition = Column(String, default="Bueno")
    disposition = Column(String, default="Frente")
    orientation = Column(String, default="N")
    
    surface_covered = Column(Float, default=0)
    surface_semicovered = Column(Float, default=0)
    surface_uncovered = Column(Float, default=0)
    surface = Column(Float, default=0) # Total surface
    
    attributes = Column(JSON, default=[])
    image = Column(Text, nullable=True)
    thumbnail_url = Column(Text, nullable=True)
    gallery = Column(JSON, default=[])
    lat = Column(Float, default=0.0)
    lng = Column(Float, default=0.0)
    hide_exact_location = Column(Boolean, default=False)
    description = Column(Text, nullable=True)
    virtual_tour_url = Column(String, nullable=True)
    video_url = Column(String, nullable=True)
    
    # IA Columns (768 dimensions for Gemini Text Embedding 004)
    embedding_descripcion = Column(Vector(768), nullable=True)
    prop_metadata = Column("metadata", JSON, default={})
    search_content = Column(Text, nullable=True)
    
    # Management
    owner_name = Column(String, nullable=True)
    owner_id = Column(Integer, nullable=True)
    assigned_agent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_agent = relationship("User", foreign_keys=[assigned_agent_id])
    key_location = Column(String, nullable=True)
    commission = Column(String, nullable=True) # commissionValue from frontend
    internal_notes = Column(Text, nullable=True)
    
    # Visitas Config
    visit_duration = Column(Integer, default=30) # en minutos
    max_simultaneous_visits = Column(Integer, default=1)
    visit_availability = Column(JSON, default={}) # { "Mon": {"enabled": true, "start": "09:00", "end": "18:00"}, ... }

    # Diffusion
    is_shared = Column(Boolean, default=False)
    sharing_commission = Column(Float, default=0.0)
    sharing_notes = Column(Text, nullable=True)
    sharing_type = Column(String, default="NO_SHARE")
    transaction_requirements = Column(Text, nullable=True)
    
    status = Column(String, default="Active")

class Development(Base):
    __tablename__ = "developments"
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True)
    code = Column(String, unique=True, index=True)
    name = Column(String)
    address = Column(String)
    delivery_date = Column(String)
    status = Column(String, default="CONSTRUCTION")
    description = Column(Text, nullable=True)
    amenities = Column(JSON, default=[])
    lat = Column(Float)
    lng = Column(Float)
    thumbnail_url = Column(Text, nullable=True)
    gallery = Column(JSON, default=[])
    is_shared = Column(Boolean, default=False)
    sharing_commission = Column(Float, default=0.0)
    sharing_notes = Column(Text, nullable=True)
    virtual_tour_url = Column(String, nullable=True)
    video_url = Column(String, nullable=True)
    
    # IA Column
    embedding_proyecto = Column(Vector(768), nullable=True)

class Typology(Base):
    __tablename__ = "typologies"
    id = Column(Integer, primary_key=True, index=True)
    development_id = Column(Integer, ForeignKey("developments.id"))
    name = Column(String)
    surface = Column(Float)
    rooms = Column(Integer)
    bathrooms = Column(Integer)
    base_price = Column(Float)
    description = Column(Text, nullable=True)

class Unit(Base):
    __tablename__ = "units"
    id = Column(Integer, primary_key=True, index=True)
    development_id = Column(Integer, ForeignKey("developments.id"))
    typology_id = Column(Integer, ForeignKey("typologies.id"), nullable=True)
    unit_name = Column(String)
    floor = Column(Integer)
    price = Column(Float)
    status = Column(String, default="AVAILABLE")

class AgencyConfig(Base):
    __tablename__ = "agency_configs"
    id = Column(Integer, primary_key=True, index=True)
    agency_name = Column(String, nullable=True)
    logo_url = Column(Text, nullable=True)
    watermark_url = Column(Text, nullable=True)
    watermark_settings = Column(JSON, nullable=True) 
    integrations = Column(JSON, default={})
    web_builder_config = Column(JSON, default={})
    
    # Global Integrations
    google_access_token = Column(String, nullable=True)
    google_refresh_token = Column(String, nullable=True)
    google_token_expiry = Column(String, nullable=True)
    google_email = Column(String, nullable=True) 
    
    outlook_access_token = Column(String, nullable=True)
    outlook_refresh_token = Column(String, nullable=True)
    outlook_token_expiry = Column(String, nullable=True)
    outlook_email = Column(String, nullable=True)

class RegistrationToken(Base):
    __tablename__ = "registration_tokens"
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True)
    email = Column(String)
    role = Column(String)
    is_used = Column(Boolean, default=False)

class SystemConfig(Base):
    __tablename__ = "system_configs"
    key = Column(String, primary_key=True)
    value = Column(String)

class Bot(Base):
    __tablename__ = "bots"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    platform = Column(String, default="whatsapp")
    instance_name = Column(String, unique=True, index=True)
    system_prompt = Column(Text, nullable=True)
    business_hours = Column(JSON, default={})
    tags = Column(JSON, default=[])
    config = Column(JSON, default={})
    status = Column(String, default="disconnected")
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class WhatsappBuffer(Base):
    __tablename__ = "whatsapp_buffer"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(String(255), nullable=False)
    message_content = Column(Text, nullable=True)
    status = Column(String(50), default='pending')
    received_at = Column(DateTime, default=datetime.datetime.utcnow)
    instance = Column(String(250), nullable=True)
    file_url = Column(String(250), nullable=True)



class BotConversation(Base):
    __tablename__ = "bot_conversations"
    phone = Column(String, primary_key=True) # remote_jid
    last_message_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_sender = Column(String) # 'user', 'bot'
    followup_sent = Column(Boolean, default=False)

class ChatHistory(Base):
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(String, index=True)
    role = Column(String)
    parts = Column(JSON)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
