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
                        "problem_type": "",
                        "search_algorithm": "",
                        "target": "Revenue",
                        "max_time": 900
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
