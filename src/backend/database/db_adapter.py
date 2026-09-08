import pandas as pd
from sqlalchemy import create_engine, inspect, text
from typing import List, Dict, Any

class DatabaseAdapter:
    def __init__(self, db_type: str, host: str, port: int, user: str, password: str, database: str):
        self.db_type = db_type.lower().strip()
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.engine = self._create_engine()

    def _create_engine(self):
        """Tạo SQLAlchemy engine dựa trên loại Database người dùng chọn"""
        if self.db_type in ["postgres", "postgresql"]:
            url = f"postgresql+psycopg2://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
        elif self.db_type == "mysql":
            url = f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
        else:
            raise ValueError(f"Loại cơ sở dữ liệu '{self.db_type}' chưa được hỗ trợ.")
        
        # Đặt timeout = 5 giây để nếu gõ sai IP/Port thì ngắt ngay, không làm treo server
        return create_engine(url, connect_args={"connect_timeout": 5})

    def test_connection_and_get_tables(self) -> List[str]:
        """
        Kiểm tra kết nối và trả về danh sách các bảng.
        Dùng khi người dùng bấm nút 'Kết nối' trên giao diện.
        """
        with self.engine.connect() as conn:
            inspector = inspect(conn)
            tables = inspector.get_table_names()
            return tables

    def fetch_table_to_dataframe(self, table_name: str, limit: int = 50000) -> pd.DataFrame:
        """
        Lấy dữ liệu của 1 bảng chuyển thành pandas.DataFrame.
        Dùng khi người dùng chọn 1 bảng và bấm 'Lấy dữ liệu'.
        """
        query = f"SELECT * FROM {table_name} LIMIT {limit}"
        df = pd.read_sql(query, con=self.engine)
        return df
