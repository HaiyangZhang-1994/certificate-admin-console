import pytest
from fastapi.testclient import TestClient

from app.main import create_app

ORIGIN = "http://127.0.0.1:5173"


def log_in(client, city="sydney"):
    response = client.post(
        "/api/auth/login",
        headers={"Origin": ORIGIN},
        json={"username": f"{city}.admin", "password": "DemoPass123!"},
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def database_url(tmp_path):
    return f"sqlite:///{(tmp_path / 'test.db').as_posix()}"


@pytest.fixture
def client(database_url):
    with TestClient(create_app(database_url, seed_demo=True, busy_timeout=100)) as client:
        yield client


@pytest.fixture
def authenticated(client):
    log_in(client)
    return client
