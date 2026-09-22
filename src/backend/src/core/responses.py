# Standard Libraries
from typing import Any, Generic, TypeVar

# Third-party Libraries
from pydantic import BaseModel

# Local Libraries
from src.shared import constants


# Declare Generic type T
T = TypeVar("T")

class BaseResponse(BaseModel, Generic[T]):
    """
    Standardized schema for APIs
    """
    success: bool = True
    message: str = constants.MessageResponse.SUCCESS.value
    data: T | None = None
    meta: dict[str, Any] | None = None


class PaginationMeta(BaseModel):
    """
    Schema defines paging parameters
    """
    total_items: int
    current_page: int
    page_size: int
    total_pages: int


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Normalized schema for APIs that return paginated lists
    """
    success: bool = True
    message: str = constants.MessageResponse.SUCCESS.value
    data: list[T]
    meta: PaginationMeta


class OffsetPaginationMeta(BaseModel):
    """
    Schema defines parameters for offset/limit pagination
    """
    offset: int
    limit: int
    total_items: int
    has_more: bool


class OffsetPaginatedResponse(BaseModel, Generic[T]):
    """
    Normalized schema for APIs that return lists using offset/limit.
    """
    success: bool = True
    message: str = constants.MessageResponse.SUCCESS.value
    data: list[T]
    meta: OffsetPaginationMeta
