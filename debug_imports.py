
import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug_import")

logger.info("Starting import debug...")

routers = [
    "auth", "users", "properties", "developments", "contacts", "branches", 
    "config", "media", "google", "calendars", "team", "import_data", 
    "whatsapp", "monitoring", "ai_matching", "ai_service", "bots", "opportunities"
]

for r in routers:
    logger.info(f"Importing router: {r}")
    try:
        exec(f"from routers import {r}")
        logger.info(f"Successfully imported {r}")
    except Exception as e:
        logger.error(f"Failed to import {r}: {e}")

logger.info("Finished import debug.")
