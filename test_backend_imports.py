import sys
import os
print("Importing os/sys done")
import logging
print("Importing logging done")
import httpx
print("Importing httpx done")
from fastapi import FastAPI
print("Importing FastAPI done")
try:
    import sqlalchemy
    print(f"Importing sqlalchemy done version={sqlalchemy.__version__}")
except Exception as e:
    print(f"Error importing sqlalchemy: {e}")
try:
    from database import engine, SessionLocal
    print("Importing database (engine/session) done")
except Exception as e:
    print(f"Error importing database: {e}")
try:
    import models
    print("Importing models done")
except Exception as e:
    print(f"Error importing models: {e}")
print("ALL DONE")
