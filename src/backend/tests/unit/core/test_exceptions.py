# Third-party Libraries
from fastapi import status

# Local Libraries
from src.core.exceptions import CustomException
from src.shared.constants import ErrorCode


def test_custom_exception_initialization():
    detail = "Resource not found"
    status_code = status.HTTP_404_NOT_FOUND
    error_code = ErrorCode.NOT_FOUND.value

    exc = CustomException(
        status_code=status_code,
        detail=detail,
        error_code=error_code
    )

    assert exc.status_code == status_code
    assert exc.detail == detail
    assert exc.error_code == error_code
    assert exc.extra == {}


def test_custom_exception_with_extra():
    extra_data = {"item_id": 123}
    exc = CustomException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Bad Request",
        extra=extra_data
    )

    assert exc.error_code == ErrorCode.BAD_REQUEST.value
    assert exc.extra == extra_data
