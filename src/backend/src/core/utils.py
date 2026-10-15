# Standard Libraries
import os
import secrets
from typing import Any

# Third-party Libraries
from fastapi import status

# Local Libraries
from src.core.constants import ErrorCode
from src.core.exceptions import CustomException


def generate_otp(length: int = 6) -> str:
    """
    Create an OTP
    """
    return "".join(
        secrets.choice("0123456789") for _ in range(length)
    )


def get_file_size(file_obj: Any) -> int:
    """
    Get file size in bytes
    """
    file_size = -1
    target_stream = getattr(file_obj, "file", file_obj)
    if target_stream is not None and hasattr(target_stream, "seek") and hasattr(target_stream, "tell"):
        try:
            curr = target_stream.tell()
            target_stream.seek(0, os.SEEK_END)
            file_size = target_stream.tell() - curr
            target_stream.seek(curr)
        except Exception:
            file_size = -1

    if (file_size is None or file_size < 0) and hasattr(file_obj, "size") and file_obj.size is not None:
        file_size = file_obj.size

    return file_size if file_size is not None else -1


def validate_file_size(
    file_obj: Any,
    max_size_mb: int,
    error_message: str | None = None,
) -> int:
    """
    Validate file size limit
    """
    file_size = get_file_size(file_obj)
    limit_bytes = max_size_mb * 1024 * 1024

    if file_size > limit_bytes:
        msg = error_message or f"File size exceeds the allowed limit of {max_size_mb}MB."
        raise CustomException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
            error_code=ErrorCode.BAD_REQUEST,
        )

    return file_size


def validate_file_bytes_size(
    file_bytes: bytes,
    max_size_mb: int,
    error_message: str | None = None,
) -> None:
    """
    Validate byte buffer size limit
    """
    limit_bytes = max_size_mb * 1024 * 1024
    if len(file_bytes) > limit_bytes:
        msg = error_message or f"File size exceeds the allowed limit of {max_size_mb}MB."
        raise CustomException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=msg,
            error_code=ErrorCode.BAD_REQUEST,
        )
