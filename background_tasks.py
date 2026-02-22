import logging
from database import SessionLocal
import models
from routers import ai_service

logger = logging.getLogger("urbanocrm.background")

def background_sync_property_ai(property_id: int):
    """
    Ejecuta el pipeline de IA en background.
    Instancia una nueva sesión DB para evitar problemas si 
    FastAPI cierra la sesión del Request principal antes de correr esto.
    """
    db = SessionLocal()
    try:
        property = db.query(models.Property).filter(models.Property.id == property_id).first()
        if not property:
            logger.warning(f"[Background Sync] Propiedad {property_id} no encontrada.")
            return
            
        context_str = ai_service.generate_property_context_string(property)
        property.search_content = context_str
        vector = ai_service.get_embedding(context_str)
        if vector:
            property.embedding_descripcion = vector
            db.commit()
            logger.info(f"[Background Sync] Éxito para Propiedad {property_id}.")
        else:
            logger.warning(f"[Background Sync] No se pudo obtener vector para {property_id}")
            
    except Exception as e:
        logger.error(f"[Background Sync] Error procesando propiedad {property_id}: {e}")
        db.rollback()
    finally:
        db.close()
