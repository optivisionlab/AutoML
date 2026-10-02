# Standard Libraries
import unittest

# Local Libraries
from src.config.settings import settings


class TestSettings(unittest.TestCase):
    def test_project_info(self):
        self.assertIsNotNone(settings.PROJECT.NAME)
        self.assertIsNotNone(settings.PROJECT.VERSION)

    def test_database_settings(self):
        self.assertIsNotNone(settings.MONGODB.CONNECT)
        self.assertEqual(settings.MONGODB.NAME, "AutoML")

    def test_cors_origins(self):
        self.assertIsInstance(settings.BACKEND_CORS_ORIGINS, list)
        self.assertGreater(len(settings.BACKEND_CORS_ORIGINS), 0)

    def test_pymapreduce_settings(self):
        self.assertIn(settings.PYMAPREDUCE.MODE, ["cluster", "local"])
        self.assertIsNotNone(settings.PYMAPREDUCE.HEAD_ADDRESS)
        self.assertGreaterEqual(settings.PYMAPREDUCE.TIMEOUT, 0)
        self.assertGreaterEqual(settings.PYMAPREDUCE.IDLE_TIMEOUT, 0)
