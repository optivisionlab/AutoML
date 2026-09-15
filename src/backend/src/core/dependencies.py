# Standard Libraries
from bson import ObjectId
from bson.errors import InvalidId

# Third-party Libraries
from fastapi import Depends, status, Path
from fastapi.security import OAuth2PasswordBearer
from pymongo.asynchronous.database import AsyncDatabase

# Local Libraries
from src.config.database import get_db
from src.core.security import jwt_service
from src.core.exceptions import CustomException
from src.shared.constants import ErrorCode


# Define the OAuth2 scheme.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncDatabase = Depends(get_db)
):
    payload = jwt_service.verify_token(token)

    if not payload:
        raise CustomException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            error_code=ErrorCode.UNAUTHORIZED.value,
        )

    try:
        user_id = ObjectId(payload['sub'])
    except InvalidId:
        raise CustomException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication data format",
            error_code=ErrorCode.UNAUTHORIZED,
        )

    user = await db.tbl_User.find_one({'_id': user_id})
    if not user:
        raise CustomException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The account does not exist or has been locked",
            error_code=ErrorCode.UNAUTHORIZED,
        )

    # Standardize IDs
    user['_id'] = str(user['_id'])
    return user


async def require_admin(
    current_user: dict = Depends(get_current_user)
) -> dict:
    if current_user.get("role") != "admin":
        raise CustomException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin privileges required.",
            error_code=ErrorCode.FORBIDDEN 
        )

    return current_user


async def require_owner_or_admin(
    id: str = Path(..., description="The user ID was affected"),
    current_user: dict = Depends(get_current_user)
) -> dict:
    is_owner = current_user.get("_id") == id
    is_admin = current_user.get("role") == "admin"

    if not (is_owner or is_admin):
        raise CustomException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access or modify this account.",
            error_code=ErrorCode.FORBIDDEN
        )

    return current_user
