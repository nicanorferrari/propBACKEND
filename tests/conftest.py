import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from auth import get_current_user_email
from database import Base, get_db
import models

# 1. Usaremos SQLite en memoria para que cada test sea rápido y 100% aislado
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

from sqlalchemy.pool import StaticPool

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para las pruebas (Sobreescribe get_db)
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

# Usuario mock para no depender de Firebase/JWT en las pruebas uniatias
TEST_EMAIL = "test_qa@urbanocrm.com"
def override_get_current_user_email():
    return TEST_EMAIL

# Aplicar los Mocks a FastAPI
fastapi_app = app.other_asgi_app if hasattr(app, "other_asgi_app") else app
fastapi_app.dependency_overrides[get_db] = override_get_db
fastapi_app.dependency_overrides[get_current_user_email] = override_get_current_user_email

client = TestClient(fastapi_app)

@pytest.fixture(scope="function")
def test_db():
    """
    Fixture que crea y destruye las tablas antes y después de cada test.
    Garantiza que ningún test influencie al siguiente (Test Isolation).
    """
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    # Pre-cargar datos mínimos para el test (El Tenant y el User)
    tenant = models.Tenant(name="QA Testing Agency")
    db.add(tenant)
    db.flush()
    
    user = models.User(
        email=TEST_EMAIL,
        first_name="QA",
        last_name="Tester",
        role="SUPER_ADMIN",
        tenant_id=tenant.id
    )
    db.add(user)
    db.commit()
    
    yield db  # Aquí se ejecutan los tests de abajo

    db.close()
    Base.metadata.drop_all(bind=engine)
