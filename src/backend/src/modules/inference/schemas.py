# Standard Libraries
from typing import Any
from datetime import datetime

# Third-party Libraries
from pydantic import BaseModel, Field, field_serializer


class ModelActivationUpdate(BaseModel):
    activate: int = Field(..., ge=0, le=1, description="1 to deploy/activate API, 0 to undeploy/deactivate")


class FeatureSchemaItem(BaseModel):
    name: str
    data_type: str = "float"
    sample_value: Any = 0.0


class CodeSnippets(BaseModel):
    curl: str
    python: str
    javascript: str
    csharp: str
    php: str


class DeploymentInfoResponse(BaseModel):
    job_id: str
    dataset_id: str | None = None
    model_name: str
    status: str
    activate: int
    best_score: float | None = None
    endpoint_url: str
    features: list[str]
    features_schema: list[FeatureSchemaItem]
    sample_payload: dict[str, Any]
    code_snippets: CodeSnippets


class PredictRequest(BaseModel):
    data: list[dict[str, Any]] = Field(..., min_length=1, description="List of feature records for prediction")


class PredictResponse(BaseModel):
    job_id: str
    model_name: str
    predictions: list[Any]
    latency_ms: float
    total_samples: int


class JobDataInfo(BaseModel):
    id: str | None = None
    name: str | None = None


class JobUserInfo(BaseModel):
    id: str | None = None
    name: str | None = None


class JobItemResponse(BaseModel):
    id: str = Field(alias="_id")
    status: int
    activate: int
    data: JobDataInfo | dict[str, Any] | None = None
    user: JobUserInfo | dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    best_model_id: int | None = None
    best_model: str | None = None
    best_score: float | None = None
    best_params: dict[str, Any] | None = None
    orther_model_scores: list[Any] | None = None
    create_at: float | None = None
    infor: str | None = None

    model_config = {
        "populate_by_name": True,
        "from_attributes": True,
        "arbitrary_types_allowed": True,
    }

    @field_serializer("create_at")
    def serialize_dt_to_float(self, dt: datetime | float | None) -> float | None:
        if isinstance(dt, datetime):
            return dt.timestamp()
        return dt
