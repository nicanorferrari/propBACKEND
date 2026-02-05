
import json
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import models # Assumes models.py is in the same directory or accessible

DATABASE_URL = "postgresql://postgres:c1dd6c9314aa474b2ca4@179.43.119.138:54322/propcrm"
INPUT_FILE = "scraped_properties.json"
TENANT_ID = 4 # Inmobiliaria Siglo XXI

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def import_data():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found.")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        properties_data = json.load(f)

    db = SessionLocal()
    print(f"Starting import of {len(properties_data)} properties...")

    count = 0
    for p in properties_data:
        try:
            # Check if property already exists by code
            existing = db.query(models.Property).filter(models.Property.code == p['code'], models.Property.tenant_id == TENANT_ID).first()
            
            # Map metadata
            metadata = {
                "source_agency": p.get("source_agency"),
                "commission_shared": p.get("commission_shared"),
                "contact_email": p.get("contact_email"),
                "contact_phone": p.get("contact_phone"),
                "contact_hours": p.get("contact_hours")
            }

            if existing:
                # Update
                existing.address = p.get('address', existing.address)
                existing.price = p.get('price', existing.price)
                existing.currency = p.get('currency', existing.currency)
                existing.description = p.get('description', existing.description)
                existing.gallery = p.get('gallery', existing.gallery)
                existing.image = p.get('image', existing.image)
                existing.type = p.get('type', existing.type)
                existing.operation = p.get('operation', existing.operation)
                existing.surface = p.get('surface', existing.surface)
                existing.rooms = p.get('rooms', existing.rooms)
                existing.bedrooms = p.get('bedrooms', existing.bedrooms)
                existing.bathrooms = p.get('bathrooms', existing.bathrooms)
                existing.prop_metadata = metadata
                print(f"Updated: {p['code']}")
            else:
                # Create NEW
                new_prop = models.Property(
                    tenant_id=TENANT_ID,
                    code=p.get('code'),
                    title=f"{p.get('type', 'Propiedad')} en {p.get('address', 'Rosario')}",
                    address=p.get('address'),
                    city="Rosario",
                    price=p.get('price', 0),
                    currency=p.get('currency', 'USD'),
                    type=p.get('type', 'Departamento'),
                    operation=p.get('operation', 'Venta'),
                    surface=p.get('surface', 0),
                    rooms=p.get('rooms', 0),
                    bedrooms=p.get('bedrooms', 0),
                    bathrooms=p.get('bathrooms', 0),
                    description=p.get('description', ''),
                    image=p.get('image'),
                    gallery=p.get('gallery', []),
                    prop_metadata=metadata
                )
                db.add(new_prop)
                print(f"Created: {p['code']}")
            
            count += 1
            if count % 10 == 0:
                db.commit()
                print(f"Progress: {count} processed...")

        except Exception as e:
            print(f"Error importing {p.get('code', 'Unknown')}: {e}")
            db.rollback()

    db.commit()
    db.close()
    print(f"Import finished. Total properties: {count}")

if __name__ == "__main__":
    import_data()
