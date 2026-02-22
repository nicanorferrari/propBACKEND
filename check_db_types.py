import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL").replace("postgres://", "postgresql://")
engine = create_engine(db_url)

print("Estado actual de Tipos de Propiedad (en inglés):")
with engine.connect() as conn:
    result = conn.execute(text("SELECT type, COUNT(*) FROM properties GROUP BY type"))
    for row in result:
        print(f"{row[0]}: {row[1]}")
