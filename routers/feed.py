from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from sqlalchemy import cast, String
import xml.etree.ElementTree as ET
import datetime

import models
from database import get_db

router = APIRouter()

@router.get("/{tenant_id}/{portal_name}.xml")
def generate_portal_xml_feed(tenant_id: int, portal_name: str, db: Session = Depends(get_db)):
    """
    Genera un XML Feed estandarizado para la sincronización con un portal específico.
    inmobiliarios como Zonaprop, Argenprop, MercadoLibre, etc.
    Funciona recopilando todas las propiedades activas de la agencia (tenant) especificada.
    """
    
    query = db.query(models.Property).filter(
        models.Property.tenant_id == tenant_id,
        models.Property.status != "Deleted"
    )
    
    # Filtrar solo si especifican un portal válido (ej. mercadolibre, zonaprop)
    if portal_name.lower() != "all":
        query = query.filter(cast(models.Property.published_on_portals, String).ilike(f'%"{portal_name}"%'))
        
    properties = query.all()

    # Raíz del XML (Estándar tipo TokkoBroker / Inmuebles24 / genérico)
    root = ET.Element("properties")

    for prop in properties:
        prop_xml = ET.SubElement(root, "property")
        
        ET.SubElement(prop_xml, "id").text = str(prop.id)
        ET.SubElement(prop_xml, "reference_code").text = prop.code or ""
        ET.SubElement(prop_xml, "title").text = prop.title or ""
        ET.SubElement(prop_xml, "description").text = prop.description or ""
        
        # Operación y Tipo
        ET.SubElement(prop_xml, "type").text = str(prop.type)
        ET.SubElement(prop_xml, "operation").text = str(prop.operation)
        
        # Precios
        prices_xml = ET.SubElement(prop_xml, "prices")
        price_xml = ET.SubElement(prices_xml, "price")
        ET.SubElement(price_xml, "currency").text = str(prop.currency)
        ET.SubElement(price_xml, "amount").text = str(prop.price)
        
        # Ubicación
        loc_xml = ET.SubElement(prop_xml, "location")
        ET.SubElement(loc_xml, "address").text = str(prop.address)
        ET.SubElement(loc_xml, "city").text = str(prop.city)
        ET.SubElement(loc_xml, "latitude").text = str(prop.lat)
        ET.SubElement(loc_xml, "longitude").text = str(prop.lng)
        
        # Superficies y características
        features_xml = ET.SubElement(prop_xml, "features")
        ET.SubElement(features_xml, "surface_total").text = str(prop.surface or 0)
        ET.SubElement(features_xml, "surface_covered").text = str(prop.surface_covered or 0)
        ET.SubElement(features_xml, "bedrooms").text = str(prop.bedrooms or 0)
        ET.SubElement(features_xml, "bathrooms").text = str(prop.bathrooms or 0)
        ET.SubElement(features_xml, "garages").text = str(prop.garages_total or prop.garages or 0)
        ET.SubElement(features_xml, "rooms").text = str(prop.rooms or 0)
        ET.SubElement(features_xml, "condition").text = str(prop.condition or "")

        # Imágenes
        pictures_xml = ET.SubElement(prop_xml, "pictures")
        # Foto principal
        if prop.image:
            pic_xml = ET.SubElement(pictures_xml, "picture")
            ET.SubElement(pic_xml, "picture_url").text = prop.image
            ET.SubElement(pic_xml, "is_cover").text = "true"
        
        # Galería
        if prop.gallery and isinstance(prop.gallery, list):
            for idx, g in enumerate(prop.gallery):
                pic_xml = ET.SubElement(pictures_xml, "picture")
                if isinstance(g, dict) and "full" in g:
                    ET.SubElement(pic_xml, "picture_url").text = g["full"]
                elif isinstance(g, str):
                    ET.SubElement(pic_xml, "picture_url").text = g
                ET.SubElement(pic_xml, "is_cover").text = "false"
        
        ET.SubElement(prop_xml, "agency").text = "UrbanoCRM"

    xml_str = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    
    return Response(content=xml_str, media_type="application/xml")
