# Standard Libraries
from enum import Enum
from datetime import datetime

# Third-party Libraries
from pydantic import BaseModel, Field, field_serializer


class DataTypeEnum(str, Enum):
    TABLE = "table"
    IMAGE = "image"
    TEXT = "text"


class SortNameEnum(str, Enum):
    AZ = "asc"
    ZA = "desc"


class SortTimeEnum(str, Enum):
    NEWEST = "desc"
    OLDEST = "asc"


class DatasetResponse(BaseModel):
    id: str = Field(alias="_id")
    dataName: str
    dataType: DataTypeEnum
    createDate: float
    latestUpdate: float

    thumbnail: str | None = None
    description: str | None = None

    model_config = {
        "populate_by_name": True,
        "from_attributes": True
    }

    @field_serializer("createDate", "latestUpdate")
    def serialize_dt_to_float(self, dt: datetime | float) -> float:
        if isinstance(dt, datetime):
            return dt.timestamp()
        return dt


class DatasetAdminResponse(DatasetResponse):
    userId: str
    username: str
    role: str


class DatasetCreate(BaseModel):
    dataName: str
    dataType: DataTypeEnum
    description: str | None = None


class DatasetUpdate(BaseModel):
    dataName: str | None = None
    description: str | None = None
