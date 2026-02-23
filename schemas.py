
from pydantic import BaseModel, Field, EmailStr, field_validator, ConfigDict
from typing import Optional, List, Any, Dict, Union
from datetime import datetime, timezone

class MonitoringLogCreate(BaseModel):
    app_name: str
    window_title: str
    url: Optional[str] = None
    start_time: datetime
    end_time: datetime
    duration_seconds: int
    is_idle: bool = False

class EmailSendRequest(BaseModel):
    to_email: EmailStr
    subject: str
    body: str
    contact_id: int

class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str

class ActivityLogResponse(BaseModel):
    id: int
    action: str
    entity_type: str
    description: str
    timestamp: datetime

    @field_validator('timestamp', mode='before')
    @classmethod
    def ensure_timezone(cls, v):
        if isinstance(v, datetime) and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    model_config = ConfigDict(from_attributes=True)

class EventBase(BaseModel):
    title: str
    start_time: datetime
    end_time: datetime
    type: Optional[str] = "VISIT"
    color: Optional[str] = None
    source: Optional[str] = None
    contact_id: Optional[int] = None
    contact_name: Optional[str] = None
    property_id: Optional[int] = None
    property_address: Optional[str] = None
    development_id: Optional[int] = None
    development_name: Optional[str] = None
    status: str = "PENDING"
    description: Optional[str] = None
    notification_options: Optional[Dict[str, Any]] = {}
    is_reminder: bool = False
    email_alert: bool = False

class EventCreate(EventBase):
    pass

class EventResponse(EventBase):
    id: int
    agent_id: Optional[int] = None
    alert_sent: bool = False
    alert_24h_sent: bool = False
    model_config = ConfigDict(from_attributes=True)

class BranchBase(BaseModel):
    name: str
    address: str
    phone: Optional[str] = None
    active: bool = True

class BranchCreate(BranchBase):
    pass

