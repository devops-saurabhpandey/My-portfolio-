from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


def test_csv_import_validation():
    csv = "sale_date,customer,amount\n2026-10-01,Acme,1200.50\n"
    response = client.post(
        "/api/v1/sales/import",
        files={"file": ("sales.csv", csv, "text/csv")},
    )
    assert response.status_code == 200
    assert response.json()["rows_received"] == 1


def test_csv_rejects_wrong_extension():
    response = client.post(
        "/api/v1/sales/import",
        files={"file": ("sales.txt", "hello", "text/plain")},
    )
    assert response.status_code == 400


def test_roles():
    response = client.get("/api/v1/roles")
    assert response.status_code == 200
    assert "ADMIN" in response.json()["roles"]
