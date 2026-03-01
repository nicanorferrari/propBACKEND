import os
print("DEBUG: main.py - imports 1")
from fastapi import FastAPI, BackgroundTasks
print("DEBUG: main.py - imports 2")
from fastapi.middleware.cors import CORSMiddleware
print("DEBUG: main.py - imports 3")
from contextlib import asynccontextmanager
print("DEBUG: main.py - imports 4")
import logging
print("DEBUG: main.py - imports 5")
import asyncio
print("DEBUG: main.py - imports 6")
from dotenv import load_dotenv
print("DEBUG: main.py - imports 7")
load_dotenv()
print("DEBUG: main.py - imports 8")
from sqlalchemy import text
print("DEBUG: main.py - imports 9")
import uuid
print("DEBUG: main.py - imports 10")
from database import engine, Base, SessionLocal
import models

from socket_manager import sio, send_notification
import socketio

# Importación de Routers
from routers import auth, users, properties, developments, contacts, branches, config, media, google, calendars, team, import_data, whatsapp, monitoring, ai_matching, ai_service, bots, opportunities, feed

import logging
from logging.handlers import RotatingFileHandler

# Configuración de Logging
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

# Handler para archivo general del Backend
backend_handler = RotatingFileHandler("backend.log", maxBytes=5*1024*1024, backupCount=5)
backend_handler.setFormatter(logging.Formatter(LOG_FORMAT))

# Handler específico para errores críticos
error_handler = RotatingFileHandler("critical_errors.log", maxBytes=2*1024*1024, backupCount=3)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(logging.Formatter(LOG_FORMAT))

# Configurar logger raíz del proyecto
logger = logging.getLogger("urbanocrm")
logger.addHandler(backend_handler)
logger.addHandler(error_handler)

# Handler específico para el Chatbot
chatbot_logger = logging.getLogger("urbanocrm.bots")
chatbot_handler = RotatingFileHandler("chatbot.log", maxBytes=5*1024*1024, backupCount=5)
chatbot_handler.setFormatter(logging.Formatter(LOG_FORMAT))
chatbot_logger.addHandler(chatbot_handler)

logger.info("Logging system initialized: backend.log, chatbot.log, critical_errors.log")

async def backfill_embeddings():
    """Tarea para rellenar embeddings faltantes en el arranque."""
    await asyncio.sleep(5) # Esperar a que la DB esté lista
    logger.info("AI: Starting backfill check for null embeddings...")
    with SessionLocal() as db:
        # Propiedades
        props = db.query(models.Property).filter(models.Property.embedding_descripcion == None).all()
        if props:
            logger.info(f"AI: Found {len(props)} properties without embeddings. Syncing...")
            for p in props:
                ctx = ai_service.generate_property_context_string(p)
                vec = ai_service.get_embedding(ctx)
                if vec:
                    p.embedding_descripcion = vec
                    db.commit()
        
        # Emprendimientos
        devs = db.query(models.Development).filter(models.Development.embedding_proyecto == None).all()
        if devs:
            logger.info(f"AI: Found {len(devs)} developments without embeddings. Syncing...")
            for d in devs:
                ctx = ai_service.generate_development_context_string(d)
                vec = ai_service.get_embedding(ctx)
                if vec:
                    d.embedding_proyecto = vec
                    db.commit()
    logger.info("AI: Backfill check completed.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    def db_setup():
        with SessionLocal() as db:
            try:
                # 1. Extensiones (solo si no están)
                db.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                db.commit()
            except Exception as e:
                logger.warning(f"Could not enable pgvector: {e}")
                db.rollback()

            # 2. Verificar si necesitamos correr migraciones pesadas
            # Si ya tenemos la tabla system_configs, asumimos que la estructura base está ok
            check_table = db.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'system_configs');")).scalar()
            
            if not check_table:
                logger.info("Database: Running base model creation...")
                Base.metadata.create_all(bind=engine)
            
            # 3. Migraciones incrementales rápidas (con IF NOT EXISTS)
            migration_commands = [
                "ALTER TABLE properties ADD COLUMN IF NOT EXISTS embedding_descripcion vector(768);",
                "ALTER TABLE developments ADD COLUMN IF NOT EXISTS embedding_proyecto vector(768);",
                "ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS alert_24h_sent BOOLEAN DEFAULT FALSE;",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS monitoring_token VARCHAR UNIQUE;",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS work_schedule JSONB;",
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS break_config JSONB;",
                "ALTER TABLE developments ADD COLUMN IF NOT EXISTS code VARCHAR UNIQUE;",
                "ALTER TABLE properties ADD COLUMN IF NOT EXISTS code VARCHAR UNIQUE;",
                "CREATE TABLE IF NOT EXISTS system_configs (key VARCHAR PRIMARY KEY, value TEXT);",
                "ALTER TABLE agency_configs ADD COLUMN IF NOT EXISTS web_builder_config JSONB;",
                "ALTER TABLE properties ADD COLUMN IF NOT EXISTS virtual_tour_url VARCHAR;",
                "ALTER TABLE properties ADD COLUMN IF NOT EXISTS video_url VARCHAR;",
                "ALTER TABLE developments ADD COLUMN IF NOT EXISTS virtual_tour_url VARCHAR;",
                "ALTER TABLE developments ADD COLUMN IF NOT EXISTS video_url VARCHAR;",
                "ALTER TABLE properties ADD COLUMN IF NOT EXISTS published_on_portals JSONB DEFAULT '[]'::jsonb;",
                "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS lead_score INTEGER DEFAULT 50;",
                "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS lead_sentiment VARCHAR DEFAULT 'NEUTRAL';",
                "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS drip_campaign_active BOOLEAN DEFAULT FALSE;",
                "ALTER TABLE contacts ADD COLUMN IF NOT EXISTS embedding_preferences vector(768);",
                "CREATE TABLE IF NOT EXISTS bots (id SERIAL PRIMARY KEY, user_id INTEGER, platform VARCHAR, instance_name VARCHAR, system_prompt TEXT, business_hours JSONB, tags JSONB, config JSONB, status VARCHAR, is_active BOOLEAN, created_at TIMESTAMP, updated_at TIMESTAMP);",
            ]
            
            for cmd in migration_commands:
                try:
                    # Solo ejecutamos si el comando contiene ADD COLUMN y la columna no existe (opcional, IF NOT EXISTS ya lo hace)
                    db.execute(text(cmd))
                    db.commit()
                except Exception as e:
                    db.rollback()

            # 4. Generar datos faltantes (Solo si es necesario)
            try:
                # User Tokens
                db.execute(text("""
                    UPDATE users SET monitoring_token = 'URB-MON-' || substring(md5(random()::text) from 1 for 12)
                    WHERE monitoring_token IS NULL;
                """))
                
                # Property codes
                db.execute(text("""
                    UPDATE properties SET code = 'URB-P' || upper(substring(md5(random()::text) from 1 for 5))
                    WHERE code IS NULL;
                """))

                # Dev codes
                db.execute(text("""
                    UPDATE developments SET code = 'URB-D' || upper(substring(md5(random()::text) from 1 for 5))
                    WHERE code IS NULL;
                """))

                db.commit()
            except Exception as e:
                logger.error(f"Error data sync: {e}")
                db.rollback()
                    
    await asyncio.to_thread(db_setup)
    yield

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from rate_limiter import limiter

