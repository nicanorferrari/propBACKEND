import pytest
import datetime
import models
from conftest import client, TEST_EMAIL, TestingSessionLocal

def test_healthz_root_endpoint():
    """Prueba que el servidor esté vivo y retorne 200"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_create_contact(test_db):
    """Prueba 1: Creación de un contacto normal"""
    payload = {
        "name": "Jane Doe QA",
        "phone": "549111222333",
        "email": "jane.doe@qa.com",
        "source": "MANUAL",
        "status": "HOT",
        "type": "CLIENT"
    }
    
    response = client.post("/api/contacts", json=payload)
    
    # 1. Asegurar HTTP 200
    assert response.status_code == 200
    data = response.json()
    
    # 2. Asegurar que los datos viajen correctamente
    assert data["name"] == "Jane Doe QA"
    assert "id" in data
    
    contact_id = data["id"]
    
    # 3. Comprobar la Integridad en Base de Datos (SQL isolation)
    assert test_db.query(models.ActivityLog).filter(
        models.ActivityLog.action == "CREATE"
    ).count() == 1

def test_duplicate_contact(test_db):
    """Prueba 2: El sistema debe rechazar telefonos y correos duplicados en el QA Tenant"""
    payload = {
        "name": "Original John",
        "phone": "999888777",
        "email": "john@qa.com"
    }
    client.post("/api/contacts", json=payload)
    
    # Intento 2 con el mismo número
    payload2 = {
        "name": "Imitator John",
        "phone": "999888777",  # Duplicado
    }
    response2 = client.post("/api/contacts", json=payload2)
    
    # Afirmar que falló con status de BadRequest o Conflict (FastAPI en contacts usa 400)
    assert response2.status_code == 400
    assert "already registered" in response2.json()["detail"].lower()

def test_last_contact_date_updates(test_db):
    """Prueba 3: Integración de la Bitácora (Interacciones) y su reflejo en Last Contact Date"""
    
    # Primero creamos un Contacto
    payload = {"name": "Bob Interaction", "phone": "123123"}
    res = client.post("/api/contacts", json=payload)
    c_id = res.json()["id"]
    
    # Agregamos una interacción manual a la fecha actual
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    client.post(f"/api/contacts/{c_id}/interactions", json={
        "type": "NOTE",
        "notes": "Bob probando su actualización",
        "date": now_iso
    })
    
    # Refrescamos desde la DB para revisar su 'last_contact_date'
    updated_contact = test_db.query(models.Contact).filter(models.Contact.id == c_id).first()
    
    assert updated_contact.last_contact_date is not None, "El contacto nunca fue tocado!"
