"""Replace these placeholder assertions when implementing the Backend ticket."""

from fastapi.testclient import TestClient

from app.main import create_app


def test_business_route_is_explicitly_unimplemented():
    with TestClient(create_app()) as client:
        response = client.get("/api/me")
    assert response.status_code == 501
    assert response.json()["error"]["code"] == "not_implemented"


def test_validation_uses_shared_error_envelope():
    with TestClient(create_app()) as client:
        response = client.get("/api/certificates?page_size=101")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
