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


@pytest.mark.asyncio
async def test_update_user_avatar_streams_to_object_storage():
    import io
    from unittest.mock import patch, MagicMock
    from bson import ObjectId
    from src.modules.users.service import UserService

    mock_repo = AsyncMock()
    user_id = str(ObjectId())
    mock_repo.get_user_by_id.return_value = {"_id": ObjectId(user_id), "username": "u1"}
    mock_repo.update_avatar.return_value = True

    service = UserService(mock_repo)

    mock_file = MagicMock()
    mock_file.filename = "my_photo.jpg"
    mock_file.content_type = "image/jpeg"
    mock_file.file = io.BytesIO(b"\xff\xd8\xff...")

    with patch("src.shared.backblaze_service.upload_file_stream", new_callable=AsyncMock) as mock_upload_stream:
        res = await service.update_user_avatar(user_id, mock_file)
        assert res.startswith(f"avatars/{user_id}/")
        mock_upload_stream.assert_called_once()
        mock_repo.update_avatar.assert_called_once()


@pytest.mark.asyncio
async def test_backblaze_upload_oversized_file_raises_bad_request():
    import io
    from src.core.exceptions import CustomException
    from src.shared import backblaze_service

    large_file = io.BytesIO(b"x" * (15 * 1024 * 1024)) # 15MB > 10MB limit

    with pytest.raises(CustomException) as ctx:
        await backblaze_service.upload_file_stream(
            object_name="avatars/test/big.png",
            file_obj=large_file,
            max_size_mb=10
        )
    assert ctx.value.status_code == 400
    assert "exceeds the allowed limit" in ctx.value.detail


@pytest.mark.asyncio
async def test_get_user_avatar_backward_compatible_base64():
    import base64
    from bson import ObjectId
    from src.modules.users.service import UserService

    mock_repo = AsyncMock()
    user_id = str(ObjectId())
    raw_img = b"PNG_FAKE_BYTES"
    b64_str = base64.b64encode(raw_img).decode("utf-8")

    mock_repo.get_user_by_id.return_value = {"_id": ObjectId(user_id), "avatar": b64_str}
    service = UserService(mock_repo)

    data = await service.get_user_avatar(user_id)
    assert data == raw_img


@pytest.mark.asyncio
async def test_get_user_avatar_object_storage_ref():
    import io
    from unittest.mock import patch
    from bson import ObjectId
    from src.modules.users.service import UserService

    mock_repo = AsyncMock()
    user_id = str(ObjectId())
    raw_img = b"BACKBLAZE_STORAGE_IMAGE_BYTES"

    mock_repo.get_user_by_id.return_value = {"_id": ObjectId(user_id), "avatar": f"avatars/{user_id}/avatar_1.png"}
    service = UserService(mock_repo)

    with patch("src.shared.backblaze_service.get_object", new_callable=AsyncMock) as mock_get_obj:
        mock_get_obj.return_value = io.BytesIO(raw_img)

        data = await service.get_user_avatar(user_id)
        assert data == raw_img
        mock_get_obj.assert_called_once_with(f"avatars/{user_id}/avatar_1.png")
