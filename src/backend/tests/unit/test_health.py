# Standard Libraries
import unittest

# Third-party Libraries
from fastapi.testclient import TestClient

# Local Libraries
from src.main import app


class TestHealthCheck(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_check(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "Running")
        self.assertIn("project", data)
        self.assertIn("version", data)

if __name__ == "__main__":
    unittest.main()
