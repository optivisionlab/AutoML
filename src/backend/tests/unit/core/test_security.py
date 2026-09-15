# Standard Libraries
import unittest

# Local Libraries
from src.core.security import HashHelper, jwt_service


class TestSecurity(unittest.TestCase):
    def test_hash_helper(self):
        password = "my_strong_password_123!"
        hashed = HashHelper.get_password_hash(password)

        self.assertNotEqual(password, hashed)
        self.assertTrue(HashHelper.verify_password(password, hashed))
        self.assertFalse(HashHelper.verify_password("wrong_password", hashed))

    def test_jwt_service_access_token(self):
        data = {"sub": "user_id_123"}
        token = jwt_service.create_access_token(data)

        self.assertIsNotNone(token)

        payload = jwt_service.verify_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], "user_id_123")
        self.assertEqual(payload["type"], "access")
        self.assertIn("exp", payload)

    def test_jwt_service_refresh_token(self):
        data = {"sub": "user_id_456"}
        token = jwt_service.create_refresh_token(data)

        self.assertIsNotNone(token)

        payload = jwt_service.verify_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], "user_id_456")
        self.assertEqual(payload["type"], "refresh")

    def test_jwt_service_verification_token(self):
        data = {"sub": "user_id_789"}
        token = jwt_service.create_verification_token(data)

        self.assertIsNotNone(token)

        payload = jwt_service.verify_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], "user_id_789")
        self.assertEqual(payload["type"], "verification")

    def test_jwt_service_verify_invalid_token(self):
        invalid_token = "this.is.invalid"
        payload = jwt_service.verify_token(invalid_token)
        self.assertIsNone(payload)


if __name__ == '__main__':
    unittest.main()
