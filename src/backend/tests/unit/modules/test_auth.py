# Standard Libraries
from unittest.mock import AsyncMock
import pytest

# Local Libraries
from src.main import app
from src.modules.auth.router import get_auth_service
from src.modules.auth.schemas import TokenResponse


@pytest.fixture
def mock_auth_service():
    service = AsyncMock()
    app.dependency_overrides[get_auth_service] = lambda: service
    yield service
    app.dependency_overrides.clear()


def test_signup_success(test_client, mock_auth_service):
    mock_auth_service.register.return_value = {
        "id": "123",
        "username": "testuser",
        "email": "test@example.com",
        "role": "user"
    }

    payload = {
        "username": "testuser",
        "email": "test@example.com",
        "gender": "male",
        "date": "01/01/2000",
        "number": "0123456789",
        "fullName": "Test User",
        "password": "password123"
    }

    response = test_client.post("/api/v1/auth/signup", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["username"] == "testuser"
    mock_auth_service.register.assert_called_once()


def test_login_success(test_client, mock_auth_service):
    mock_auth_service.login.return_value = TokenResponse(
        access_token="access_token",
        refresh_token="refresh_token",
        token_type="bearer"
    )

    payload = {
        "username": "testuser",
        "password": "password123"
    }

    response = test_client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["access_token"] == "access_token"
    mock_auth_service.login.assert_called_once()


def test_refresh_token_success(test_client, mock_auth_service):
    mock_auth_service.refresh_token.return_value = TokenResponse(
        access_token="new_access_token",
        refresh_token="new_refresh_token",
        token_type="bearer"
    )

    response = test_client.post("/api/v1/auth/refresh", json={"refresh_token": "valid_refresh_token"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["access_token"] == "new_access_token"
