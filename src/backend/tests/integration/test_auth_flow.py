# Third-party Libraries
from bson import ObjectId

# Local Libraries
from src.core.security import HashHelper


def test_auth_workflow(test_client, mock_db):
    """
    Test complete authentication cycle: Signup -> Login -> Profile -> Refresh
    """
    user_id = str(ObjectId())
    hashed_pwd = HashHelper.get_password_hash("secure_password_123")
    
    # Mock Database lookup and creation
    mock_db.tbl_User.find_one.return_value = None  # No existing user
    mock_db.tbl_User.insert_one.return_value.inserted_id = ObjectId(user_id)

    # 1. Signup Request
    signup_payload = {
        "username": "autouser",
        "email": "autouser@example.com",
        "gender": "other",
        "date": "01/01/1995",
        "number": "0123456789",
        "fullName": "AutoML User",
        "password": "secure_password_123"
    }
    signup_res = test_client.post("/api/v1/auth/signup", json=signup_payload)
    assert signup_res.status_code == 200
    assert signup_res.json()["success"] is True

    # 2. Login Request
    mock_db.tbl_User.find_one.return_value = {
        "_id": ObjectId(user_id),
        "username": "autouser",
        "email": "autouser@example.com",
        "password": hashed_pwd,
        "is_active": True,
        "is_verified": True,
        "role": "user"
    }

    login_res = test_client.post("/api/v1/auth/login", json={
        "username": "autouser",
        "password": "secure_password_123"
    })
    assert login_res.status_code == 200
    tokens = login_res.json()["data"]
    assert "access_token" in tokens
    assert "refresh_token" in tokens

    # 3. Access Protected User Profile
    auth_header = {"Authorization": f"Bearer {tokens['access_token']}"}
    profile_res = test_client.get(f"/api/v1/users/{user_id}", headers=auth_header)
    assert profile_res.status_code == 200

    # 4. Refresh Token
    refresh_res = test_client.post("/api/v1/auth/refresh", json={
        "refresh_token": tokens["refresh_token"]
    })
    assert refresh_res.status_code == 200
    assert "access_token" in refresh_res.json()["data"]
