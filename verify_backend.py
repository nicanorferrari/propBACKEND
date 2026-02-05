
import sys
import os
from datetime import datetime

# Add backend to path
sys.path.append(os.path.abspath("c:/Users/Public/Documents/Inmobiliarias.ai/backend"))

try:
    import models
    import schemas
    print("✅ Check 1: Imports successful")
except Exception as e:
    print(f"❌ Check 1 Failed: {e}")
    sys.exit(1)

try:
    # Test Interaction Model Instantiation (Mock)
    interaction = models.ContactInteraction(
        contact_id=1,
        type="CALL",
        notes="Test note",
        date=datetime.now()
    )
    print("✅ Check 2: ContactInteraction model instantiated")
except Exception as e:
    print(f"❌ Check 2 Failed: {e}")

try:
    # Test Schema Instantiation tttt
    schema = schemas.InteractionCreate(
        contact_id=1,
        type="EMAIL",
        notes="Test Schema",
        date=datetime.now()
    )
    print(f"✅ Check 3: InteractionCreate schema valid: {schema}")
except Exception as e:
    print(f"❌ Check 3 Failed: {e}")

print("Backend Verification Complete.")
