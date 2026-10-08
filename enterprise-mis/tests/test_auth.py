from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


def token_for(username, password):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_login_and_me():
    token = token_for("admin", "admin-demo")
    response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["role"] == "ADMIN"


def test_viewer_cannot_import():
    token = token_for("viewer", "viewer-demo")
    response = client.post(
        "/api/v1/sales/import",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("sales.csv", "sale_date,customer,amount\n2026-10-01,A,10", "text/csv")},
    )
    assert response.status_code == 403
