# Standard Libraries
import pytest

# Local Libraries
from src.core.security import HashHelper, jwt_service


def test_hash_helper():
    password = "my_strong_password_123!"
    hashed = HashHelper.get_password_hash(password)

    assert password != hashed
    assert HashHelper.verify_password(password, hashed) is True
    assert HashHelper.verify_password("wrong_password", hashed) is False


@pytest.mark.parametrize("token_type,create_fn", [
    ("access", jwt_service.create_access_token),
    ("refresh", jwt_service.create_refresh_token),
    ("verification", jwt_service.create_verification_token),
])
def test_jwt_token_lifecycle(token_type, create_fn):
    data = {"sub": f"user_id_{token_type}"}
    token = create_fn(data)
    assert token is not None

    payload = jwt_service.verify_token(token)
    assert payload is not None
    assert payload["sub"] == f"user_id_{token_type}"
    assert payload["type"] == token_type
    assert "exp" in payload


def test_jwt_service_verify_invalid_token():
    invalid_token = "this.is.invalid"
    payload = jwt_service.verify_token(invalid_token)
    assert payload is None
