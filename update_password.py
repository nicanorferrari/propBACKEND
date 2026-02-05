
import sys
import os
import bcrypt
from database import SessionLocal
import models

def update_password():
    email = "manager@inmobiliaria.com"
    password = "p4ssw0rdC4M88rrrTTpp"
    
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            print(f"Error: User {email} not found")
            return
        
        # Use bcrypt directly
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        # Decode to string for storage
        user.hashed_password = hashed.decode('utf-8')
        
        db.commit()
        print(f"Successfully updated password (directly via bcrypt) for {email}")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    update_password()
