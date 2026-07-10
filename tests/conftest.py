import os
os.environ["RATE_LIMIT_ENABLED"] = "0"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app
from app.auth import get_password_hash
from app.models import User

TEST_DATABASE_URL = "sqlite:///./test.db"
test_engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def teacher_token(client, db):
    user = User(
        username="teacher",
        email="teacher@test.com",
        hashed_password=get_password_hash("pass123"),
        is_teacher=True
    )
    db.add(user)
    db.commit()

    r = client.post("/auth/login", json={
        "username": "teacher",
        "password": "pass123"
    })
    return r.json()["access_token"]


@pytest.fixture
def student_token(client):
    client.post("/auth/register", json={
        "username": "student",
        "email": "student@test.com",
        "password": "pass123",
        "is_teacher": False
    })
    r = client.post("/auth/login", json={
        "username": "student",
        "password": "pass123"
    })
    return r.json()["access_token"]


@pytest.fixture
def teacher_headers(teacher_token):
    return {"Authorization": f"Bearer {teacher_token}"}


@pytest.fixture
def student_headers(student_token):
    return {"Authorization": f"Bearer {student_token}"}
