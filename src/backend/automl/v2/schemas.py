from pydantic import BaseModel
from typing import Dict, List, Any

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
                        "algorithm_search": "",
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
