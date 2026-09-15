# Standard Libraries
import asyncio
from typing import Any
from bson import ObjectId

# Third-party Libraries
from pymongo.asynchronous.database import AsyncDatabase


class UserRepository:
    def __init__(self, db: AsyncDatabase):
        self.user_collection = db.tbl_User
        self.linked_accounts_collection = db.linked_accounts

    # User Collection
    async def get_user_by_id(self, user_id: ObjectId) -> dict[str, Any] | None:
        """
        Retrieve user information using ID
        """
        return await self.user_collection.find_one({'_id': user_id})

    async def get_total_users(self) -> int:
        """
        Count the total number of users in the database
        """
        return await self.user_collection.count_documents({})

    async def get_all_users(self, skip: int, limit: int) -> list[dict[str, Any]]:
        """
        Get a list of users by skip and limit
        """
        cursor = self.user_collection.find({}).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def update_user(self, user_id: ObjectId, update_data: dict) -> bool:
        """
        Update user information
        """
        result = await self.user_collection.update_one(
            {'_id': user_id},
            {'$set': update_data}
        )
        return result.modified_count > 0

    async def delete_user_completely(self, user_id: ObjectId) -> bool:
        """
        Permanently delete the user
        """
        delete_user_task = self.user_collection.delete_one({"_id": user_id})
        delete_accounts_task = self.linked_accounts_collection.delete_many({"user_id": user_id})

        results = await asyncio.gather(delete_user_task, delete_accounts_task)
        user_delete_result = results[0]
    
        return user_delete_result.deleted_count > 0

    async def update_avatar(self, user_id: ObjectId, avatar_base64: str) -> bool:
        """
        Update the avatar URL
        """
        result = await self.user_collection.update_one(
            {'_id': user_id},
            {'$set': {'avatar': avatar_base64}}
        )
        return result.modified_count > 0

    async def get_local_password(self, user_id: ObjectId) -> str | None:
        """
        Retrieve passwords from local accounts
        """
        account = await self.linked_accounts_collection.find_one({
            'user_id': user_id,
            'provider': 'local'
        })
        return account.get('password') if account else None

    async def update_password(self, user_id: ObjectId, hashed_password: str) -> bool:
        """
        Update your password
        """
        update_account_task = self.linked_accounts_collection.update_one(
            {"user_id": user_id, "provider": "local"},
            {"$set": {"password": hashed_password}},
            upsert=True 
        )

        update_user_task = self.user_collection.update_one(
            {"_id": user_id},
            {"$unset": {"password": ""}}
        )

        results = await asyncio.gather(update_account_task, update_user_task)

        return results[0].modified_count > 0 or results[0].upserted_id is not None
