# Standard Libraries
from unittest.mock import AsyncMock
import pytest

# Local Libraries
from src.main import app
from src.modules.users.router import get_user_service
from src.core.dependencies import get_current_user


@pytest.fixture
def mock_user_service():
    service = AsyncMock()
    app.dependency_overrides[get_user_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: {"_id": "admin_id", "role": "admin"}
    yield service
    app.dependency_overrides.clear()


def test_get_all_users_success(test_client, mock_user_service):
    mock_user_service.get_paginated_users.return_value = (
        [{"id": "1", "username": "user1", "email": "user1@example.com", "role": "user", "is_verified": True}],
        {"current_page": 1, "page_size": 10, "total_items": 1, "total_pages": 1}
    )

    response = test_client.get("/api/v1/users")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["data"]) == 1
    assert data["meta"]["total_items"] == 1


def test_get_user_by_id_success(test_client, mock_user_service):
    mock_user_service.get_user_details.return_value = {
        "id": "123",
        "username": "testuser",
        "email": "test@example.com",
        "role": "user",
        "is_verified": True
    }

    response = test_client.get("/api/v1/users/123")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["username"] == "testuser"


def test_update_user_success(test_client, mock_user_service):
    mock_user_service.update_user_info.return_value = {
        "id": "123",
        "username": "newname",
        "email": "test@example.com",
        "role": "user",
        "is_verified": True
    }

    payload = {
        "fullName": "New Name",
        "number": "0987654321"
    }

    response = test_client.put("/api/v1/users/123", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["username"] == "newname"


def test_delete_user_success(test_client, mock_user_service):
    response = test_client.delete("/api/v1/users/123")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
