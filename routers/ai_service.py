
import os
import google.generativeai as genai
from typing import List
import logging

logger = logging.getLogger("urbanocrm.ai_service")

# Configurar API Key de Gemini
API_KEY = os.getenv("API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)

def generate_property_context_string(prop) -> str:
    """
    Genera el string de contexto para una propiedad según requerimiento.
    """
    neighborhood = prop.neighborhood or prop.city or "Sin ubicación"
    p_type = prop.type or "Propiedad"
    rooms = prop.rooms or 0
    bedrooms = prop.bedrooms or 0
    currency = prop.currency or "USD"
    price = f"{prop.price:,.0f}" if prop.price else "Consultar"
    description = prop.description or ""
    features = ", ".join(prop.attributes) if prop.attributes else "Ninguna especificada"
    address = prop.address or ""
    
    return f"Propiedad en {neighborhood}. Dirección: {address}. Tipo: {p_type}. {rooms} ambientes, {bedrooms} dormitorios. Precio: {currency} {price}. Descripción: {description}. Características: {features}."

def generate_development_context_string(dev) -> str:
    """
    Genera el string de contexto para un emprendimiento según requerimiento.
    """
    status_map = {"CONSTRUCTION": "En construcción", "PRE_SALE": "Pozo", "DELIVERED": "Finalizado"}
    status = status_map.get(dev.status, dev.status)
    typologies = ", ".join([t.name for t in dev.typologies]) if hasattr(dev, 'typologies') and dev.typologies else "A confirmar"
    amenities = ", ".join(dev.amenities) if dev.amenities else "No especificados"
    
    return f"Emprendimiento {dev.name} en {dev.address}. Estado: {status}. Tipologías disponibles: {typologies}. Amenities: {amenities}. Descripción: {dev.description or ''}."

def get_embedding(text: str, task_type: str = "retrieval_query") -> List[float]:
    """
    Llama a Gemini API para obtener el vector de embedding 004.
    """
    if not API_KEY or not text:
        return None
    
    try:
        result = genai.embed_content(
            model="models/gemini-embedding-001",
            content=text,
            task_type=task_type,
            output_dimensionality=768
        )
        return result['embedding']
    except Exception as e:
        logger.error(f"AI ERROR: Failed to get embedding from Gemini: {e}")
        return None
