import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.main import app
from src.db.database import Base, get_db
from src.models.blacklist_model import BlacklistEmail

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

Base.metadata.create_all(bind=engine)

client = TestClient(app)
STATIC_BEARER_TOKEN = "123456"


@pytest.fixture(autouse=True)
def run_around_tests():
    db = TestingSessionLocal()
    db.query(BlacklistEmail).delete()
    db.commit()
    db.close()
    yield
    db = TestingSessionLocal()
    db.query(BlacklistEmail).delete()
    db.commit()
    db.close()


def test_add_email_success():
    response = client.post(
        "/blacklists/",
        json={
            "email": "test@example.com",
            "app_uuid": "abc-123",
            "blocked_reason": "spam"
        },
        headers={"Authorization": f"Bearer {STATIC_BEARER_TOKEN}"}
    )
    assert response.status_code == 201
    assert response.json()["message"] == "Email successfully added to blacklist"


def test_add_email_duplicate():
    client.post(
        "/blacklists/",
        json={
            "email": "test@example.com",
            "app_uuid": "abc-123"
        },
        headers={"Authorization": f"Bearer {STATIC_BEARER_TOKEN}"}
    )
    response = client.post(
        "/blacklists/",
        json={
            "email": "test@example.com",
            "app_uuid": "abc-123"
        },
        headers={"Authorization": f"Bearer {STATIC_BEARER_TOKEN}"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Email is already in blacklist"


def test_check_blacklisted_email():
    client.post(
        "/blacklists/",
        json={
            "email": "blocked@example.com",
            "app_uuid": "app-456"
        },
        headers={"Authorization": f"Bearer {STATIC_BEARER_TOKEN}"}
    )

    response = client.get(
        "/blacklists/blocked@example.com",
        headers={"Authorization": f"Bearer {STATIC_BEARER_TOKEN}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "blocked@example.com"
    assert data["is_blacklisted"] is True


def test_check_non_blacklisted_email():
    response = client.get(
        "/blacklists/nobody@example.com",
        headers={"Authorization": f"Bearer {STATIC_BEARER_TOKEN}"}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Email not found in blacklist"