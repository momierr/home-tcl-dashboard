from fastapi.testclient import TestClient

from home_tcl_dashboard.app import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/api/health")
    assert response.json() == {"status": "ok"}
    assert response.status_code == 200
