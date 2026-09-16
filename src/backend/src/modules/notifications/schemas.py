# Standard Libraries
from typing import Any

# Third-party Libraries
from pydantic import BaseModel, Field


class NotificationResponse(BaseModel):
    id: str = Field(alias="_id") 
    job_id: str
    status: str | int
    message: str
    metadata: dict[str, Any]
    is_read: bool
    created_at: float

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }
