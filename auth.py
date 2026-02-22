import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from settings import settings
from fastapi.security import OAuth2PasswordBearer
import bcrypt

# --- FIX DE COMPATIBILIDAD BCRYPT / PASSLIB ---
# Las versiones nuevas de bcrypt (4.0.0+) eliminaron el atributo '__about__'
# que passlib intenta leer, causando un AttributeError.
# Este bloque inyecta el atributo faltante para que passlib funcione.

if not hasattr(bcrypt, '__about__'):
    try:
        from collections import namedtuple
        Version = namedtuple('Version', ['__version__'])
        bcrypt.__about__ = Version(bcrypt.__version__)
    except Exception:
        # Fallback simple si lo anterior falla
        class MockAbout:
            __version__ = bcrypt.__version__
        bcrypt.__about__ = MockAbout()
# ----------------------------------------------

# Configuración JWT
SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes

# Configuración de Hashing de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Esquema de seguridad OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def verify_password(plain_password, hashed_password):
    """Verifica si la contraseña plana coincide con el hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """Genera un hash seguro para la contraseña."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Crea un token JWT de acceso."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user_email(token: str = Depends(oauth2_scheme)):
    """
    Decodifica el token y extrae el email (sub).
    Nota: Para obtener el objeto usuario completo, se debe consultar la DB
    usando este email en el endpoint correspondiente.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        return email
    except JWTError as e:
        # Debugging 401 errors
        try:
            with open("debug_auth_error.txt", "a") as f:
                f.write(f"[{datetime.now()}] JWT Error: {str(e)} | Token: {token[:20]}... | Secret: {SECRET_KEY[:5]}...\n")
        except:
             pass
        raise credentials_exception