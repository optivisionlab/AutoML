# Standard Libraries
from typing import Any

# Third-party Libraries
from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase


def _oid(value: str) -> ObjectId | None:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        return None


class ConnectionRepository:
    """
    Kết nối đã lưu (tbl_DatabaseConnection) và bản xem trước truy vấn (tbl_DatabasePreview).
    Mọi truy vấn lọc theo CẢ _id và userId: kết nối của người khác coi như không tồn tại.
    """

    def __init__(self, db: AsyncDatabase):
        self.__connections = db.tbl_DatabaseConnection
        self.__previews = db.tbl_DatabasePreview

    # ------------------------------------------------------------- kết nối
    async def create(self, doc: dict) -> dict:
        result = await self.__connections.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    async def list_by_user(self, user_id: str, skip: int, limit: int) -> tuple[list[dict], int]:
        query = {"userId": user_id}
        total = await self.__connections.count_documents(query)
        cursor = self.__connections.find(query).sort("updated_at", -1).skip(skip).limit(limit)
        return [doc async for doc in cursor], total

    async def get(self, connection_id: str, user_id: str) -> dict | None:
        oid = _oid(connection_id)
        if oid is None:
            return None
        return await self.__connections.find_one({"_id": oid, "userId": user_id})

    async def update(self, connection_id: str, user_id: str, fields: dict, now: float) -> dict | None:
        oid = _oid(connection_id)
        if oid is None:
            return None
        return await self.__connections.find_one_and_update(
            {"_id": oid, "userId": user_id},
            {"$set": {**fields, "updated_at": now}, "$inc": {"version": 1}},
            return_document=ReturnDocument.AFTER,
        )

    async def delete(self, connection_id: str, user_id: str) -> bool:
        oid = _oid(connection_id)
        if oid is None:
            return False
        result = await self.__connections.delete_one({"_id": oid, "userId": user_id})
        if result.deleted_count:
            await self.__previews.delete_many({"connection_id": connection_id, "userId": user_id})
        return bool(result.deleted_count)

    # ------------------------------------------------------------- bản xem trước
    async def create_preview(self, doc: dict) -> dict:
        result = await self.__previews.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    async def prune_previews(self, user_id: str, expired_before: float, keep: int) -> None:
        """
        Dọn bản xem trước của MỘT người dùng (gọi trước mỗi lần tạo preview mới): bỏ bản hết hạn từ trước
        `expired_before`, và chỉ giữ `keep` bản mới nhất. Không đụng bản đang nhập (import_state=running).
        Không có bước này thì mỗi lần preview thêm một document chứa truy vấn - kho phình vô hạn.
        """
        idle = {"userId": user_id, "import_state": {"$ne": "running"}}
        await self.__previews.delete_many({**idle, "expires_at": {"$lt": expired_before}})
        extra = [doc["_id"] async for doc in self.__previews.find(idle, {"_id": 1}).sort("created_at", -1).skip(keep)]
        if extra:
            # Kiểm lại trạng thái lúc xoá: một import có thể vừa nhận chỗ (running) sau khi tìm ở trên.
            await self.__previews.delete_many({"_id": {"$in": extra}, "import_state": {"$ne": "running"}})

    async def get_preview(self, preview_id: str, user_id: str) -> dict | None:
        oid = _oid(preview_id)
        if oid is None:
            return None
        return await self.__previews.find_one({"_id": oid, "userId": user_id})

    async def claim_preview_import(self, preview_id: str, user_id: str, now: float, lease_seconds: float,
                                   token: str) -> dict | None:
        """
        Giữ chỗ nhập cho đúng một yêu cầu (nguyên tử), có HẠN: tiến trình nhập chết giữa chừng thì
        sau lease_seconds lần thử lại được nhận việc. `token` định danh lượt đang giữ chỗ: lượt cũ
        bị chiếm chỗ không ghi đè được kết quả của lượt mới. Trả bản ghi nếu giữ chỗ được.
        """
        oid = _oid(preview_id)
        if oid is None:
            return None
        return await self.__previews.find_one_and_update(
            {"_id": oid, "userId": user_id, "$or": [
                {"import_state": None},
                {"import_state": "running", "claimed_at": {"$lt": now - lease_seconds}},
            ]},
            {"$set": {"import_state": "running", "claimed_at": now, "claim_token": token}},
            return_document=ReturnDocument.AFTER,
        )

    async def finish_preview_import(self, preview_id: str, user_id: str, result: dict[str, Any] | None,
                                    token: str | None = None) -> None:
        """
        result=None: nhập lỗi - trả chỗ để thử lại. Có token thì chỉ lượt ĐANG giữ chỗ mới ghi được
        (lượt cũ quá hạn không xoá / ghi đè trạng thái của lượt mới).
        """
        oid = _oid(preview_id)
        query: dict[str, Any] = {"_id": oid, "userId": user_id}
        if token is not None:
            query["claim_token"] = token
        update = {"$set": {"import_state": "done", "import_result": result}} if result else {"$set": {"import_state": None}}
        await self.__previews.update_one(query, update)
