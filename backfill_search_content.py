
import sys
import os

# Add current directory to path to allow imports
sys.path.append(os.getcwd())

from dotenv import load_dotenv
import os
# Load local backend .env (where API_KEY and DB_URL are now)
load_dotenv()

from sqlalchemy.orm import Session
from database import SessionLocal
import models
from routers import ai_service
import time

def backfill():
    print("Starting backfill process...")
    db = SessionLocal()
    try:
        props = db.query(models.Property).all()
        print(f"Found {len(props)} properties.")
        
        count = 0
        for prop in props:
            count += 1
            print(f"[{count}/{len(props)}] Processing Property ID {prop.id}: {prop.address}")
            
            # 1. Generate new context (includes Address now)
            try:
                context_str = ai_service.generate_property_context_string(prop)
                
                # 2. Save to search_content
                prop.search_content = context_str
                
                # 3. Regenerate Embedding (task_type=retrieval_document)
                vector = ai_service.get_embedding(context_str, task_type="retrieval_document")
                
                if vector:
                    prop.embedding_descripcion = vector
                    print("   -> Context and Embedding updated.")
                else:
                    print("   -> Context updated. Embedding failed (API error?).")
                    
                # Commit every item or batch to save progress
                db.commit()
                time.sleep(0.5) 
                
            except Exception as e:
                print(f"   -> Error processing property {prop.id}: {e}")
                
        print("Backfill completed successfully.")
        
    except Exception as e:
        print(f"Critical Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    backfill()
