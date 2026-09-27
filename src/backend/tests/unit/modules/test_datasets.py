# Standard Libraries
import unittest
from unittest.mock import AsyncMock
import time

# Third-party Libraries
from fastapi.testclient import TestClient

# Local Libraries
from src.main import app
from src.modules.datasets.router import get_dataset_service
from src.modules.datasets.service import DatasetService
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

    def test_get_list_public_datasets_success(self):
        self.mock_dataset_service.get_user_datasets.return_value = (
            [{
                "id": "dataset_public_1", 
                "dataName": "Community Dataset", 
                "dataType": "table", 
                "createDate": time.time(), 
                "latestUpdate": time.time(),
                "description": "Public dataset",
                "public": True
            }],
            {"current_page": 1, "page_size": 10, "total_items": 1, "total_pages": 1}
        )

        response = self.client.get("/api/v1/datasets/default")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(len(data["data"]), 1)
        self.assertEqual(data["data"][0]["dataName"], "Community Dataset")
        self.assertTrue(data["data"][0]["public"])

    def test_delete_dataset_success(self):
        # Service delete_dataset returns None on success
        self.mock_dataset_service.delete_dataset.return_value = None
        
        response = self.client.delete("/api/v1/datasets/dataset_1")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])


class TestDatasetServiceLogic(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_repo = AsyncMock()
        self.service = DatasetService(self.mock_repo)

        self.normal_user = {"_id": "user_1", "role": "user", "username": "user1"}
        self.other_user = {"_id": "user_2", "role": "user", "username": "user2"}
        self.admin_user = {"_id": "admin_1", "role": "admin", "username": "admin"}

    def test_is_dataset_public(self):
        self.assertTrue(self.service._is_dataset_public({"public": True}))
        self.assertTrue(self.service._is_dataset_public({"userId": "0"}))
        self.assertFalse(self.service._is_dataset_public({"userId": "user_1", "public": False}))

    def test_has_read_permission(self):
        # Owner can read
        self.assertTrue(self.service._has_read_permission({"userId": "user_1", "public": False}, self.normal_user))
        # Other user cannot read private dataset
        self.assertFalse(self.service._has_read_permission({"userId": "user_1", "public": False}, self.other_user))
        # Other user can read public dataset
        self.assertTrue(self.service._has_read_permission({"userId": "user_1", "public": True}, self.other_user))
        # Other user can read legacy dataset (userId '0')
        self.assertTrue(self.service._has_read_permission({"userId": "0"}, self.other_user))
        # Admin can read everything
        self.assertTrue(self.service._has_read_permission({"userId": "user_1", "public": False}, self.admin_user))

    def test_has_write_permission(self):
        # Owner can write
        self.assertTrue(self.service._has_write_permission({"userId": "user_1", "public": False}, self.normal_user))
        self.assertTrue(self.service._has_write_permission({"userId": "user_1", "public": True}, self.normal_user))
        # Other user cannot write
        self.assertFalse(self.service._has_write_permission({"userId": "user_1", "public": True}, self.other_user))
        # Normal user cannot write legacy dataset (userId '0')
        self.assertFalse(self.service._has_write_permission({"userId": "0"}, self.normal_user))
        # Admin can write legacy dataset and any dataset
        self.assertTrue(self.service._has_write_permission({"userId": "0"}, self.admin_user))
        self.assertTrue(self.service._has_write_permission({"userId": "user_1"}, self.admin_user))
    async def test_get_dataset_detail_private_access_denied(self):
        from bson import ObjectId
        from src.core.exceptions import CustomException
        oid = ObjectId()
        self.mock_repo.get_dataset_by_id.return_value = {
            "_id": oid,
            "dataName": "Private Data",
            "dataType": "table",
            "createDate": 123456.0,
            "latestUpdate": 123456.0,
            "userId": "user_1",
            "public": False
        }

        with self.assertRaises(CustomException) as ctx:
            await self.service.get_dataset_detail(self.other_user, str(oid))
        self.assertEqual(ctx.exception.status_code, 404)

    async def test_get_dataset_detail_public_allowed(self):
        from bson import ObjectId
        oid = ObjectId()
        self.mock_repo.get_dataset_by_id.return_value = {
            "_id": oid,
            "dataName": "Public Data",
            "dataType": "table",
            "createDate": 123456.0,
            "latestUpdate": 123456.0,
            "userId": "user_1",
            "public": True
        }

        res = await self.service.get_dataset_detail(self.other_user, str(oid))
        self.assertEqual(res.dataName, "Public Data")
        self.assertTrue(res.public)

    async def test_get_dataset_detail_legacy_allowed(self):
        from bson import ObjectId
        oid = ObjectId()
        self.mock_repo.get_dataset_by_id.return_value = {
            "_id": oid,
            "dataName": "Legacy Data",
            "dataType": "table",
            "createDate": 123456.0,
            "latestUpdate": 123456.0,
            "userId": "0",
            "public": None
        }

        res = await self.service.get_dataset_detail(self.other_user, str(oid))
        self.assertEqual(res.dataName, "Legacy Data")
        self.assertTrue(res.public)

    async def test_delete_dataset_permission_denied_for_non_owner(self):
        from bson import ObjectId
        from src.core.exceptions import CustomException
        oid = ObjectId()
        self.mock_repo.get_dataset_by_id.return_value = {
            "_id": oid,
            "userId": "user_1",
            "public": True
        }

        with self.assertRaises(CustomException) as ctx:
            await self.service.delete_dataset(self.other_user, str(oid))
        self.assertEqual(ctx.exception.status_code, 403)

    async def test_delete_legacy_dataset_denied_for_normal_user_allowed_for_admin(self):
        from bson import ObjectId
        from src.core.exceptions import CustomException
        oid = ObjectId()
        self.mock_repo.get_dataset_by_id.return_value = {
            "_id": oid,
            "userId": "0",
            "public": True
        }
        self.mock_repo.delete_dataset.return_value = True

        # Normal user -> 403 Forbidden
        with self.assertRaises(CustomException) as ctx:
            await self.service.delete_dataset(self.normal_user, str(oid))
        self.assertEqual(ctx.exception.status_code, 403)

        # Admin -> Success
        await self.service.delete_dataset(self.admin_user, str(oid))
        self.mock_repo.delete_dataset.assert_called_with(oid)


if __name__ == "__main__":
    unittest.main()

