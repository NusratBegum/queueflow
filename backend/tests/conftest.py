import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://postgres@localhost:5433/queueflow_test")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-use-0123456789")

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def signup(client: TestClient, email: str = "staff@example.com") -> dict[str, str]:
    r = client.post("/api/v1/auth/signup", json={"email": email, "password": "correct-horse"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def auth(client: TestClient) -> dict[str, str]:
    return signup(client)


@pytest.fixture
def queue(client: TestClient, auth: dict[str, str]) -> dict:
    r = client.post("/api/v1/queues", json={"name": "Corner Clinic"}, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()
