# Standard Libraries
import uuid
import asyncio
from datetime import datetime, timezone

# Third-party Libraries
from fastapi import status

# Local Libraries
from src.shared.constants import ErrorCode
from src.shared.mqtt_client import mqtt_service
from src.core.exceptions import CustomException
from src.modules.notifications.schemas import NotificationResponse
from src.modules.notifications.repository import NotificationRepository


class NotificationService:
    def __init__(self, repo: NotificationRepository):
        self.repo = repo

    """
    Push Notification
    """
    async def push_notification(self, user_id: str, job_id: str, status: str, message: str, metadata: dict):
        notif_id = str(uuid.uuid4())

        notification_doc = {
            "_id": notif_id,
            "user_id": user_id,
            "job_id": job_id,
            "status": status, # 1: success, -1: failure, 0: training
            "message": message,
            "metadata": metadata,
            "is_read": False,
            "created_at": datetime.now(timezone.utc).timestamp()
        }

        try:
            await self.repo.insert(notification_doc.copy())
        except Exception as db_err:
            print(f"Exception when save notification to DB: {db_err}")

        mqtt_payload = notification_doc.copy()
        mqtt_payload["id"] = mqtt_payload.pop("_id")
        topic = f"hautoml/users/{user_id}/notifications"

        await mqtt_service.publish(topic=topic, payload=mqtt_payload, qos=1)

        return notif_id

    """
    Fetch Notifications
    """
    async def fetch_notifications(self, user_id: str, offset: int, limit: int, unread_only: bool = False) -> tuple[list[NotificationResponse], dict]:
        total_items_task = self.repo.count_notifications(user_id, unread_only)
        raw_notifs_task = self.repo.get_notifications(user_id, offset, limit, unread_only)

        total_items, raw_notifs = await asyncio.gather(total_items_task, raw_notifs_task)

        formatted_notifs = [NotificationResponse(**notif) for notif in raw_notifs]

        has_more = (offset + limit) < total_items
        meta_data = {
            "offset": offset,
            "limit": limit,
            "total_items": total_items,
            "has_more": has_more
        }

        return formatted_notifs, meta_data

    """
    Read Notification
    """
    async def read_notification(self, user_id: str, notification_id: str) -> None:
        success = await self.repo.mark_as_read(user_id, notification_id)

        if not success:
            raise CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Notification not found or already read",
                error_code=ErrorCode.NOT_FOUND
            )
