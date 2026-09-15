# Standard Libraries
import unittest
from unittest.mock import AsyncMock

# Third-party Libraries
from fastapi.testclient import TestClient

# Local Libraries
from src.main import app
from src.modules.notifications.router import get_notification_service
from src.core.dependencies import get_current_user


class TestNotificationsAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        
        self.mock_notification_service = AsyncMock()
        app.dependency_overrides[get_notification_service] = lambda: self.mock_notification_service
        
        self.mock_user = {
            "_id": "user_123",
            "role": "user"
        }
        app.dependency_overrides[get_current_user] = lambda: self.mock_user
        
    def tearDown(self):
        app.dependency_overrides.clear()

    def test_fetch_notifications(self):
        mock_notif = {
            "id": "notif1", 
            "job_id": "job123", 
            "status": "success", 
            "message": "Test message", 
            "metadata": {}, 
            "is_read": False, 
            "created_at": 1600000000.0
        }
        self.mock_notification_service.fetch_notifications.return_value = (
            [mock_notif],
            {"offset": 0, "limit": 10, "total_items": 1, "has_more": False}
        )
        
        response = self.client.get("/api/v1/notifications")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["data"]), 1)
        self.assertEqual(data["data"][0]["message"], "Test message")
        self.assertFalse(data["meta"]["has_more"])

    def test_fetch_unread_notifications(self):
        mock_notif = {
            "id": "notif2", 
            "job_id": "job124", 
            "status": "pending", 
            "message": "Unread message", 
            "metadata": {}, 
            "is_read": False, 
            "created_at": 1600000000.0
        }
        self.mock_notification_service.fetch_notifications.return_value = (
            [mock_notif],
            {"offset": 0, "limit": 10, "total_items": 1, "has_more": False}
        )
        
        response = self.client.get("/api/v1/notifications/unread")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["data"]), 1)
        self.assertEqual(data["data"][0]["message"], "Unread message")

    def test_read_notification(self):
        response = self.client.put("/api/v1/notifications/notif1/read")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

if __name__ == "__main__":
    unittest.main()
