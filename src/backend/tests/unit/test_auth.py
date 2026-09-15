# Standard Libraries
import unittest
from unittest.mock import AsyncMock

# Third-party Libraries
from fastapi.testclient import TestClient

# Local Libraries
from src.main import app
from src.modules.auth.router import get_auth_service
from src.core.dependencies import get_current_user
from src.modules.auth.schemas import TokenResponse


class TestAuthAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        
        # Mock AuthService
        self.mock_auth_service = AsyncMock()
        
        # Override dependency
        app.dependency_overrides[get_auth_service] = lambda: self.mock_auth_service
        
    def tearDown(self):
        app.dependency_overrides.clear()

    def test_signup_success(self):
        # mock register response
        self.mock_auth_service.register.return_value = {
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
        
        response = self.client.post("/api/v1/auth/signup", json=payload)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["username"], "testuser")
        self.mock_auth_service.register.assert_called_once()

    def test_login_success(self):
        self.mock_auth_service.login.return_value = TokenResponse(
            access_token="access_token",
            refresh_token="refresh_token",
            token_type="bearer"
        )
        
        payload = {
            "username": "testuser",
            "password": "password123"
        }
        
        response = self.client.post("/api/v1/auth/login", json=payload)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["access_token"], "access_token")
        self.assertEqual(response.cookies.get("refresh_token"), "refresh_token")
        self.mock_auth_service.login.assert_called_once()
        
    def test_refresh_token_success(self):
        self.mock_auth_service.refresh_token.return_value = TokenResponse(
            access_token="new_access_token",
            refresh_token="new_refresh_token",
            token_type="bearer"
        )
        
        payload = {
            "refresh_token": "old_refresh_token"
        }
        
        response = self.client.post("/api/v1/auth/refresh", json=payload)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["access_token"], "new_access_token")
        self.assertEqual(response.cookies.get("refresh_token"), "new_refresh_token")
        self.mock_auth_service.refresh_token.assert_called_once()

    def test_get_me_success(self):
        mock_user = {
            "_id": "123",
            "username": "testuser",
            "email": "test@example.com",
            "role": "user"
        }
        
        app.dependency_overrides[get_current_user] = lambda: mock_user
        
        response = self.client.get("/api/v1/auth/me")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["username"], "testuser")

    def test_logout_success(self):
        app.dependency_overrides[get_current_user] = lambda: {"_id": "123"}
        
        response = self.client.post("/api/v1/auth/logout")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])


if __name__ == '__main__':
    unittest.main()
