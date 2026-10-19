# Standard Libraries
import uuid
import math
import base64
from bson import ObjectId
from bson.errors import InvalidId

# Third-party Libraries
from fastapi import UploadFile, status

# Local Libraries
from src.core import exceptions, constants
from src.shared import backblaze_service
from src.modules.users.schemas import UserResponse, UserDetailResponse, UpdateUserRequest, ChangePasswordRequest
from src.modules.users.repository import UserRepository


class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    """
    Retrieve the user
    """
    async def get_user_details(self, user_id: str) -> UserDetailResponse:
        try:
            user_id = ObjectId(user_id)
        except InvalidId:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID format",
                error_code=constants.ErrorCode.BAD_REQUEST,
            )

        user = await self.repo.get_user_by_id(user_id)

        if not user:
            raise exceptions.CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User information not found",
                error_code=constants.ErrorCode.NOT_FOUND
            )

        user['_id'] = str(user['_id'])

        return UserDetailResponse(**user)

    """
    Get Paginated Users
    """
    async def get_paginated_users(self, page: int, page_size: int) -> tuple[list[UserResponse], dict]:
        total_items = await self.repo.get_total_users()

        total_pages = math.ceil(total_items / page_size) if total_items > 0 else 0
        skip = (page - 1) * page_size

        users = await self.repo.get_all_users(skip=skip, limit=page_size)

        for user in users:
            user['_id'] = str(user['_id'])

        user_responses = [UserResponse(**user) for user in users]

        # Meta Data
        meta_data = {
            "total_items": total_items,
            "current_page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }

        return user_responses, meta_data

    """
    Update User
    """
    async def update_user_info(self, user_id: str, payload: UpdateUserRequest) -> UserDetailResponse:
        try:
            oid = ObjectId(user_id)
        except InvalidId:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID format",
                error_code=constants.ErrorCode.BAD_REQUEST,
            )

        update_data = payload.model_dump(exclude_unset=True)

        if not update_data:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No data is provided for updating",
                error_code=constants.ErrorCode.BAD_REQUEST
            )

        is_updated = await self.repo.update_user(oid, update_data)

        if is_updated:
            return await self.get_user_details(user_id)

        user_exists = await self.repo.get_user_by_id(oid)
        if not user_exists:
            raise exceptions.CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No user found",
                error_code=constants.ErrorCode.NOT_FOUND
            )

        return await self.get_user_details(user_id)

    """
    Permanently Delete The User
    """
    async def delete_user(self, user_id: str) -> None:
        try:
            oid = ObjectId(user_id)
        except InvalidId:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID format",
                error_code=constants.ErrorCode.BAD_REQUEST,
            )

        is_deleted = await self.repo.delete_user_completely(oid)

        if not is_deleted:
            raise exceptions.CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No user found to delete",
                error_code=constants.ErrorCode.NOT_FOUND
            )

    """
    Get Avatar
    """
    async def get_user_avatar(self, user_id: str) -> bytes:
        try:
            oid = ObjectId(user_id)
        except InvalidId:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID format",
                error_code=constants.ErrorCode.BAD_REQUEST,
            )

        user = await self.repo.get_user_by_id(oid)
        if not user:
            raise exceptions.CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No user found",
                error_code=constants.ErrorCode.NOT_FOUND
            )

        avatar_val = user.get('avatar')
        if not avatar_val:
            raise exceptions.CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="This user has not updated their profile picture",
                error_code=constants.ErrorCode.NOT_FOUND
            )

        # Backblaze storage reference
        if avatar_val.startswith("avatars/"):
            try:
                buffer = await backblaze_service.get_object(avatar_val)
                return buffer.getvalue()
            except Exception as e:
                raise exceptions.CustomException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to retrieve avatar image from storage",
                    error_code=constants.ErrorCode.INTERNAL_SERVER_ERROR
                )

        # Backward compatibility for legacy Base64 avatar strings
        try:
            raw_b64 = avatar_val
            if "," in raw_b64:
                raw_b64 = raw_b64.split(",")[1]

            return base64.b64decode(raw_b64)
        except Exception as e:
            raise exceptions.CustomException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"The image data is corrupted: {str(e)}",
                error_code=constants.ErrorCode.INTERNAL_SERVER_ERROR
            )

    async def update_user_avatar(self, user_id: str, file: UploadFile) -> str:
        try:
            oid = ObjectId(user_id)
        except InvalidId:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID format",
                error_code=constants.ErrorCode.BAD_REQUEST,
            )

        user_exists = await self.repo.get_user_by_id(oid)
        if not user_exists:
            raise exceptions.CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No user found",
                error_code=constants.ErrorCode.NOT_FOUND
            )

        if not file.content_type or not file.content_type.startswith("image/"):
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only image file uploads are supported",
                error_code=constants.ErrorCode.BAD_REQUEST
            )

        old_avatar = user_exists.get("avatar")

        file_extension = file.filename.split(".")[-1] if file.filename and "." in file.filename else "png"
        object_name = f"avatars/{user_id}/avatar_{uuid.uuid4().hex[:8]}.{file_extension}"

        if hasattr(file.file, "seek"):
            file.file.seek(0)

        await backblaze_service.upload_file_stream(
            object_name=object_name,
            file_obj=file.file,
            content_type=file.content_type
        )

        # Update MongoDB with Backblaze object path (replacing legacy base64)
        await self.repo.update_avatar(oid, object_name)

        # Clean up old object in Backblaze if applicable
        if old_avatar and isinstance(old_avatar, str) and old_avatar.startswith("avatars/"):
            await backblaze_service.remove_object(old_avatar)

        return object_name

    """
    Update Password
    """
    async def change_password(self, user_id: str, payload: ChangePasswordRequest) -> None:
        try:
            oid = ObjectId(user_id)
        except InvalidId:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID format",
                error_code=constants.ErrorCode.BAD_REQUEST,
            )

        hashed_old_password = await self.repo.get_local_password(oid)
        if not hashed_old_password:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This account does not have a password set",
                error_code=constants.ErrorCode.BAD_REQUEST
            )

        if payload.old_password != hashed_old_password:
            raise exceptions.CustomException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="The current password is incorrect",
                error_code=constants.ErrorCode.UNAUTHORIZED
            )

        if payload.old_password == payload.new_password:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The new password must not be the same as the current password",
                error_code=constants.ErrorCode.BAD_REQUEST
            )

        await self.repo.update_password(oid, payload.new_password)
