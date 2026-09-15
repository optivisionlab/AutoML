# Third-party Libraries
from pymongo.asynchronous.database import AsyncDatabase


class NotificationRepository:
    def __init__(self, db: AsyncDatabase):
        self.__collection = db.tbl_Notification

    # Notification Collection
    async def insert(self, doc: dict) -> None:
        """
        Insert notification
        """
        await self.__collection.insert_one(doc)

    async def count_notifications(self, user_id: str, unread_only: bool = False) -> int:
        """
        Count notifications
        """
        query = {"user_id": user_id}
        if unread_only:
            query["is_read"] = False

        return await self.__collection.count_documents(query)

    async def get_notifications(self, user_id: str, offset: int, limit: int, unread_only: bool = False) -> list[dict]:
        """
        Get notifications
        """
        query = {"user_id": user_id}
        if unread_only:
            query["is_read"] = False

        cursor = self.__collection.find(query).sort("created_at", -1).skip(offset).limit(limit)

        return await cursor.to_list(length=limit)

    async def mark_as_read(self, user_id: str, notification_id: str) -> bool:
        """
        Mark notification
        """
        result = await self.__collection.update_one(
            {"_id": notification_id, "user_id": user_id},
            {"$set": {"is_read": True}}
        )

        return result.modified_count > 0
