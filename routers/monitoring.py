
from fastapi import APIRouter, Depends, HTTPException, Header, Query
from sqlalchemy.orm import Session
from database import get_db
import models, schemas
from typing import Optional, List
from datetime import datetime, date

router = APIRouter()

async def get_user_by_monitoring_token(db: Session = Depends(get_db), authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Monitoring Token is required")
    
    # Soporta tanto "Bearer <token>" como "<token>" directo
    try:
        token = authorization.split(" ")[1] if " " in authorization else authorization
    except IndexError:
        raise HTTPException(status_code=401, detail="Invalid token format")

    user = db.query(models.User).filter(models.User.monitoring_token == token).first()
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid Monitoring Token")
    
    return user

@router.post("/log")
async def log_activity(
    log_data: schemas.MonitoringLogCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_user_by_monitoring_token)
):
    db_log = models.MonitoringLog(
        user_id=user.id,
        app_name=log_data.app_name,
        window_title=log_data.window_title,
        url=log_data.url,
        start_time=log_data.start_time,
        end_time=log_data.end_time,
        duration_seconds=log_data.duration_seconds,
        is_idle=log_data.is_idle
    )
    db.add(db_log)
    db.commit()
    return {"status": "ok", "received": True, "user": user.email}

from auth import get_current_user_email

@router.get("/user/{user_id}")
def get_user_logs(
    user_id: int, 
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    email: str = Depends(get_current_user_email)
):
    # Authenticate user
    current_user = db.query(models.User).filter(models.User.email == email).first()
    if not current_user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    query = db.query(models.MonitoringLog).filter(models.MonitoringLog.user_id == user_id)
    
    if start_date:
        start_dt = datetime.combine(start_date, datetime.min.time())
        query = query.filter(models.MonitoringLog.timestamp >= start_dt)
    if end_date:
        end_dt = datetime.combine(end_date, datetime.max.time())
        query = query.filter(models.MonitoringLog.timestamp <= end_dt)
        
    logs = query.order_by(models.MonitoringLog.timestamp.desc()).limit(500).all()
    return logs
