from pydantic import BaseModel

class InputRequest(BaseModel):
    id_data: str
    id_user: str
    config: dict

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id_data": "1",
                    "id_user": "2",
                    "config": {
                        "choose": "new_model",
                        "metric_sort": "accuracy",
                        "list_feature": [
                            "A",
                            "B",
                            "..."
                        ],
                        "target": "Revenue"

                    }
                }
            ]
        }
    }

class UserInfo(BaseModel):
    id: str
    name: str

class DataInfo(BaseModel):
    id: str
    name: str

class JobResponse(BaseModel):
    _id: str | None
    job_id: str | None
    data: DataInfo | None
    user: UserInfo | None
    best_model_id: int | None
    best_params: dict | None
    best_score: float | None
    orther_model_scores: list | None
    status: int | None
    create_at: float | None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "_id": "1",
                    "job_id": "2",
                    "data": {
                        "id": "...",
                        "name": "..."
                    },
                    "user": {
                        "id": "...",
                        "name": "..."
                    },
                    "best_model_id": "...",
                    "best_params": {},
                    "best_score": 1.2,
                    "orther_model_scores": [],
                    "status": 1,
                    "create_at": 12.112
                }
            ]
        }
    }
