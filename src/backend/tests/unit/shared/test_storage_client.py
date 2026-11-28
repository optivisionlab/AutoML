import pytest

from src.shared.storage_client import S3Storage


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("", ""),
        ("   ", ""),
        ("minio", "minio"),
        ("minio:9000", "minio:9000"),
        ("localhost:9000", "localhost:9000"),
        ("127.0.0.1:9000", "127.0.0.1:9000"),
        (" minio:9000/ ", "minio:9000"),
        ("//minio:9000", "minio:9000"),
        ("http://minio:9000/", "minio:9000"),
        ("https://s3.example.com/bucket", "s3.example.com"),
        ("[::1]:9000", "[::1]:9000"),
        ("http://[::1]:9000/", "[::1]:9000"),
    ],
)
def test_storage_endpoint_preserves_host_and_port(raw, expected):
    assert S3Storage._clean_endpoint(raw) == expected
