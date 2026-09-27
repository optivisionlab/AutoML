from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import pandas as pd
from sqlalchemy import inspect, text
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
    def get_test_query(self) -> str:
        """Câu lệnh kiểm tra kết nối (mặc định SELECT 1, CSDL như Oracle cần SELECT 1 FROM DUAL)"""
        return "SELECT 1"

    def test_connection(self) -> bool:
        """Kiểm tra nhanh kết nối"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text(self.get_test_query()))
            return True
        except Exception as e:
            raise DatabaseConnectionError(f"Không thể kết nối đến cơ sở dữ liệu: {str(e)}") from e

    def get_tables(self) -> List[str]:
        """Lấy danh sách tên bảng (bao gồm cả views nếu có)"""
        try:
            schema = (
                self.config.schema_name.strip()
                if self.config.schema_name and self.config.schema_name.strip()
                else None
            )
            with self.engine.connect() as conn:
                inspector = inspect(conn)
                tables = inspector.get_table_names(schema=schema)
                try:
                    views = inspector.get_view_names(schema=schema) or []
                except Exception:
                    views = []
                all_tables = set(tables + views)
                return sorted(list(all_tables))
        except Exception as e:
            raise DatabaseConnectionError(f"Lỗi khi lấy danh sách bảng: {str(e)}") from e

    def get_full_table_name(self, table_name: str) -> str:
        """Ghép schema_name với tên bảng nếu có chỉ định schema"""
        safe_table = self.quote_identifier(table_name)
        schema = (
            self.config.schema_name.strip()
            if self.config.schema_name and self.config.schema_name.strip()
            else None
        )
        if schema:
            safe_schema = self.quote_identifier(schema)
            return f"{safe_schema}.{safe_table}"
        return safe_table

    def build_select_query(self, table_name: str, limit: int = 50000) -> str:
        """Xây dựng câu lệnh SELECT giới hạn số dòng (override ở MSSQL, Oracle)"""
        safe_table = self.get_full_table_name(table_name)
        return f"SELECT * FROM {safe_table} LIMIT {int(limit)}"

    def fetch_table_to_dataframe(self, table_name: str, limit: int = 50000) -> pd.DataFrame:
        """Kéo dữ liệu bảng về DataFrame an toàn"""
        tables = self.get_tables()
        canonical_table = None
        if table_name in tables:
            canonical_table = table_name
        else:
            # Fallback cho CSDL trả về chữ HOA như Snowflake, Oracle
            lower_map = {t.lower(): t for t in tables}
            if table_name.lower() in lower_map:
                canonical_table = lower_map[table_name.lower()]
            else:
                raise TableNotFoundError(f"Bảng hoặc view '{table_name}' không tồn tại trong CSDL.")

        query = self.build_select_query(table_name=canonical_table, limit=limit)

        try:
            with self.engine.connect() as conn:
                return pd.read_sql(text(query), con=conn)
        except Exception as e:
            raise QueryExecutionError(f"Lỗi trích xuất bảng '{table_name}': {str(e)}") from e

    def run_sql(self, sql: str, limit: Optional[int] = 1000) -> pd.DataFrame:
        """Cho phép AI Agent thực thi câu SQL tự do một cách an toàn"""
        cleaned_sql = sql.strip().upper()
        if not (cleaned_sql.startswith("SELECT") or cleaned_sql.startswith("WITH")):
            raise ValueError("Chỉ cho phép thực thi câu lệnh truy vấn đọc dữ liệu (SELECT / WITH).")
        with self.engine.connect() as conn:
            df = pd.read_sql(text(sql), con=conn)
            if limit is not None and len(df) > limit:
                return df.head(limit)
            return df

    def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Trích xuất danh sách cột & kiểu dữ liệu để làm Prompt ngữ cảnh cho Agent"""
        schema = (
            self.config.schema_name.strip()
            if self.config.schema_name and self.config.schema_name.strip()
            else None
        )
        with self.engine.connect() as conn:
            inspector = inspect(conn)
            columns = inspector.get_columns(table_name, schema=schema)
            return {
                "table_name": table_name,
                "columns": [{"name": col["name"], "type": str(col["type"])} for col in columns],
            }

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
