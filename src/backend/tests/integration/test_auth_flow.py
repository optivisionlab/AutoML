# Third-party Libraries
from bson import ObjectId

# Local Libraries
from src.core.security import HashHelper


def test_auth_workflow(test_client, mock_db):
    """
    Test complete authentication cycle: Signup -> Login -> Profile -> Refresh
    """
    user_id = str(ObjectId())
    user_oid = ObjectId(user_id)
    hashed_pwd = HashHelper.get_password_hash("secure_password_123")
    
    user_doc_unverified = {
        "_id": user_oid,
        "username": "autouser",
        "email": "autouser@example.com",
        "gender": "other",
        "date": "01/01/1995",
        "number": "0123456789",
        "fullName": "AutoML User",
        "role": "user",
        "avatar": None,
        "is_verified": False,
        "is_active": True,
        "created_at": 100000.0,
    }

    user_doc_verified = {
        "_id": user_oid,
        "username": "autouser",
        "email": "autouser@example.com",
        "gender": "other",
        "date": "01/01/1995",
        "number": "0123456789",
        "fullName": "AutoML User",
        "password": "secure_password_123",
        "role": "user",
        "avatar": None,
        "is_verified": True,
        "is_active": True,
        "created_at": 100000.0,
    }

    # Mock Database lookup and creation
    mock_db.tbl_User.insert_one.return_value.inserted_id = user_oid
    mock_db.linked_accounts.insert_one.return_value.inserted_id = ObjectId()
    mock_db.linked_accounts.find_one.return_value = {
        "user_id": user_oid,
        "provider": "local",
        "password": "secure_password_123",
    }

    # During signup: first find_one (check existence) -> None, second find_one (get_user_by_id) -> user_doc_unverified
    mock_db.tbl_User.find_one.side_effect = [None, user_doc_unverified]

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
    mock_db.tbl_User.find_one.side_effect = None
    mock_db.tbl_User.find_one.return_value = user_doc_verified

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
