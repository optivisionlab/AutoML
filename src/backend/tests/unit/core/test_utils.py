import io
import pytest
from src.core.exceptions import CustomException
from src.core.utils import generate_otp, get_file_size, validate_file_size, validate_file_bytes_size


def test_generate_otp():
    otp = generate_otp(6)
    assert len(otp) == 6
    assert otp.isdigit()


def test_get_file_size_from_bytesio():
    buf = io.BytesIO(b"1234567890")
    size = get_file_size(buf)
    assert size == 10
    # Pointer should be restored
    assert buf.tell() == 0


def test_get_file_size_from_object_with_size_attr():
    class FakeFile:
        size = 2048

    size = get_file_size(FakeFile())
    assert size == 2048


def test_validate_file_size_success():
    buf = io.BytesIO(b"x" * 1024)
    size = validate_file_size(buf, max_size_mb=1)
    assert size == 1024


def test_validate_file_size_oversized_raises():
    buf = io.BytesIO(b"x" * (2 * 1024 * 1024)) # 2MB
    with pytest.raises(CustomException) as ctx:
        validate_file_size(buf, max_size_mb=1)
    assert ctx.value.status_code == 400
    assert "exceeds the allowed limit" in ctx.value.detail


def test_validate_file_bytes_size_success():
    data = b"x" * 1024
    validate_file_bytes_size(data, max_size_mb=1)


def test_validate_file_bytes_size_oversized_raises():
    data = b"x" * (2 * 1024 * 1024)
    with pytest.raises(CustomException) as ctx:
        validate_file_bytes_size(data, max_size_mb=1, error_message="Custom oversized error")
    assert ctx.value.status_code == 400
    assert "Custom oversized error" in ctx.value.detail
