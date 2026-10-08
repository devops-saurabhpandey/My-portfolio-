from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_health():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'

def test_kpis():
    response = client.get('/api/v1/kpis')
    assert response.status_code == 200
    assert response.json()['orders'] == 500
