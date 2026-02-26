
import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import models, schemas
from database import get_db

from auth import get_current_user_email

router = APIRouter()

# CONFIGURACIÓN DE AGENCIA (Privada)
@router.get("/agency/config")
def get_agency_config(db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    conf = db.query(models.AgencyConfig).first()
    if not conf:
        conf = models.AgencyConfig(agency_name="Urbano Inmobiliaria")
        db.add(conf)
        db.commit()
        db.refresh(conf)
    return conf

@router.put("/agency/config")
def update_agency_config(data: schemas.AgencyConfigUpdate, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    conf = db.query(models.AgencyConfig).first()
    if not conf: raise HTTPException(404)
    for k, v in data.dict(exclude_unset=True).items(): setattr(conf, k, v)
    db.commit()
    db.refresh(conf)
    return conf

# CONFIGURACIÓN PÚBLICA (Para el mapa del frontend)
@router.get("/public/config/maps-key")
def get_maps_key(db: Session = Depends(get_db)):
    cfg = db.query(models.SystemConfig).filter(models.SystemConfig.key == "google_maps_key").first()
    # Retornamos la key de la DB o el fallback de env
    return {"key": cfg.value if cfg else os.getenv("VITE_GOOGLE_MAPS_KEY", "")}

# CONFIGURACIÓN ADMIN (Para el Super Admin)
@router.get("/admin/config/google_maps_key")
def get_admin_maps_key(db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    # Simple auth check
    user = db.query(models.User).filter(models.User.email == email).first()
    if user.role != "BROKER_ADMIN" and user.role != "SUPERADMIN":
         raise HTTPException(status_code=403, detail="Forbidden")
    cfg = db.query(models.SystemConfig).filter(models.SystemConfig.key == "google_maps_key").first()
    return {"value": cfg.value if cfg else ""}

@router.put("/admin/config/google_maps_key")
def set_admin_maps_key(data: schemas.ConfigUpdate, db: Session = Depends(get_db), email: str = Depends(get_current_user_email)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if user.role != "BROKER_ADMIN" and user.role != "SUPERADMIN":
         raise HTTPException(status_code=403, detail="Forbidden")
    cfg = db.query(models.SystemConfig).filter(models.SystemConfig.key == "google_maps_key").first()
    if not cfg:
        cfg = models.SystemConfig(key="google_maps_key", value=data.value)
        db.add(cfg)
    else:
        cfg.value = data.value
    db.commit()
    return {"status": "ok"}

@router.get("/public/inventory-summary")
def get_inventory_summary(db: Session = Depends(get_db)):
    """
    Retorna conteo de propiedades por operación para validación en WebBuilder.
    """
    sale = db.query(models.Property).filter(models.Property.operation.in_(["Venta", "Sale"]), models.Property.status == "Active").count()
    rent = db.query(models.Property).filter(models.Property.operation.in_(["Alquiler", "Rent"]), models.Property.status == "Active").count()
    temp = db.query(models.Property).filter(models.Property.operation.in_(["Alquiler Temporal", "Temporary Rent"]), models.Property.status == "Active").count()
    devs = db.query(models.Development).filter(models.Development.status.in_(["Active", "CONSTRUCTION"])).count()
    
    return {
        "sale_count": sale,
        "rent_count": rent,
        "temp_rent_count": temp,
        "development_count": devs
    }
