"""
Nguồn NoSQL: MongoDB, CHỈ ĐỌC (find / aggregate đã qua query_policy.validate_mongo_query).

Không kế thừa BaseDatabaseAdapter (lớp đó dựa trên SQLAlchemy). Host phải nằm trong
DB_SOURCE_MONGO_ALLOWED_HOSTS (chặn SSRF tới máy nội bộ); không cho đọc database hệ thống.
Tài khoản kết nối nên chỉ có quyền `read` - bộ kiểm toán tử không thay được quyền của server.
"""
# Standard Libraries
from typing import Any

# Local Libraries
from src.adapters.query_policy import validate_mongo_query
from src.adapters.query_runner import MAX_COLUMNS, QueryFailedError, QueryResult, QueryTimeoutError, SourceAccessError


SYSTEM_DATABASES = {"admin", "local", "config"}


def _flatten_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return type(value).__name__


def normalize_document(doc: dict) -> dict:
    """
    Kiểu BSON -> kiểu Python thường: ObjectId -> chuỗi, Decimal128 -> decimal.Decimal (giữ đủ
    chính xác; lúc nhập mới đổi và ghi chú). Ngày giờ giữ nguyên datetime. json_safe lo phần hiển thị.
    """
    from bson import ObjectId  # noqa: PLC0415
    from bson.decimal128 import Decimal128  # noqa: PLC0415
    from bson.int64 import Int64  # noqa: PLC0415

    def convert(value):
        if isinstance(value, ObjectId):
            return str(value)
        if isinstance(value, Decimal128):
            return value.to_decimal()
        if isinstance(value, Int64):
            return int(value)          # BSON int64 là lớp con của int: đưa về int thường
        if isinstance(value, dict):
            return {str(k): convert(v) for k, v in value.items()}
        if isinstance(value, list):
            return [convert(v) for v in value]
        return value

    return {str(k): convert(v) for k, v in doc.items()}


class MongoSource:
    """Một kết nối MongoDB chỉ đọc tới đúng một database."""

    def __init__(
        self,
        database: str,
        host: str | None = "localhost",
        port: int | None = None,
        username: str | None = None,
        password: str | None = None,
        allowed_hosts: set[str] | None = None,
        timeout: float = 10.0,
        client: Any = None,
        forbidden_databases: set[str] | None = None,
    ):
        forbidden = {d.lower() for d in SYSTEM_DATABASES | set(forbidden_databases or ())}
        if not database or database.lower() in forbidden or "$" in database:
            raise SourceAccessError("Không được đọc database hệ thống hay database của chính HAutoML.")
        self.database_name = database
        self.timeout_ms = int(timeout * 1000)
        if client is None:
            host = (host or "localhost").strip()
            if allowed_hosts is not None and host.lower() not in allowed_hosts:
                raise SourceAccessError(f"Host MongoDB '{host}' không nằm trong danh sách được phép.")
            from pymongo import MongoClient  # noqa: PLC0415

            client = MongoClient(
                host=host,
                port=int(port or 27017),
                username=username or None,
                password=password or None,
                authSource=database if username else None,
                serverSelectionTimeoutMS=min(self.timeout_ms, 5000),
                connectTimeoutMS=min(self.timeout_ms, 5000),
                socketTimeoutMS=self.timeout_ms + 2000,
                readPreference="secondaryPreferred",
            )
        self.client = client
        self.db = client[database]

    def close(self) -> None:
        try:
            self.client.close()
        except Exception:  # noqa: BLE001 - đóng kết nối không được làm hỏng kết quả
            pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _call(self, func, *args, **kwargs):
        from pymongo import errors  # noqa: PLC0415

        try:
            return func(*args, **kwargs)
        except errors.ExecutionTimeout:
            raise QueryTimeoutError(f"Truy vấn chạy quá {self.timeout_ms / 1000:g} giây và đã bị huỷ.") from None
        except (errors.ServerSelectionTimeoutError, errors.ConnectionFailure, errors.ConfigurationError):
            raise SourceAccessError("Không kết nối được MongoDB.") from None
        except errors.OperationFailure as error:
            message = str(error.details.get("errmsg") if error.details else error)
            raise QueryFailedError(f"MongoDB báo lỗi: {message[:500]}") from None

    def list_tables(self) -> list[str]:
        names = self._call(self.db.list_collection_names)
        return sorted(n for n in names if not n.startswith("system."))

    def _read(self, cursor, max_bytes: int) -> list[dict]:
        """
        Đọc cursor TỪNG DOCUMENT, cộng kích thước BSON và dừng ngay khi vượt trần - không nạp hết
        rồi mới đo (nhiều document lớn làm backend hết RAM trước khi kịp kiểm).
        """
        import bson  # noqa: PLC0415

        docs, total = [], 0
        for doc in cursor:
            total += len(bson.encode(doc))
            if total > max_bytes:
                raise QueryFailedError(
                    f"Kết quả quá lớn (vượt {max_bytes // (1024 * 1024)} MiB) - chọn bớt trường / dòng."
                )
            docs.append(doc)
        return docs

    def describe(self, collection: str, sample_rows: int, max_bytes: int = 8 * 1024 * 1024) -> dict:
        if collection not in self.list_tables():
            raise QueryFailedError(f"Collection '{collection}' không tồn tại.")
        docs = self._call(lambda: self._read(self.db[collection].find({}, limit=sample_rows, batch_size=sample_rows), max_bytes))
        types: dict[str, set[str]] = {}
        for doc in docs:
            for key, value in doc.items():
                types.setdefault(str(key), set()).add(_flatten_type(value))
        columns = [{"name": k, "type": "|".join(sorted(v)), "nullable": "null" in v} for k, v in types.items()]
        return {"columns": columns, "rows": [normalize_document(d) for d in docs], "schema_inferred": True}

    def execute(self, query: dict, cap: int, max_bytes: int = 8 * 1024 * 1024) -> QueryResult:
        spec = validate_mongo_query(query)
        if spec["collection"] not in self.list_tables():
            raise QueryFailedError(f"Collection '{spec['collection']}' không tồn tại.")
        collection = self.db[spec["collection"]]
        if spec["kind"] == "find":
            def run():
                cursor = collection.find(spec["filter"], spec["projection"] or None, limit=cap + 1, batch_size=100)
                if spec["sort"]:
                    cursor = cursor.sort(list(spec["sort"].items()))
                if hasattr(cursor, "max_time_ms"):
                    cursor = cursor.max_time_ms(self.timeout_ms)
                return self._read(cursor, max_bytes)
        else:
            pipeline = list(spec["pipeline"]) + [{"$limit": cap + 1}]

            def run():
                try:
                    cursor = collection.aggregate(pipeline, maxTimeMS=self.timeout_ms, allowDiskUse=False, batchSize=100)
                except TypeError:  # mongomock không nhận các tuỳ chọn này
                    cursor = collection.aggregate(pipeline)
                return self._read(cursor, max_bytes)
        docs = self._call(run)
        rows = [normalize_document(d) for d in docs]
        columns: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    seen.add(key)
                    columns.append(key)
                    if len(columns) > MAX_COLUMNS:
                        raise QueryFailedError(
                            f"Các document có hơn {MAX_COLUMNS} trường khác nhau - dùng $project chọn trường cần lấy."
                        )
        truncated = len(rows) > cap
        # Giữ hàng THƯA (thiếu trường = không có khoá): điền đủ mọi cột cho mọi hàng thì document
        # mỗi cái một trường riêng nở thành bảng hàng triệu ô ngay trong backend.
        return QueryResult(columns=columns, rows=rows[:cap], truncated=truncated)
