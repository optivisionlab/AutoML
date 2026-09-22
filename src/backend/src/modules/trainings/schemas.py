# Standard Libraries
from typing import Any

# Third-party Libraries
from pydantic import BaseModel

# Local Libraries
from src.modules.preprocessing import CVStrategyConfig


class ModelTaskResult(BaseModel):
    """
    Schema for individual model training output executed on distributed workers
    """
    model_name: str
    best_params: dict[str, Any]
    scores: dict[str, float]
    primary_score: float
    metric_sort: str
    model_bytes: bytes
    latency: float

    model_config = {
        "arbitrary_types_allowed": True
    }


class ModelScoreItem(BaseModel):
    """
    Schema for individual model evaluation record in leaderboard and database
    """
    model_id: int
    model_name: str
    scores: dict[str, float]
    best_params: dict[str, Any]


class ModelStorageInfo(BaseModel):
    """
    Storage path specification for MinIO model artifact
    """
    bucket_name: str
    object_name: str


class AutoMLPipelineResult(BaseModel):
    """
    Output schema for pure in-memory AutoML distributed training pipeline
    """
    best_model_id: int
    best_model: str
    best_params: dict[str, Any]
    best_score: float
    model_scores: list[ModelScoreItem]
    best_model_bytes: bytes
    cv_strategy: CVStrategyConfig
    feature_names: list[str]
    time_limit_reached: bool = False
    completed_models: int
    total_models: int

    model_config = {
        "arbitrary_types_allowed": True
    }


class JobSuccessPayload(BaseModel):
    """
    Payload for updating tbl_Job in MongoDB upon successful training completion
    """
    best_model_id: int
    best_model: str
    model: ModelStorageInfo
    best_params: dict[str, Any]
    best_score: float
    model_scores: list[ModelScoreItem]
    time_limit_reached: bool = False
    completed_models: int | None = None
    total_models: int | None = None
