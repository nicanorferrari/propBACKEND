
import bcrypt
from database import SessionLocal
import models

def reset_broker_password():
    email = "broker@inmobiliaria.com"
    password = "password123"
    
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            print(f"User {email} not found")
            return
        
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        user.hashed_password = hashed.decode('utf-8')
        
        db.commit()
        print(f"Password reset success for {email} to 'password123'")
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    reset_broker_password()