class BranchResponse(BranchBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class AgencyConfigUpdate(BaseModel):
    agency_name: Optional[str] = None
    logo_url: Optional[str] = None
    watermark_url: Optional[str] = None
    watermark_settings: Optional[Any] = None
    integrations: Optional[Any] = None
    web_builder_config: Optional[Any] = None

class InvitationRequest(BaseModel):
    email: EmailStr
    role: str

class UserRegistration(BaseModel):
    token: str
    first_name: str
    last_name: str
    password: str
    phone_mobile: Optional[str] = None

class ContactBase(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = "WARM"
    type: Optional[str] = "CLIENT"
    source: Optional[str] = None
    lead_score: Optional[int] = 50
    lead_sentiment: Optional[str] = "NEUTRAL"
    drip_campaign_active: Optional[bool] = False
    notes: Optional[str] = None
    last_contact_date: Optional[datetime] = None

class ContactCreate(ContactBase):
    pass

class InteractionBase(BaseModel):
    type: str  # CALL, WHATSAPP, EMAIL, MEETING, OTHER
    notes: Optional[str] = None
    date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class InteractionCreate(InteractionBase):
    contact_id: Optional[int] = None # Optional in body because it's usually in the URL path

class InteractionResponse(InteractionBase):
    id: int
    contact_id: int
    user_id: Optional[int] = None
    created_at: datetime
    
    @field_validator('date', 'created_at', mode='before')
    @classmethod
    def ensure_timezone(cls, v):
        if isinstance(v, datetime) and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v

    model_config = ConfigDict(from_attributes=True)

class ContactResponse(ContactBase):
    id: int
    created_at: datetime
    created_by_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)

class UserProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    tax_id: Optional[str] = None
    job_title: Optional[str] = None
    phone_mobile: Optional[str] = None
    phone_office: Optional[str] = None
    has_whatsapp: Optional[bool] = False
    email_alt: Optional[str] = None
    avatar_url: Optional[str] = None
    social_instagram: Optional[str] = None
    social_linkedin: Optional[str] = None
    social_facebook: Optional[str] = None
    social_web: Optional[str] = None
    language: Optional[str] = None
    timezone: Optional[str] = None
    email_signature: Optional[str] = None
    work_schedule: Optional[Dict[str, Any]] = None
    break_config: Optional[Dict[str, Any]] = None
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None

class UserResponse(UserProfileUpdate):
    id: int
    email: str
    role: str
    avatar_url: Optional[str] = None
    monitoring_token: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    phone_mobile: Optional[str] = None

class PresignedUrlRequest(BaseModel):
    filename: str
    content_type: str

class ConfigUpdate(BaseModel):
    value: str

class PropertyCreate(BaseModel):
    title: str
    address: str
    city: str
    neighborhood: Optional[str] = None
    price: float = 0.0
    currency: str = "USD"
    type: str
    operation: str
    
    # Specs
    rooms: int = 1
    bedrooms: int = 0
    bathrooms: int = 0
    toilettes: int = 0
    suites: int = 0
    has_walk_in_closet: bool = False
    garages_total: int = 0
    garages_covered: int = 0
    garages_uncovered: int = 0
    age_type: str = "New"
    age_years: int = 0
    
    # Building fields
    floor: Optional[str] = None
    unit_number: Optional[str] = None
    units_per_floor: int = 0
    building_floors: int = 0
    elevators: int = 0
    levels: int = 1
    zoning: Optional[str] = None
    fot: Optional[str] = None
    fos: Optional[str] = None
    
    condition: str = "Bueno"
    disposition: str = "Frente"
    orientation: str = "N"
    
    surface_covered: float = 0.0
    surface_semicovered: float = 0.0
    surface_uncovered: float = 0.0
    surface: float = 0.0
    
    attributes: Optional[Any] = []
    image: Optional[str] = None
    thumbnail_url: Optional[str] = None
    gallery: Optional[List[Union[Dict[str, str], str]]] = []
    lat: float = 0.0
    lng: float = 0.0
    hide_exact_location: bool = False
    description: Optional[str] = None
    virtual_tour_url: Optional[str] = None
    video_url: Optional[str] = None
    published_on_portals: Optional[List[str]] = []
    
    # Management
    owner_name: Optional[str] = None
    owner_id: Optional[int] = None
    assigned_agent_id: Optional[int] = None
    key_location: Optional[str] = None
    commission: Optional[str] = None
    internal_notes: Optional[str] = None
    
    # Visitas Config
    visit_duration: int = 30
    max_simultaneous_visits: int = 1
    visit_availability: Optional[Dict[str, Any]] = {}

    # Diffusion
    is_shared: bool = False
    sharing_commission: float = 0.0
    sharing_notes: Optional[str] = None
    sharing_type: Optional[str] = "NO_SHARE"
    transaction_requirements: Optional[str] = None

class PropertyResponse(PropertyCreate):
    id: int
    assigned_agent_id: Optional[int] = None
    code: Optional[str] = "N/A"
    status: Optional[str] = "Active"
    model_config = ConfigDict(from_attributes=True)

class TypologyBase(BaseModel):
    name: str
    surface: float
    rooms: int
    bathrooms: int
    base_price: float
    description: Optional[str] = None

class TypologyResponse(TypologyBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class UnitBase(BaseModel):
    unit_name: str
    floor: int
    price: float
    status: str = "AVAILABLE"
    typology_name: Optional[str] = None

class UnitResponse(UnitBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class DevelopmentBase(BaseModel):
    name: str
    address: str
    delivery_date: str
    status: str = "CONSTRUCTION"
    description: Optional[str] = None
    amenities: Optional[Any] = []
    lat: float
    lng: float
    thumbnail_url: Optional[str] = None
    gallery: Optional[List[Union[Dict[str, str], str]]] = []
    is_shared: bool = False
    sharing_commission: float = 0.0
    sharing_notes: Optional[str] = None
    virtual_tour_url: Optional[str] = None
    video_url: Optional[str] = None

class DevelopmentCreate(DevelopmentBase):
    typologies: List[TypologyBase] = []
    units: List[UnitBase] = []

class DevelopmentResponse(DevelopmentBase):
    id: int
    code: Optional[str] = "N/A"
    typologies: List[TypologyResponse] = []
    units: List[UnitResponse] = []
    model_config = ConfigDict(from_attributes=True)

# Bot Schemas
class BotBase(BaseModel):
    platform: str
    system_prompt: Optional[str] = None
    business_hours: Optional[Dict[str, Any]] = {}
    tags: Optional[List[str]] = []
    config: Optional[Dict[str, Any]] = {}
    is_active: bool = False

class BotCreate(BotBase):
    pass

class BotResponse(BotBase):
    id: int
    status: str
    instance_name: Optional[str] = None
    qrCode: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class BotConnectRequest(BaseModel):
    platform: str

# Sales Pipeline Schemas
class PipelineStageBase(BaseModel):
    name: str
    order: int = 0
    color: Optional[str] = None

class PipelineStageCreate(PipelineStageBase):
    pass

class PipelineStageResponse(PipelineStageBase):
    id: int
    pipeline_id: int
    model_config = ConfigDict(from_attributes=True)

class PipelineBase(BaseModel):
    name: str
    is_active: bool = True

class PipelineCreate(PipelineBase):
    stages: Optional[List[PipelineStageCreate]] = []

class PipelineResponse(PipelineBase):
    id: int
    stages: List[PipelineStageResponse]
    model_config = ConfigDict(from_attributes=True)

class DealBase(BaseModel):
    title: str
    value: float = 0.0
    currency: str = "USD"
    pipeline_stage_id: int
    property_id: Optional[int] = None
    contact_id: Optional[int] = None
    assigned_agent_id: Optional[int] = None
    priority: str = "MEDIUM"
    status: str = "OPEN"
    requirements: Optional[str] = None
    close_date: Optional[datetime] = None

class DealCreate(DealBase):
    pass

class DealUpdate(BaseModel):
    title: Optional[str] = None
    value: Optional[float] = None
    currency: Optional[str] = None
    pipeline_stage_id: Optional[int] = None
    property_id: Optional[int] = None
    contact_id: Optional[int] = None
    assigned_agent_id: Optional[int] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    requirements: Optional[str] = None
    close_date: Optional[datetime] = None

class DealCommentResponse(BaseModel):
    id: int
    content: str
    user_id: Optional[int] = None
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)

class DealHistoryResponse(BaseModel):
    id: int
    from_stage_id: Optional[int] = None
    to_stage_id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class DealResponse(DealBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    property: Optional[PropertyResponse] = None
    contact: Optional[ContactResponse] = None
    agent: Optional[UserResponse] = None
    comments: List[DealCommentResponse] = []
    history: List[DealHistoryResponse] = []
    model_config = ConfigDict(from_attributes=True)
