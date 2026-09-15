# Standard Libraries
import unittest
from unittest.mock import AsyncMock

# Third-party Libraries
from fastapi.testclient import TestClient

# Local Libraries
from src.main import app
from src.modules.users.router import get_user_service
from src.core.dependencies import get_current_user


class TestUsersAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        
        self.mock_user_service = AsyncMock()
        app.dependency_overrides[get_user_service] = lambda: self.mock_user_service
        
        # Default mock admin user for authorization
        self.mock_admin = {
            "_id": "admin_id",
            "role": "admin"
        }
        app.dependency_overrides[get_current_user] = lambda: self.mock_admin
        
    def tearDown(self):
        app.dependency_overrides.clear()

    def test_get_all_users_success(self):
        self.mock_user_service.get_paginated_users.return_value = (
            [{"id": "1", "username": "user1", "email": "user1@example.com", "role": "user", "is_verified": True}],
            {"current_page": 1, "page_size": 10, "total_items": 1, "total_pages": 1}
        )
        
        response = self.client.get("/api/v1/users")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["data"]), 1)
        self.assertEqual(data["meta"]["total_items"], 1)

    def test_get_user_by_id_success(self):
        self.mock_user_service.get_user_details.return_value = {
            "id": "123",
            "username": "testuser",
            "email": "test@example.com",
            "role": "user",
            "is_verified": True
        }
        
        response = self.client.get("/api/v1/users/123")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["username"], "testuser")

    def test_update_user_success(self):
        self.mock_user_service.update_user_info.return_value = {
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
        
        response = self.client.put("/api/v1/users/123", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["username"], "newname")

    def test_delete_user_success(self):
        response = self.client.delete("/api/v1/users/123")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

if __name__ == "__main__":
    unittest.main()
