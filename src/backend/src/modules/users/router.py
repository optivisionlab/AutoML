# Standard Libraries
import io

# Third-party Libraries
from pymongo.asynchronous.database import AsyncDatabase
from fastapi.responses import StreamingResponse
from fastapi import Depends, Path, Query, Body, APIRouter, UploadFile, File

# Local Libraries
from src.config.database import get_db
from src.core.dependencies import require_admin, require_owner_or_admin
from src.core.responses import BaseResponse, PaginatedResponse, PaginationMeta
from src.modules.users.service import UserService
from src.modules.users.repository import UserRepository
from src.modules.users.schemas import UserResponse, UserDetailResponse, UpdateUserRequest, ChangePasswordRequest


# Router
router = APIRouter(prefix="/users", tags=["Users"])

def get_user_service(db: AsyncDatabase = Depends(get_db)) -> UserService:
    return UserService(UserRepository(db))


@router.get("", dependencies=[Depends(require_admin)], response_model=PaginatedResponse[UserResponse])
async def get_all_users(
    page: int = Query(1, ge=1, description="Current page (starting from 1)"),
    page_size: int = Query(10, ge=1, le=100, description="Number of records per page"),
    service: UserService = Depends(get_user_service)
):
    users_data, meta_data = await service.get_paginated_users(page, page_size)

    return PaginatedResponse(
        message="Get a list of successful users",
        data=users_data,
        meta=PaginationMeta(**meta_data)
    )


@router.get("/{id}", dependencies=[Depends(require_owner_or_admin)], response_model=BaseResponse[UserDetailResponse])
async def get_user_by_id(
    id: str = Path(..., description="The user ID code needs to be viewed in detail"),
    service: UserService = Depends(get_user_service)
):
    user_data = await service.get_user_details(id)

    return BaseResponse(
        message="User details successfully retrieved",
        data=user_data
    )


@router.put("/{id}", dependencies=[Depends(require_owner_or_admin)], response_model=BaseResponse[UserDetailResponse])
async def update_user(
    id: str = Path(..., description="The user ID needs to be updated"),
    payload: UpdateUserRequest = Body(...),
    service: UserService = Depends(get_user_service)
):
    updated_user = await service.update_user_info(id, payload)

    return BaseResponse(
        message="User information updated successfully",
        data=updated_user
    )


@router.delete("/{id}", dependencies=[Depends(require_admin)], response_model=BaseResponse[None])
async def delete_user(
    id: str = Path(..., description="The user ID to be deleted"),
    service: UserService = Depends(get_user_service)
):
    await service.delete_user(id)

    return BaseResponse(
        message="The user and associated data have been deleted",
        data=None
    )


@router.get("/{id}/avatar", dependencies=[Depends(require_owner_or_admin)], response_class=StreamingResponse)
async def get_avatar(
    id: str = Path(..., description="User ID"),
    service: UserService = Depends(get_user_service)
):
    avatar_bytes = await service.get_user_avatar(id)

    return StreamingResponse(
        io.BytesIO(avatar_bytes), 
        media_type="image/png"
    )


@router.post("/{id}/avatar", dependencies=[Depends(require_owner_or_admin)], response_model=BaseResponse[dict])
async def update_avatar(
    id: str = Path(..., description="User ID"),
    file: UploadFile = File(..., description="Uploaded image file"),
    service: UserService = Depends(get_user_service)
):
    avatar_base64 = await service.update_user_avatar(id, file)

    return BaseResponse(
        message="Profile picture updated successfully",
        data={"avatar": avatar_base64}
    )


@router.post("/{id}/password", dependencies=[Depends(require_owner_or_admin)], response_model=BaseResponse[None])
async def change_password(
    id: str = Path(..., description="User ID"),
    payload: ChangePasswordRequest = Body(...),
    service: UserService = Depends(get_user_service)
):
    await service.change_password(id, payload)

    return BaseResponse(
        message="Password changed successfully. Please log in again",
        data=None
    )
