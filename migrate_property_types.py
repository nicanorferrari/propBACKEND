import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL").replace("postgres://", "postgresql://")
engine = create_engine(db_url)

TYPE_MAP = {
    "Departamento": "Apartment",
    "Casa": "House",
    "Tipo Casa PH": "PH",
    "Terreno": "Land",
    "Local": "Commercial",
    "Oficina": "Office",
    "Cochera": "Garage",
    "Galpón": "Warehouse"
}

print("Iniciando migración de Tipos de Propiedad (Spanish -> English)...")

with engine.connect() as conn:
    total_updated = 0
    for es, en in TYPE_MAP.items():
        print(f"Migrando '{es}' -> '{en}'...")
        result = conn.execute(
            text("UPDATE properties SET type = :en WHERE type = :es"),
            {"en": en, "es": es}
        )
        count = result.rowcount
        print(f"  -> {count} registros actualizados.")
        total_updated += count
    
    conn.commit()

print(f"Migración completada. Total: {total_updated}")
