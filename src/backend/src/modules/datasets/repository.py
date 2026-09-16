# Standard Libraries
from typing import Any
from bson import ObjectId

# Third-party Libraries
from pymongo.asynchronous.database import AsyncDatabase


class DatasetRepository:
    def __init__(self, db: AsyncDatabase):
        self.__collection = db.tbl_Data

    # Data Collection
    async def get_datasets_with_count(self, user_id: str, skip: int, limit: int, data_type: str | None = None, sort_params: list[tuple] | None = None) -> tuple[list[dict], int]:
        """
        Retrieving user datasets
        """
        filter_query: dict[str, Any] = {
            "userId": user_id,
            "activate": 1
        }

        if data_type:
            filter_query["dataType"] = data_type

        total_items = await self.__collection.count_documents(filter_query)

        projection = {
            "userId": 0,
            "username": 0,
            "role": 0,
            "data_link": 0
        }

        cursor = self.__collection.find(filter_query, projection=projection)

        if sort_params:
            cursor = cursor.sort(sort_params)

        cursor = cursor.skip(skip).limit(limit)
        datasets = await cursor.to_list(length=limit)

        return datasets, total_items

    async def get_all_datasets_with_count(self, skip: int, limit: int, data_type: str | None = None, sort_params: list[tuple] | None = None) -> tuple[list[dict], int]:
        """
        Retrieve all datasets
        """
        filter_query: dict[str, Any] = {
            "activate": 1
        }

        if data_type:
            filter_query["dataType"] = data_type

        total_items = await self.__collection.count_documents(filter_query)

        projection = {
            "data_link": 0
        }

        cursor = self.__collection.find(filter_query, projection=projection)

        if sort_params:
            cursor = cursor.sort(sort_params)

        cursor = cursor.skip(skip).limit(limit)
        datasets = await cursor.to_list(length=limit)

        return datasets, total_items

    async def get_dataset_by_id(self, dataset_id: ObjectId, user_id: str) -> dict | None:
        """
        Retrieve detail dataset
        """
        filter_query: dict[str, Any] = {
            "_id": dataset_id,
            "userId": user_id,
            "activate": 1
        }

        projection = {
            "userId": 0, 
            "username": 0, 
            "role": 0, 
            "data_link": 0
        }

        dataset = await self.__collection.find_one(filter_query, projection=projection)

        return dataset

    async def create_dataset(self, dataset_doc: dict[str, Any]) -> dict[str, Any]:
        """
        Save metadata
        """
        result = await self.__collection.insert_one(dataset_doc)
        dataset_doc["_id"] = result.inserted_id

        return dataset_doc

    async def update_dataset(self, dataset_id: ObjectId, user_id: str, update_data: dict[str, Any]) -> bool:
        """
        Update metadata
        """
        filter_query = {
            "_id": dataset_id,
            "userId": user_id,
            "activate": 1
        }

        result = await self.__collection.update_one(filter_query, {"$set": update_data})
        return result.modified_count > 0

    async def delete_dataset(self, dataset_id: ObjectId, user_id: str) -> bool:
        """
        Soft delete dataset
        """
        filter_query = {
            "_id": dataset_id,
            "userId": user_id,
            "activate": 1
        }

        result = await self.__collection.update_one(filter_query, {"$set": {"activate": 0}})
        return result.modified_count > 0
