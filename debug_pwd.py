
import bcrypt
password = "p4ssw0rdC4M88rrrTTpp"
print(f"Length: {len(password)}")
try:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    print("Bcrypt direct success")
except Exception as e:
    print(f"Bcrypt direct error: {e}")

from auth import get_password_hash
try:
    hashed = get_password_hash(password)
    print("Passlib success")
except Exception as e:
    print(f"Passlib error: {e}")
