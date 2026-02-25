import os
print("DEBUG: database.py - starting imports")
import re
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from settings import settings

# 1. Obtener la URL base
raw_url = settings.database_url

# 2. Limpieza robusta de la URL para forzar driver síncrono (psycopg2)
if raw_url.startswith("postgres"):
    # Reemplaza protocolos como postgres:// o postgresql:// por postgresql+psycopg2://
    DATABASE_URL = re.sub(r'^.*?://', 'postgresql+psycopg2://', raw_url)
else:
    DATABASE_URL = raw_url

# 3. Crear el motor síncrono
# Agregamos pool_size y max_overflow para manejar mejor las conexiones en la nube
engine = create_engine(
    DATABASE_URL, 
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={"connect_timeout": 10} if not DATABASE_URL.startswith("sqlite") else {}
)

# 4. Configuración de sesiones
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 5. Base para modelos
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()