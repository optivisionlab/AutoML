# Third-party Libraries
from pymongo.asynchronous.database import AsyncDatabase
from fastapi import Depends, Path, Query, APIRouter

# Local Libraries
from src.core import dependencies, responses
from src.config import databases
from src.modules.notifications.service import NotificationService
from src.modules.notifications.schemas import NotificationResponse
from src.modules.notifications.repository import NotificationRepository


# Router
router = APIRouter(prefix="/notifications", tags=["Notifications"])

def get_notification_service(db: AsyncDatabase = Depends(databases.get_db)) -> NotificationService:
    return NotificationService(NotificationRepository(db))


@router.get("", response_model=responses.OffsetPaginatedResponse[NotificationResponse])
async def fetch_notifications(
    offset: int = Query(0, ge=0, description="Starting position"),
    limit: int = Query(10, gt=0, le=50, description="Quantity taken"),
    current_user: dict = Depends(dependencies.get_current_user),
    service: NotificationService = Depends(get_notification_service)
):
    user_id = current_user["_id"] 
    notifs, meta = await service.fetch_notifications(user_id, offset, limit, unread_only=False)

    return responses.OffsetPaginatedResponse(
        message="Received the success notification",
        data=notifs,
        meta=responses.OffsetPaginationMeta(**meta)
    )


@router.get("/unread", response_model=responses.OffsetPaginatedResponse[NotificationResponse])
async def fetch_unread_notifications(
    offset: int = Query(0, ge=0),
    limit: int = Query(10, gt=0, le=50),
    current_user: dict = Depends(dependencies.get_current_user),
    service: NotificationService = Depends(get_notification_service)
):
    user_id = current_user["_id"]
    notifs, meta = await service.fetch_notifications(user_id, offset, limit, unread_only=True)

    return responses.OffsetPaginatedResponse(
        message="Get unread notifications",
        data=notifs,
        meta=responses.OffsetPaginationMeta(**meta)
    )


@router.put("/{notification_id}/read", response_model=responses.BaseResponse[None])
async def read_notification(
    notification_id: str = Path(...),
    current_user: dict = Depends(dependencies.get_current_user),
    service: NotificationService = Depends(get_notification_service)
):
    user_id = current_user["_id"]
    await service.read_notification(user_id, notification_id)

    return responses.BaseResponse(
        message="Marked as read",
        data=None
    )
