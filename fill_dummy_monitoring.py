import sys
import os
import datetime
from sqlalchemy.orm import Session
from database import SessionLocal
from models import MonitoringLog, User

def generate_logs():
    db = SessionLocal()
    
    user_id = 2
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        print(f"User {user_id} not found.")
        sys.exit(1)
        
    # Set the target date as 2026-02-23
    target_date = datetime.date(2026, 2, 23)
    
    # We'll create a structured script of events
    events = [
        {"app_name": "chrome.exe", "title": "UrbanoCRM - Propiedades - Google Chrome", "start": "08:55:00", "end": "09:30:00"},
        {"app_name": "whatsapp.exe", "title": "WhatsApp - (12) Mensajes nuevos", "start": "09:30:00", "end": "09:45:00"},
        {"app_name": "chrome.exe", "title": "UrbanoCRM - Oportunidades - Google Chrome", "start": "09:45:00", "end": "10:30:00"},
        {"app_name": "IDLE_MODE", "title": "", "start": "10:30:00", "end": "10:35:00", "is_idle": True}, # Pausa PC
        {"app_name": "winword.exe", "title": "Contrato Alquiler depto Belgrano - Word", "start": "10:35:00", "end": "11:15:00"},
        {"app_name": "excel.exe", "title": "Reporte Finanzas Feb26.xlsx - Excel", "start": "11:15:00", "end": "11:40:00"},
        # Offline de 11:40 a 12:40 (1h = Fuera de Linea prolongado / Ausencia)
        {"app_name": "chrome.exe", "title": "Zonaprop Inmobiliarias - Google Chrome", "start": "12:40:00", "end": "13:00:00"},
        # Break programado de 13:00 a 13:30. Estará offline (o sea sin logs).
        # A las 13:30 vuelve.
        {"app_name": "chrome.exe", "title": "UrbanoCRM - Calendario - Google Chrome", "start": "13:30:00", "end": "14:15:00"},
        {"app_name": "IDLE_MODE", "title": "", "start": "14:15:00", "end": "14:40:00", "is_idle": True}, # Pausa 25 min (Se considera Offline por > 20min)
        {"app_name": "whatsapp.exe", "title": "WhatsApp - (3) Mensajes nuevos", "start": "14:40:00", "end": "15:20:00"},
        {"app_name": "chrome.exe", "title": "Google - Búsqueda de Chrome", "start": "15:20:00", "end": "15:50:00"},
        {"app_name": "spotify.exe", "title": "Spotify Premium", "start": "15:50:00", "end": "16:10:00"}, # Ocio, debería impactar en UI y análisis
        {"app_name": "chrome.exe", "title": "UrbanoCRM - Propiedades - Google Chrome", "start": "16:10:00", "end": "17:45:00"},
        {"app_name": "excel.exe", "title": "Listado de Visitas.xlsx", "start": "17:45:00", "end": "18:05:00"},
    ]

    # Borramos los actuales de hoy de ese usuario para limpiar
    start_dt = datetime.datetime.combine(target_date, datetime.time.min)
    end_dt = datetime.datetime.combine(target_date, datetime.time.max)
    db.query(MonitoringLog).filter(
        MonitoringLog.user_id == user_id,
        MonitoringLog.start_time >= start_dt,
        MonitoringLog.start_time <= end_dt
    ).delete()

    for e in events:
        st = datetime.datetime.strptime(f"{target_date} {e['start']}", "%Y-%m-%d %H:%M:%S")
        et = datetime.datetime.strptime(f"{target_date} {e['end']}", "%Y-%m-%d %H:%M:%S")
        dur = int((et - st).total_seconds())

        log = MonitoringLog(
            user_id=user_id,
            app_name=e["app_name"],
            window_title=e["title"],
            start_time=st,
            end_time=et,
            duration_seconds=dur,
            is_idle=e.get("is_idle", False),
            timestamp=datetime.datetime.utcnow()
        )
        db.add(log)
        
    db.commit()
    db.close()
    print("Done generating dummy data.")

if __name__ == '__main__':
    generate_logs()
