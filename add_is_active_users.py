from database import engine, SessionLocal
from sqlalchemy import text

def run():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE;"))
            conn.commit()
            print("Successfully added 'is_active' column to users table.")
        except Exception as e:
            print("Ignored error (maybe column exists already):", e)

if __name__ == "__main__":
    run()
