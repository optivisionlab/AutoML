# Standard Libraries
import asyncio
from typing import Any
from bson import ObjectId

# Third-party Libraries
from pymongo.asynchronous.database import AsyncDatabase


class AuthRepository:
    def __init__(self, db: AsyncDatabase):
        self.user_collection = db.tbl_User
        self.linked_accounts_collection = db.linked_accounts

    # User Collection
    async def check_user_exists(self, email: str, username: str) -> bool:
        """
        Check for duplicate email addresses or usernames 
        """
        existing_user = await self.user_collection.find_one({
            "$or": [
                {"email": email},
                {"username": username}
            ]
        })
        return existing_user is not None

    async def get_user_by_email(self, email: str):
        return await self.user_collection.find_one({"email": email})

    async def create_user(self, user_doc: dict[str, Any]) -> ObjectId:
        """
        Save the user and return the ObjectId
        """
        result = await self.user_collection.insert_one(user_doc)
        return result.inserted_id

    async def update_user(self, user_id: ObjectId, update_data: dict):
        """
        Update user information
        """
        await self.user_collection.update_one(
            {'_id': user_id},
            {'$set': update_data}
        )

    async def get_user_by_id(self, user_id: ObjectId) -> dict[str, Any] | None:
        """
        Retrieve user information using ID
        """
        return await self.user_collection.find_one({'_id': user_id})

    async def get_user_by_login_identifier(self, identifier: str):
        """
        Find users by email or username
        """
        return await self.user_collection.find_one({
            "$or": [
                {"email": identifier},
                {"username": identifier}
            ]
        })

    # Linked Account Collection
    async def get_local_linked_account(self, user_id):
        """
        Get the local linked account using the user's _id
        """
        return await self.linked_accounts_collection.find_one({
            'user_id': user_id,
            'provider': 'local'
        })

    async def create_linked_account(self, linked_account_doc: dict[str, Any]) -> None:
        """
        Save linked account
        """
        await self.linked_accounts_collection.insert_one(linked_account_doc)

    async def get_linked_account(self, user_id: ObjectId, provider: str):
        """
        Find linked accounts
        """
        return await self.linked_accounts_collection.find_one({
            'user_id': user_id,
            'provider': provider
        })

    # OTP In User Collection
    async def update_user_otp(self, user_id: ObjectId, otp: str, expires_at: float):
        """
        Save the OTP code and expiration date to the database
        """
        await self.user_collection.update_one(
            {"_id": user_id},
            {"$set": {
                "otp": otp,
                "createAtOTP": expires_at
            }}
        )

    async def clear_user_otp(self, user_id: ObjectId):
        """
        Clear the OTP code from the database
        """
        await self.user_collection.update_one(
            {"_id": user_id},
            {"$unset": {"otp": "", "createAtOTP": ""}}
        )

    # Password In DB
    async def update_password(self, user_id: ObjectId, hashed_password: str):
        """
        Update password
        """
        update_user_task = self.user_collection.update_one(
            {"_id": user_id},
            {"$unset": {"password": ""}}
        )

        update_account_task = self.linked_accounts_collection.update_one(
            {
                "user_id": user_id, 
                "provider": "local"
            },
            {"$set": {"password": hashed_password}},
            upsert=True 
        )

        await asyncio.gather(update_user_task, update_account_task)
