# Standard Libraries
from unittest.mock import AsyncMock, MagicMock
import pytest
import pandas as pd
import numpy as np
from bson import ObjectId
from fastapi.testclient import TestClient

# Local Libraries
from src.main import app
from src.core.security import jwt_service


@pytest.fixture
def mock_db():
    """
    Mock MongoDB database with collections for repository testing
    """
    db = MagicMock()
    db.tbl_User = AsyncMock()
    db.tbl_Data = AsyncMock()
    db.tbl_Job = AsyncMock()
    db.tbl_Notification = AsyncMock()
    return db


@pytest.fixture
def mock_minio(monkeypatch):
    """
    Mock MinIO service for object storage operations
    """
    mock_service = AsyncMock()
    mock_service.upload_file = AsyncMock(return_value="models/test_model.pkl")
    mock_service.download_file = AsyncMock(return_value=b"fake-binary-content")
    mock_service.delete_file = AsyncMock(return_value=True)
    mock_service.get_presigned_url = AsyncMock(return_value="http://localhost:9000/presigned")
    mock_service.close = AsyncMock()
    
    monkeypatch.setattr("src.shared.minio_service", mock_service)
    return mock_service


@pytest.fixture
def mock_kafka(monkeypatch):
    """
    Mock Kafka service for event streaming
    """
    mock_service = AsyncMock()
    mock_service.send_message = AsyncMock(return_value=True)
    mock_service.connect = AsyncMock()
    mock_service.disconnect = AsyncMock()
    
    monkeypatch.setattr("src.shared.kafka_service", mock_service)
    return mock_service


@pytest.fixture
def mock_mqtt(monkeypatch):
    """
    Mock MQTT service for real-time notifications
    """
    mock_service = AsyncMock()
    mock_service.publish = AsyncMock(return_value=True)
    mock_service.connect = AsyncMock()
    mock_service.disconnect = AsyncMock()
    
    monkeypatch.setattr("src.shared.mqtt_service", mock_service)
    return mock_service


@pytest.fixture
def mock_mapreduce(monkeypatch):
    """
    Mock PyMapReduce Manager for cluster operations
    """
    mock_mgr = MagicMock()
    mock_driver = MagicMock()
    mock_mgr.get_driver = AsyncMock(return_value=mock_driver)
    mock_mgr.shutdown = AsyncMock()
    
    monkeypatch.setattr("src.shared.MapReduceManager", mock_mgr)
    return mock_mgr


@pytest.fixture
def sample_user_id():
    """
    Sample MongoDB ObjectId string
    """
    return str(ObjectId())


@pytest.fixture
def sample_user(sample_user_id):
    """
    Sample user document representation
    """
    return {
        "_id": ObjectId(sample_user_id),
        "username": "testuser",
        "email": "testuser@example.com",
        "is_active": True,
        "is_verified": True,
        "role": "user"
    }


@pytest.fixture
def auth_headers(sample_user_id):
    """
    Valid Authorization header with bearer token
    """
    token = jwt_service.create_access_token({"sub": sample_user_id, "role": "user"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def mock_lifespan_services(monkeypatch):
    """
    Globally mock all external services in lifespan for testing
    """
    monkeypatch.setattr("src.config.databases.DatabaseManager.connection", AsyncMock())
    monkeypatch.setattr("src.config.databases.DatabaseManager.close_connection", AsyncMock())
    monkeypatch.setattr("src.shared.MapReduceManager.get_driver", AsyncMock())
    monkeypatch.setattr("src.shared.MapReduceManager.shutdown", AsyncMock())
    monkeypatch.setattr("src.shared.mapreduce_client.MapReduceManager.get_driver", AsyncMock())
    monkeypatch.setattr("src.shared.mapreduce_client.MapReduceManager.shutdown", AsyncMock())
    monkeypatch.setattr("src.main.mqtt_service.connect", AsyncMock())
    monkeypatch.setattr("src.main.mqtt_service.disconnect", AsyncMock())
    monkeypatch.setattr("src.main.kafka_service.connect", AsyncMock())
    monkeypatch.setattr("src.main.kafka_service.disconnect", AsyncMock())
    monkeypatch.setattr("src.main.minio_service.close", AsyncMock())


@pytest.fixture
def test_client(mock_db, mock_minio, mock_kafka, mock_mqtt, mock_mapreduce, monkeypatch):
    """
    FastAPI TestClient with mocked database and shared services state
    """
    app.state.db = mock_db
    with TestClient(app) as client:
        yield client


@pytest.fixture
def sample_classification_df():
    """
    Sample DataFrame for classification tasks
    """
    np.random.seed(42)
    return pd.DataFrame({
        "feature_num1": np.random.randn(50),
        "feature_num2": np.random.uniform(10, 100, 50),
        "feature_cat": np.random.choice(["A", "B", "C"], 50),
        "target": np.random.choice([0, 1], 50)
    })


@pytest.fixture
def sample_regression_df():
    """
    Sample DataFrame for regression tasks
    """
    np.random.seed(42)
    x = np.random.randn(50)
    return pd.DataFrame({
        "feature_num1": x,
        "feature_num2": np.random.uniform(5, 50, 50),
        "feature_cat": np.random.choice(["Low", "Med", "High"], 50),
        "target": x * 2.5 + np.random.randn(50) * 0.1
    })
