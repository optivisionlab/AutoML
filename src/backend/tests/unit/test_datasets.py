# Standard Libraries
import unittest
from unittest.mock import AsyncMock
import time

# Third-party Libraries
from fastapi.testclient import TestClient

# Local Libraries
from src.main import app
from src.modules.datasets.router import get_dataset_service
from src.core.dependencies import get_current_user


class TestDatasetsAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

        self.mock_dataset_service = AsyncMock()
        app.dependency_overrides[get_dataset_service] = lambda: self.mock_dataset_service

        # Default mock admin user for authorization
        self.mock_user = {
            "_id": "user_123",
            "role": "user",
            "username": "testuser"
        }
        app.dependency_overrides[get_current_user] = lambda: self.mock_user

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_get_list_datasets_success(self):
        self.mock_dataset_service.get_user_datasets.return_value = (
            [{
                "id": "dataset_1", 
                "dataName": "Dataset 1", 
                "dataType": "table", 
                "createDate": time.time(), 
                "latestUpdate": time.time(),
                "description": "Test dataset"
            }],
            {"current_page": 1, "page_size": 10, "total_items": 1, "total_pages": 1}
        )

        response = self.client.get("/api/v1/datasets")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["data"]), 1)
        self.assertEqual(data["meta"]["total_items"], 1)

    def test_get_dataset_by_id_success(self):
        self.mock_dataset_service.get_dataset_detail.return_value = {
            "id": "dataset_1", 
            "dataName": "Dataset 1", 
            "dataType": "table", 
            "createDate": time.time(), 
            "latestUpdate": time.time(),
            "description": "Test dataset"
        }

        response = self.client.get("/api/v1/datasets/dataset_1")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["dataName"], "Dataset 1")

    def test_upload_new_dataset_success(self):
        self.mock_dataset_service.upload_and_process_dataset.return_value = {
            "id": "dataset_2", 
            "dataName": "Uploaded Dataset", 
            "dataType": "table", 
            "createDate": time.time(), 
            "latestUpdate": time.time()
        }

        # Simulating multipart form-data upload
        files = {
            "file": ("test.csv", b"col1,col2\n1,2", "text/csv")
        }
        data_form = {
            "dataName": "Uploaded Dataset",
            "dataType": "table",
            "description": "New dataset"
        }

        response = self.client.post("/api/v1/datasets", data=data_form, files=files)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["dataName"], "Uploaded Dataset")

    def test_update_dataset_success(self):
        self.mock_dataset_service.update_dataset_info.return_value = {
            "id": "dataset_1", 
            "dataName": "Updated Dataset", 
            "dataType": "table", 
            "createDate": time.time(), 
            "latestUpdate": time.time(),
            "description": "Updated description"
        }

        payload = {
            "dataName": "Updated Dataset",
            "description": "Updated description"
        }

        response = self.client.put("/api/v1/datasets/dataset_1", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["dataName"], "Updated Dataset")

    def test_delete_dataset_success(self):
        # Service delete_dataset returns None on success
        self.mock_dataset_service.delete_dataset.return_value = None
        
        response = self.client.delete("/api/v1/datasets/dataset_1")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

if __name__ == "__main__":
    unittest.main()
