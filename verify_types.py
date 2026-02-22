import requests
import xml.etree.ElementTree as ET
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL").replace("postgres://", "postgresql://")
engine = create_engine(db_url)

# 1. Get XML Data
print("Fetching XML...")
url = "https://feeds.adinco.net/18618/ar_adinco.xml"
response = requests.get(url)
response.encoding = 'utf-8'
root = ET.fromstring(response.text)

xml_types = {}
for ad in root.findall('ad'):
    aid = ad.findtext('id').strip()
    ptype = ad.findtext('property_type')
    xml_types[aid] = ptype

print(f"Loaded {len(xml_types)} properties from XML.")

# 2. Check DB
print("Checking DB mismatches...")
with engine.connect() as conn:
    result = conn.execute(text("SELECT id, code, type FROM properties WHERE code LIKE 'IMP-%'"))
    
    mismatches = 0
    total = 0
    updates = []
    
    for row in result:
        total += 1
        db_id = row.id
        code = row.code # IMP-XXXX
        current_type = row.type
        
        xml_id = code.replace("IMP-", "")
        
        if xml_id in xml_types:
            xml_type = xml_types[xml_id]
            
            # Normalize for comparison if needed, but assuming exact match first
            if current_type != xml_type:
                print(f"Mismatch {code}: XML={xml_type} vs DB={current_type}")
                mismatches += 1
                updates.append({'id': db_id, 'type': xml_type})
        else:
            print(f"Warning: {code} not found in XML")

    print(f"Total checked: {total}")
    print(f"Mismatches found: {mismatches}")
    
    # 3. Apply Fixes
    if updates:
        print(f"Applying {len(updates)} updates...")
        for u in updates:
            conn.execute(text("UPDATE properties SET type = :type WHERE id = :id"), u)
        conn.commit()
        print("Done.")
    else:
        print("No updates needed.")