app = FastAPI(title="UrbanoCRM AI-SaaS", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", # Vite Dev Server
        "http://localhost:3000", # Alternative React Port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        os.getenv("FRONTEND_URL", "https://app.inmobiliarias.ai") # Production override
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Autenticación"])
app.include_router(users.router, prefix="/api/users", tags=["Usuarios"])
app.include_router(team.router, prefix="/api/team", tags=["Equipo"])
app.include_router(properties.router, prefix="/api/properties", tags=["Propiedades"])
app.include_router(developments.router, prefix="/api/developments", tags=["Emprendimientos"])
app.include_router(contacts.router, prefix="/api/contacts", tags=["Contactos"])
app.include_router(branches.router, prefix="/api/branches", tags=["Sucursales"])
app.include_router(config.router, prefix="/api", tags=["Configuración"])
app.include_router(media.router, prefix="/api/media", tags=["Multimedia"])
app.include_router(google.router, prefix="/api/integrations", tags=["Google Integration"])
app.include_router(calendars.router, prefix="/api/calendar", tags=["Agenda"])
app.include_router(import_data.router, prefix="/api/import", tags=["Importación"])
app.include_router(whatsapp.router, prefix="/api/whatsapp", tags=["WhatsApp"])
app.include_router(monitoring.router, prefix="/api/monitoring", tags=["Monitoreo"])
app.include_router(ai_matching.router, prefix="/api/ai-matching", tags=["AI Intelligence"])
app.include_router(bots.router, prefix="/api/bots", tags=["Bot Mastery"])
app.include_router(opportunities.router, prefix="/api/opportunities", tags=["Oportunidades"])
app.include_router(feed.router, prefix="/api/feeds", tags=["Sindicación Portales"])

@app.get("/")
async def root():
    return {"status": "ok", "message": "UrbanoCRM SaaS AI Engine Active"}

# Dev route for testing socket 
@app.get("/test-socket/{user_id}")
async def test_socket(user_id: str):
    import datetime
    import uuid
    data = {
        "id": "test-" + str(uuid.uuid4())[:8],
        "type": "SYSTEM",
        "title": "Prueba de Servidor",
        "description": "Esto es una notificación de prueba en tiempo real.",
        "time": datetime.datetime.now().isoformat(),
        "read": False,
        "link": "/"
    }
    await send_notification(user_id, data)
    return {"status": "sent", "user": user_id, "data": data}

# Wrap FastAPI application with Socket.IO ASGI application
app = socketio.ASGIApp(sio, other_asgi_app=app)
