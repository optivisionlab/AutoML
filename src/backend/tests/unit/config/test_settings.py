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

    def test_mail_settings(self):
        self.assertIsNotNone(settings.MAIL.USERNAME)
        self.assertIsNotNone(settings.MAIL.PASSWORD)
        self.assertIsNotNone(settings.MAIL.LOGO)
        self.assertTrue(settings.MAIL.LOGO.startswith("http"))

    def test_backend_settings(self):
        self.assertIsNotNone(settings.BACKEND.HOST)
        self.assertIsInstance(settings.BACKEND.PORT, int)
        self.assertGreater(settings.BACKEND.PORT, 0)

    def test_pymapreduce_settings(self):
        self.assertIn(settings.PYMAPREDUCE.MODE, ["cluster", "local"])
        self.assertIsNotNone(settings.PYMAPREDUCE.HEAD_ADDRESS)
        if settings.PYMAPREDUCE.WORKER_IDLE_TIMEOUT is not None:
            self.assertGreaterEqual(settings.PYMAPREDUCE.WORKER_IDLE_TIMEOUT, 0)
        if settings.PYMAPREDUCE.ACTOR_IDLE_TIMEOUT is not None:
            self.assertGreaterEqual(settings.PYMAPREDUCE.ACTOR_IDLE_TIMEOUT, 0)
