
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any
from database import get_db, SessionLocal
from . import ai_service
import models
import logging

router = APIRouter()
logger = logging.getLogger("urbanocrm.ai")

async def run_backfill():
    with SessionLocal() as db:
        # Props
        props = db.query(models.Property).filter(models.Property.embedding_descripcion == None).all()
        for p in props:
            ctx = ai_service.generate_property_context_string(p)
            vec = ai_service.get_embedding(ctx)
            if vec:
                p.embedding_descripcion = vec
                db.commit()
        # Devs
        devs = db.query(models.Development).filter(models.Development.embedding_proyecto == None).all()
        for d in devs:
            ctx = ai_service.generate_development_context_string(d)
            vec = ai_service.get_embedding(ctx)
            if vec:
                d.embedding_proyecto = vec
                db.commit()
    logger.info("AI: Manual backfill completed.")

@router.post("/backfill")
async def trigger_backfill(background_tasks: BackgroundTasks):
    """Fuerza la generación de embeddings para todos los registros que no tengan."""
    background_tasks.add_task(run_backfill)
    return {"status": "processing", "message": "Backfill task started in background."}

@router.get("/match")
def match_lead_interest(query: str = Query(..., min_length=3), db: Session = Depends(get_db)):
    """
    Búsqueda semántica usando similitud de coseno en pgvector.
    """
    query_vector = ai_service.get_embedding(query)
    if not query_vector:
        raise HTTPException(500, "Error generating query embedding")

    # Búsqueda en Propiedades (Similaridad de Coseno: 1 - Distancia)
    props_sql = text("""
        SELECT id, address, price, currency, thumbnail_url, 'PROPERTY' as type, code, city, neighborhood,
        operation, description,
        (1 - (embedding_descripcion <=> :vec)) as score
        FROM properties
        WHERE embedding_descripcion IS NOT NULL
        ORDER BY score DESC
        LIMIT 6
    """)
    
    # Búsqueda en Emprendimientos
    devs_sql = text("""
        SELECT id, name as address, 0 as price, 'USD' as currency, thumbnail_url, 'DEVELOPMENT' as type, code, address as city, '' as neighborhood,
        'Sale' as operation, description,
        (1 - (embedding_proyecto <=> :vec)) as score
        FROM developments
        WHERE embedding_proyecto IS NOT NULL
        ORDER BY score DESC
        LIMIT 6
    """)

    props_results = db.execute(props_sql, {"vec": str(query_vector)}).fetchall()
    devs_results = db.execute(devs_sql, {"vec": str(query_vector)}).fetchall()

    combined = []
    for r in props_results: combined.append(dict(r._mapping))
    for r in devs_results: combined.append(dict(r._mapping))
    
    # Ordenar por score descendente y tomar los mejores
    final_matches = sorted(combined, key=lambda x: x['score'], reverse=True)[:6]

    return {
        "query": query,
        "matches": final_matches
    }

@router.post("/send-recommendation")
async def send_recommendation_whatsapp(
    contact_id: int, 
    entity_id: int, 
    entity_type: str, 
    db: Session = Depends(get_db)
):
    contact = db.query(models.Contact).filter(models.Contact.id == contact_id).first()
    if not contact: raise HTTPException(404, "Contacto no encontrado")
    
    msg = ""
    if entity_type == 'PROPERTY':
        prop = db.query(models.Property).filter(models.Property.id == entity_id).first()
        msg = f"Hola {contact.name}, basado en tu interés, creo que esta propiedad es ideal: {prop.address}. Valor: {prop.currency} {prop.price}. Ver ficha: https://urbanocrm.com/p/{prop.code}"
    else:
        dev = db.query(models.Development).filter(models.Development.id == entity_id).first()
        msg = f"Hola {contact.name}, este nuevo proyecto en {dev.address} ({dev.name}) coincide con lo que buscas. Ver info: https://urbanocrm.com/d/{dev.code}"

    return {"status": "ok", "message_queued": msg}
