import sys
import os
import random
import datetime

# Add the backend dir to path so we can import models and database
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
import models
from sqlalchemy import text

db = SessionLocal()

try:
    print("Deleting contacts imported from Google...")
    imported_contacts = db.query(models.Contact).filter(models.Contact.source == "GOOGLE_IMPORT").all()
    imported_ids = [c.id for c in imported_contacts]
    
    if imported_ids:
        # Avoid FK constraints errors, remove their interactions first if needed
        db.query(models.ContactInteraction).filter(models.ContactInteraction.contact_id.in_(imported_ids)).delete(synchronize_session=False)
        db.query(models.CalendarEvent).filter(models.CalendarEvent.contact_id.in_(imported_ids)).update({"contact_id": None}, synchronize_session=False)
        db.query(models.Deal).filter(models.Deal.contact_id.in_(imported_ids)).update({"contact_id": None}, synchronize_session=False)
        db.query(models.Contact).filter(models.Contact.id.in_(imported_ids)).delete(synchronize_session=False)
        db.commit()
        print(f"Deleted {len(imported_ids)} Google contacts.")
    else:
        print("No Google contacts found.")

    # Get a user/tenant to bind these to
    user = db.query(models.User).filter(models.User.email == "broker@inmobiliaria.com").first()
    if not user:
        user = db.query(models.User).first()
        
    tenant_id = user.tenant_id if user else None
    user_id = user.id if user else None

    # Let's create some dummy 'owner' contacts
    mock_owners_data = [
        {"name": "Roberto Fernandez", "phone": "5491112345601", "email": "roberto.fer@test.com"},
        {"name": "Marta Linares", "phone": "5491112345602", "email": "mlinares89@test.com"},
        {"name": "Carlos Gomez", "phone": "5491112345603", "email": "gomez.car@test.com"},
        {"name": "Lucía Santoro", "phone": "5491112345604", "email": "santo.lucia@test.com"},
    ]

    print("Creating new mock contacts...")
    created_contacts = []
    for d in mock_owners_data:
        c = models.Contact(
            name=d["name"],
            phone=d["phone"],
            email=d["email"],
            type="OWNER",
            source="MANUAL_MOCK",
            status="WARM",
            tenant_id=tenant_id,
            created_by_id=user_id,
            last_contact_date=datetime.datetime.now(datetime.timezone.utc)
        )
        db.add(c)
        created_contacts.append(c)
        
    db.commit()
    for c in created_contacts:
        db.refresh(c)

    print(f"Created {len(created_contacts)} mock contacts.")

    # Fetch some properties and assign them these new contacts as owners
    properties = db.query(models.Property).all()
    if properties:
        for i, c in enumerate(created_contacts):
            # assign 1 property per contact if available
            if i < len(properties):
                p = properties[i]
                p.owner_id = c.id
                p.owner_name = c.name
                
        db.commit()
        print(f"Linked {min(len(created_contacts), len(properties))} properties to the new owners.")
    else:
        print("No properties found to link.")

    print("Done!")

except Exception as e:
    print(f"An error occurred: {e}")
    db.rollback()
finally:
    db.close()
