from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

# --- 1. ĐỊNH NGHĨA CÁC EXCEPTION CHUẨN HÓA ---
class DatabaseAdapterError(Exception):
    """Lỗi gốc cho toàn bộ adapter"""
    pass

class DatabaseConnectionError(DatabaseAdapterError):
    """Lỗi khi không thể kết nối tới DB (sai IP/port, timeout)"""
    pass

class TableNotFoundError(DatabaseAdapterError):
    """Lỗi khi không tìm thấy bảng"""
    pass

class QueryExecutionError(DatabaseAdapterError):
    """Lỗi khi truy vấn dữ liệu"""
    pass

# --- 2. CẤU HÌNH KẾT NỐI CHUẨN ---
@dataclass
class DatabaseConfig:
    db_type: str
    database: str
    host: Optional[str] = "localhost"
    port: Optional[int] = None
    user: Optional[str] = None
    password: Optional[str] = None
    schema_name: Optional[str] = None
    connect_timeout: int = 5
    extra_params: Dict[str, Any] = field(default_factory=dict)

# --- 3. TẦNG CHUNG TRỪU TƯỢNG (BASE ADAPTER) ---
class BaseDatabaseAdapter(ABC):
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._engine: Optional[Engine] = None

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            self._engine = self.create_engine()
        return self._engine

    # Các hàm trừu tượng: Mỗi hệ CSDL con bắt buộc phải tự viết
    @abstractmethod
    def get_connection_url(self) -> str:
        """Tạo chuỗi connection string riêng cho CSDL"""
        pass

    @abstractmethod
    def create_engine(self) -> Engine:
        """Khởi tạo SQLAlchemy engine kèm cấu hình riêng (timeout, charset...)"""
        pass

    @abstractmethod
    def quote_identifier(self, identifier: str) -> str:
        """Bọc tên bảng theo chuẩn từng CSDL (Postgres dùng ", MySQL dùng `)"""
        pass

    # Các hàm dùng chung (Đã có sẵn logic dùng cho mọi CSDL)
    def test_connection(self) -> bool:
        """Kiểm tra nhanh kết nối bằng lệnh SELECT 1"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            raise DatabaseConnectionError(f"Không thể kết nối đến cơ sở dữ liệu: {str(e)}") from e

    def get_tables(self) -> List[str]:
        """Lấy danh sách tên bảng"""
        try:
            with self.engine.connect() as conn:
                inspector = inspect(conn)
                tables = inspector.get_table_names(schema=self.config.schema_name)
                return sorted(tables)
        except Exception as e:
            raise DatabaseConnectionError(f"Lỗi khi lấy danh sách bảng: {str(e)}") from e

    def fetch_table_to_dataframe(self, table_name: str, limit: int = 50000) -> pd.DataFrame:
        """Kéo dữ liệu bảng về DataFrame an toàn"""
        tables = self.get_tables()
        if table_name not in tables:
            raise TableNotFoundError(f"Bảng '{table_name}' không tồn tại trong CSDL.")

        safe_table = self.quote_identifier(table_name)
        query = f"SELECT * FROM {safe_table} LIMIT {int(limit)}"

        try:
            with self.engine.connect() as conn:
                return pd.read_sql(text(query), con=conn)
        except Exception as e:
            raise QueryExecutionError(f"Lỗi trích xuất bảng '{table_name}': {str(e)}") from e

    def dispose(self):
        """Dọn dẹp và đóng Engine, giải phóng Connection Pool"""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None

    # Hỗ trợ cú pháp "with adapter:"
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dispose()
