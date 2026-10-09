# Third-party Libraries
import pytest
from pydantic import ValidationError

# Local Libraries
from src.core.responses import BaseResponse, PaginatedResponse, OffsetPaginatedResponse
from src.core.constants import MessageResponse


def test_base_response_default():
    response = BaseResponse()
    assert response.success is True
    assert response.message == MessageResponse.SUCCESS.value
    assert response.data is None
    assert response.meta is None


def test_base_response_with_data():
    data = {"id": 1, "name": "Test"}
    response = BaseResponse(data=data)
    assert response.success is True
    assert response.data == data


def test_paginated_response():
    data = [{"id": 1}, {"id": 2}]
    meta = {
        "total_items": 100,
        "current_page": 1,
        "page_size": 2,
        "total_pages": 50
    }

    response = PaginatedResponse(data=data, meta=meta)
    assert response.success is True
    assert len(response.data) == 2
    assert response.meta.total_items == 100
    assert response.meta.current_page == 1


def test_paginated_response_validation_error():
    data = [{"id": 1}]
    # Missing required fields in meta
    meta = {"total_items": 100}

    with pytest.raises(ValidationError):
        PaginatedResponse(data=data, meta=meta)


def test_offset_paginated_response():
    data = [{"id": 1}]
    meta = {
        "offset": 0,
        "limit": 10,
        "total_items": 5,
        "has_more": False
    }

    response = OffsetPaginatedResponse(data=data, meta=meta)
    assert response.success is True
    assert len(response.data) == 1
    assert response.meta.offset == 0
    assert response.meta.has_more is False
