import uuid
import logging
import io
import httpx
import re
import xml.etree.ElementTree as ET
from fastapi import APIRouter, Depends, Body, HTTPException
from sqlalchemy.orm import Session
from typing import List, Any, Dict, Set
from database import get_db
import models
from storage import minio_client, MINIO_BUCKET, MINIO_PUBLIC_DOMAIN, get_minio_client
from PIL import Image

import csv
import codecs
from fastapi import APIRouter, Depends, Body, HTTPException, UploadFile, File
from auth import get_current_user_email

router = APIRouter()
logger = logging.getLogger("urbanocrm.import")

@router.post("/contacts/csv")
async def import_contacts_csv(file: UploadFile = File(...), db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    
    try:
        csvReader = csv.DictReader(codecs.iterdecode(file.file, 'utf-8'))
        
        imported = 0
        skipped = 0
        errors = 0
        
        for row in csvReader:
            try:
                # Normalize keys (strip spaces, lowercase)
                row = {k.strip().lower(): v for k, v in row.items() if k}
                
                # Check required Name
                name = row.get('nombre') or row.get('name') or row.get('full name')
                if not name:
                    errors += 1
                    continue
                
                # Extract other fields
                contact_email = row.get('email') or row.get('correo') or row.get('mail')
                phone = row.get('telefono') or row.get('phone') or row.get('celular') or row.get('mobile')
                
                # Duplicate Check
                exists = False
                if contact_email:
                    if db.query(models.Contact).filter(models.Contact.tenant_id == user.tenant_id, models.Contact.email == contact_email).first():
                        exists = True
                if not exists and phone:
                     if db.query(models.Contact).filter(models.Contact.tenant_id == user.tenant_id, models.Contact.phone == phone).first():
                        exists = True
                
                if exists:
                    skipped += 1
                    continue
                
                # Create
                new_contact = models.Contact(
                    tenant_id=user.tenant_id,
                    created_by_id=user.id,
                    name=name,
                    email=contact_email,
                    phone=phone,
                    type="CLIENT", # Default
                    status="WARM", # Default
                    source="CSV_IMPORT",
                    notes=row.get('notas') or row.get('notes') or ""
                )
                db.add(new_contact)
                imported += 1
                
            except Exception as e:
                logger.error(f"Error importing row: {e}")
                errors += 1
                
        db.commit()
        return {"status": "success", "imported": imported, "skipped": skipped, "errors": errors}
        
    except Exception as e:
        db.rollback()
        logger.error(f"CSV Import Error: {e}")
        raise HTTPException(status_code=400, detail="Invalid CSV format or encoding")

# Mapeo de servicios de Adinco a keys del CRM
ADINCO_SERVICES_MAP = {
    "Agua Corriente": "water",
    "Cloacas": "sewer",
    "Gas": "gas",
    "Gas Natural": "gas",
    "Electricidad": "electricity",
    "Pavimento": "pavement",
    "Internet": "internet",
    "Videocable": "cable",
    "Cable": "cable",
    "Teléfono": "telephone",
    "Seguridad": "security_24h"
}

# Mapeo de ambientes y otros datos
ADINCO_OTHER_MAP = {
    "Balcón": "balcony",
    "Cocina": "kitchen",
    "Comedor": "dining_room",
    "Living": "living_room",
    "Lavadero": "laundry",
    "Terraza": "terrace",
    "Toilette": "toilette",
    "Vestidor": "dressing_room",
    "Escritorio": "office",
    "Pileta": "pool",
    "Parrilla": "grill",
    "SUM": "sum",
    "Gimnasio": "gym",
    "Solarium": "solarium",
    "Mascotas": "pets",
    "Hidromasaje": "jacuzzi",
    "Aire Acondicionado": "ac",
    "Calefacción": "heating",
    "Jardín": "terrace" # Simplificado
}

async def scrape_unit_ids_from_dev(dev_url: str) -> Set[str]:
    """
    Visita la URL del emprendimiento y extrae los IDs de las unidades relacionadas
    usando Regex (basado en la lógica PHP proporcionada).
    """
    if not dev_url: return set()
    try:
        async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
            resp = await client.get(dev_url, follow_redirects=True)
            if resp.status_code != 200: return set()
            html = resp.text
            
            # Buscamos IDs en el HTML: usualmente están en clases property-code o enlaces
            # Regex 1: Enlaces de unidades
            links = re.findall(r'class="emprendimiento__unidad-link"[^>]*>\s*<a[^>]+href=".*?([0-9]+)', html, re.I)
            # Regex 2: Códigos de propiedad directos
            codes = re.findall(r'class="property-code"[^>]*>\s*.*?-\s*([0-9]+)', html, re.S)
            
            return set(links + codes)
    except Exception as e:
        logger.error(f"Error scraping dev units from {dev_url}: {e}")
        return set()

async def ingest_adinco_image(url: str) -> Dict[str, str]:
    """
    Limpia la URL (quita extra_large_) y sube variantes a MinIO.
    """
    if not url: return None
    # Limpiamos la URL según requerimiento
    clean_url = url.replace("extra_large_", "")
    
    try:
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            resp = await client.get(clean_url, follow_redirects=True)
            if resp.status_code != 200: return None
            img_data = resp.content
            
        base_img = Image.open(io.BytesIO(img_data))
        if base_img.mode in ("RGBA", "P"): base_img = base_img.convert("RGB")
            
        variants = {}
        resolutions = [("full", None), ("mid", 800), ("thumb", 300)]
        base_id = str(uuid.uuid4())
        
        for name, width in resolutions:
            output = io.BytesIO()
            curr_img = base_img.copy()
            if width and curr_img.size[0] > width:
                ratio = width / float(curr_img.size[0])
                curr_img = curr_img.resize((width, int(float(curr_img.size[1]) * ratio)), Image.Resampling.LANCZOS)
            
            curr_img.save(output, format="JPEG", quality=85 if name != "full" else 92, optimize=True)
            file_size = output.tell()
            output.seek(0)
            object_name = f"uploads/{base_id}_{name}.jpg"
            
            minio_client.put_object(MINIO_BUCKET, object_name, data=output, length=file_size, content_type="image/jpeg")
            variants[name] = f"https://{MINIO_PUBLIC_DOMAIN}/{MINIO_BUCKET}/{object_name}"
            
        return variants
    except Exception: return None

@router.post("/adinco/{agency_id}")
async def import_adinco_xml(agency_id: str, db: Session = Depends(get_db)):
    # URL corregida según especificación del usuario
    xml_url = f"https://feeds.adinco.net/{agency_id}/ar_adinco.xml"
    
    try:
        async with httpx.AsyncClient(verify=False, timeout=60.0) as client:
            resp = await client.get(xml_url)
            if resp.status_code != 200:
                raise HTTPException(status_code=404, detail=f"No se pudo descargar el XML de Adinco desde {xml_url}")
            xml_content = resp.text
            
        root = ET.fromstring(xml_content)
        ads = root.findall('ad')
        
        # PASO 1: Identificar todos los IDs que pertenecen a emprendimientos
        all_linked_unit_ids = set()
        dev_ads = [ad for ad in ads if ad.findtext('property_type') == 'Emprendimiento']
        
        for ad in dev_ads:
            url = ad.findtext('url')
            if url:
                unit_ids = await scrape_unit_ids_from_dev(url)
                all_linked_unit_ids.update(unit_ids)

        added_p, added_d = 0, 0
        
        # PASO 2: Procesar Ads
        for ad in ads:
            ext_id = ad.findtext('id').strip()
            p_type = ad.findtext('property_type')
            
            # Si el ID está en la lista de unidades vinculadas, lo saltamos (se importa como de pozo o se omite)
            if ext_id in all_linked_unit_ids and p_type != 'Emprendimiento':
                logger.info(f"Omitiendo unidad vinculada: {ext_id}")
                continue

            # Extraer Amenities
            amenities = set()
            services_node = ad.find('services')
            if services_node is not None:
                for s in services_node.findall('service'):
                    val = ADINCO_SERVICES_MAP.get(s.text)
                    if val: amenities.add(val)
            
            other_node = ad.find('other_data')
            if other_node is not None:
                for o in other_node.findall('other'):
                    val = ADINCO_OTHER_MAP.get(o.text)
                    if val: amenities.add(val)

            # Extraer Imágenes
            gallery = []
            pic_nodes = ad.find('pictures')
            if pic_nodes is not None:
                for p in pic_nodes.findall('picture')[:10]: # Max 10 por velocidad
                    url = p.findtext('picture_url')
                    if url:
                        variants = await ingest_adinco_image(url)
                        if variants: gallery.append(variants)
            
            cover = gallery[0] if gallery else None
            
            if p_type == 'Emprendimiento':
                new_dev = models.Development(
                    name=ad.findtext('content_title') or ad.findtext('title'),
                    address=ad.findtext('address'),
                    delivery_date=ad.findtext('year') or "A Confirmar",
                    description=ad.findtext('content'),
                    amenities=list(amenities),
                    lat=float(ad.findtext('latitude') or 0),
                    lng=float(ad.findtext('longitude') or 0),
                    thumbnail_url=cover["thumb"] if cover else None,
                    gallery=gallery,
                    status="CONSTRUCTION"
                )
                db.add(new_dev); added_d += 1
            else:
                price_node = ad.find('price')
                new_prop = models.Property(
                    code=f"IMP-{ext_id}",
                    title=ad.findtext('content_title') or ad.findtext('title'),
                    address=ad.findtext('address'),
                    city=ad.findtext('city') or "Rosario",
                    price=float(ad.findtext('price') or 0),
                    currency=price_node.get('currency') if price_node is not None else "USD",
                    type=p_type,
                    operation="Sale" if "Sale" in ad.findtext('type') else "Rent",
                    description=ad.findtext('content'),
                    attributes=list(amenities),
                    bedrooms=int(ad.findtext('rooms') or 0),
                    bathrooms=int(ad.findtext('bathrooms') or 0),
                    surface=float(ad.findtext('plot_area') or 0),
                    surface_covered=float(ad.findtext('floor_area') or 0),
                    image=cover["full"] if cover else None,
                    thumbnail_url=cover["thumb"] if cover else None,
                    gallery=gallery,
                    lat=float(ad.findtext('latitude') or 0),
                    lng=float(ad.findtext('longitude') or 0),
                    status="Active"
                )
                db.add(new_prop); added_p += 1
            
            db.commit()

        return {"status": "success", "properties": added_p, "developments": added_d}
    except Exception as e:
        logger.error(f"Error crítico en importador Adinco: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/clean")
async def cleanup_imported_data(db: Session = Depends(get_db)):
    # Borrar propiedades importadas (código empieza con IMP-)
    props = db.query(models.Property).filter(models.Property.code.like("IMP-%")).all()
    devs = db.query(models.Development).all()
    for p in props: db.delete(p)
    for d in devs: db.delete(d)
    db.commit()
    return {"status": "success", "deleted_properties": len(props), "deleted_developments": len(devs)}