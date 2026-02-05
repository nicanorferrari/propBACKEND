from database import SessionLocal
from models import CalendarEvent
from sqlalchemy import text

def fix_sources():
    db = SessionLocal()
    try:
        # Check for nulls
        null_events = db.query(CalendarEvent).filter(CalendarEvent.source == None).all()
        print(f"Found {len(null_events)} events with NULL source.")
        
        if null_events:
            # Update them
            db.execute(text("UPDATE calendar_events SET source = 'CRM' WHERE source IS NULL"))
            db.commit()
            print("Fixed NULL sources.")
        else:
            print("No fix needed.")
            
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    fix_sources()
