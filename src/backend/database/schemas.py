from typing import Optional, Dict, Any
from pydantic import BaseModel


class ConnectDBRequest(BaseModel):
    """Schema dữ liệu cho API kết nối và lấy danh sách bảng CSDL."""
    db_type: str
    database: str
    host: Optional[str] = "localhost"
    port: Optional[int] = None
    user: Optional[str] = None
    password: Optional[str] = None
    schema_name: Optional[str] = None
    extra_params: Optional[Dict[str, Any]] = None


class ImportTableRequest(BaseModel):
    """Schema dữ liệu cho API trích xuất bảng CSDL thành dataset trong AutoML."""
    db_type: str
    database: str
    table_name: str
    data_name: str
    host: Optional[str] = "localhost"
    port: Optional[int] = None
    user: Optional[str] = None
    password: Optional[str] = None
    schema_name: Optional[str] = None
    extra_params: Optional[Dict[str, Any]] = None
