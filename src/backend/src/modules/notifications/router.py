# Third-party Libraries
from pymongo.asynchronous.database import AsyncDatabase
from fastapi import Depends, Path, Query, APIRouter

# Local Libraries
from src.config.database import get_db
from src.core.dependencies import get_current_user
from src.core.responses import BaseResponse, OffsetPaginatedResponse, OffsetPaginationMeta
from src.modules.notifications.service import NotificationService
from src.modules.notifications.repository import NotificationRepository
from src.modules.notifications.schemas import NotificationResponse


# Router
router = APIRouter(prefix="/notifications", tags=["Notifications"])

def get_notification_service(db: AsyncDatabase = Depends(get_db)) -> NotificationService:
    return NotificationService(NotificationRepository(db))


@router.get("", response_model=OffsetPaginatedResponse[NotificationResponse])
async def fetch_notifications(
    offset: int = Query(0, ge=0, description="Starting position"),
    limit: int = Query(10, gt=0, le=50, description="Quantity taken"),
    current_user: dict = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service)
):
    user_id = current_user["_id"] 
    notifs, meta = await service.fetch_notifications(user_id, offset, limit, unread_only=False)

    return OffsetPaginatedResponse(
        message="Received the success notification",
        data=notifs,
        meta=OffsetPaginationMeta(**meta)
    )


@router.get("/unread", response_model=OffsetPaginatedResponse[NotificationResponse])
async def fetch_unread_notifications(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0, le=50),
    current_user: dict = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service)
):
    user_id = current_user["_id"]
    notifs, meta = await service.fetch_notifications(user_id, offset, limit, unread_only=True)

    return OffsetPaginatedResponse(
        message="Get unread notifications",
        data=notifs,
        meta=OffsetPaginationMeta(**meta)
    )


@router.put("/{notification_id}/read", response_model=BaseResponse[None])
async def read_notification(
    notification_id: str = Path(...),
    current_user: dict = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service)
):
    user_id = current_user["_id"]
    await service.read_notification(user_id, notification_id)

    return BaseResponse(
        message="Marked as read",
        data=None
    )
