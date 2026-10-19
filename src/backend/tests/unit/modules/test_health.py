# Local Libraries
from src.config.settings import settings


def test_health_check(test_client):
    response = test_client.get("/")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "Running"
    assert data["project"] == settings.PROJECT.NAME
    assert data["version"] == settings.PROJECT.VERSION
