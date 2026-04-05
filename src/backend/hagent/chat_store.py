"""
HAgent — Quản lý lịch sử chat (MongoDB, DB chính AutoML)

Lưu trữ và truy xuất lịch sử hội thoại trong collection `hagent_conversations`
thuộc database AutoML (dùng chung với backend chính).
"""

import uuid
from datetime import datetime, timezone

from pymongo import ASCENDING


# ─── Collection name ─────────────────────────────────────
COLLECTION = "hagent_conversations"


def _col(db):
    """Lấy collection conversations từ DB."""
    return db[COLLECTION]


async def ensure_indexes(db):
    """Tạo các index cần thiết (gọi 1 lần khi startup)."""
    col = _col(db)
    await col.create_index(
        [("user_id", ASCENDING), ("conversation_id", ASCENDING)],
        unique=True,
    )
    await col.create_index([("user_id", ASCENDING), ("updated_at", ASCENDING)])


async def add_message(
    db,
    conversation_id: str,
    user_id: str,
    role: str,
    content: str,
    provider: str = "",
    model: str = "",
) -> None:
    """Thêm một tin nhắn vào cuộc hội thoại. Tạo mới nếu chưa tồn tại."""
    now = datetime.now(timezone.utc)
    message = {
        "role": role,
        "content": content,
        "timestamp": now,
        "provider": provider,
        "model": model,
    }

    update_fields = {
        "$push": {"messages": message},
        "$set": {"updated_at": now},
    }
    if provider:
        update_fields["$set"]["provider"] = provider
    if model:
        update_fields["$set"]["model"] = model

    result = await _col(db).update_one(
        {"conversation_id": conversation_id, "user_id": user_id},
        update_fields,
    )

    # Nếu cuộc hội thoại chưa tồn tại, tạo mới
    if result.matched_count == 0:
        doc = {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "messages": [message],
            "created_at": now,
            "updated_at": now,
            "provider": provider,
            "model": model,
        }
        await _col(db).insert_one(doc)


async def get_message_history(
    db, conversation_id: str, user_id: str, limit: int = 50
) -> list[dict]:
    """Lấy danh sách tin nhắn gần nhất từ cuộc hội thoại."""
    doc = await _col(db).find_one(
        {"conversation_id": conversation_id, "user_id": user_id},
    )
    if doc is None:
        return []
    messages = doc.get("messages", [])
    return messages[-limit:]


async def delete_conversation(db, conversation_id: str, user_id: str) -> bool:
    """Xóa cuộc hội thoại. Trả về True nếu xóa thành công."""
    result = await _col(db).delete_one({
        "conversation_id": conversation_id,
        "user_id": user_id,
    })
    return result.deleted_count > 0


async def list_conversations(db, user_id: str, limit: int = 20) -> list[dict]:
    """Liệt kê các cuộc hội thoại gần nhất (chỉ tóm tắt)."""
    cursor = _col(db).find(
        {"user_id": user_id},
        {
            "conversation_id": 1,
            "created_at": 1,
            "updated_at": 1,
            "provider": 1,
            "model": 1,
            "messages": {"$slice": -1},
        },
    ).sort("updated_at", -1).limit(limit)

    results = []
    async for doc in cursor:
        last_msg = doc.get("messages", [{}])
        results.append({
            "conversation_id": doc["conversation_id"],
            "updated_at": doc["updated_at"].isoformat() if doc.get("updated_at") else "",
            "created_at": doc["created_at"].isoformat() if doc.get("created_at") else "",
            "provider": doc.get("provider", ""),
            "preview": last_msg[0].get("content", "")[:100] if last_msg else "",
        })
    return results
