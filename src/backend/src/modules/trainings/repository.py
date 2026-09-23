# Standard Libraries
from typing import Any
from bson import ObjectId
from bson.errors import InvalidId

# Third-party Libraries
from pymongo.asynchronous.database import AsyncDatabase

# Local Libraries
from src.modules.trainings.schemas import JobSuccessPayload


class TrainingRepository:
    def __init__(self, db: AsyncDatabase):
        self.__job_collection = db.tbl_Job
        self.__data_collection = db.tbl_Data

    async def get_job_by_id(self, job_id: str) -> dict[str, Any] | None:
        """
        Retrieve job document by ID
        """
        try:
            query = {"_id": ObjectId(job_id)}
        except (InvalidId, TypeError):
            query = {"_id": job_id}

        return await self.__job_collection.find_one(query)

    async def get_dataset_info(self, dataset_id: str) -> dict[str, Any] | None:
        """
        Retrieve dataset storage metadata
        """
        try:
            query = {"_id": ObjectId(dataset_id), "activate": 1}
        except (InvalidId, TypeError):
            query = {"_id": dataset_id, "activate": 1}

        return await self.__data_collection.find_one(
            query,
            projection={"data_link": 1, "dataName": 1}
        )

    async def update_status(self, job_id: str, status: int) -> bool:
        """
        Update job running status
        """
        try:
            query = {"_id": ObjectId(job_id)}
        except (InvalidId, TypeError):
            query = {"_id": job_id}

        result = await self.__job_collection.update_one(query, {"$set": {"status": status}})
        return result.modified_count > 0

    async def update_failure(self, job_id: str, error_msg: str) -> None:
        """
        Update job state to failed (status = -1) with error information
        """
        try:
            query = {"_id": ObjectId(job_id)}
        except (InvalidId, TypeError):
            query = {"_id": job_id}

        update_data = {
            "$set": {
                "status": -1,
                "infor": error_msg
            }
        }
        await self.__job_collection.update_one(query, update_data)

    async def update_success(self, job_id: str, final_result: JobSuccessPayload | dict[str, Any]) -> None:
        """
        Update job state to completed (status = 1) with final AutoML model evaluation metrics
        """
        try:
            query = {"_id": ObjectId(job_id)}
        except (InvalidId, TypeError):
            query = {"_id": job_id}

        if isinstance(final_result, JobSuccessPayload):
            payload_dict = final_result.model_dump()
        else:
            payload_dict = final_result

        model_info = payload_dict.get("model", {})
        update_data = {
            "$set": {
                "best_model_id": payload_dict["best_model_id"],
                "best_model": payload_dict["best_model"],
                "model": {
                    "bucket_name": model_info.get("bucket_name", "") if isinstance(model_info, dict) else getattr(model_info, "bucket_name", ""),
                    "object_name": model_info.get("object_name", "") if isinstance(model_info, dict) else getattr(model_info, "object_name", "")
                },
                "best_params": payload_dict["best_params"],
                "best_score": payload_dict["best_score"],
                "orther_model_scores": payload_dict["model_scores"],
                "status": 1,
                "time_limit_reached": payload_dict.get("time_limit_reached", False),
                "completed_models": payload_dict.get("completed_models"),
                "total_models": payload_dict.get("total_models")
            }
        }
        await self.__job_collection.update_one(query, update_data)

    async def update_activation(self, job_id: str, activate: int) -> bool:
        """
        Update job model deployment activation status (1 for active, 0 for inactive)
        """
        try:
            query = {"_id": ObjectId(job_id)}
        except (InvalidId, TypeError):
            query = {"_id": job_id}

        result = await self.__job_collection.update_one(query, {"$set": {"activate": activate}})
        return result.modified_count > 0

    async def get_jobs_with_count(
        self,
        user_id: str,
        skip: int,
        limit: int,
        activate: int | None = None,
        data_name: str | None = None,
        sort_params: list[tuple] | None = None,
        is_admin: bool = False,
    ) -> tuple[list[dict[str, Any]], int]:
        """
        Retrieve paginated list of jobs with optional activation, data name filter, and sorting.
        """
        filter_query: dict[str, Any] = {}
        if not is_admin:
            filter_query["user.id"] = user_id

        if activate is not None:
            filter_query["activate"] = activate

        if data_name:
            filter_query["data.name"] = {"$regex": data_name, "$options": "i"}

        total_items = await self.__job_collection.count_documents(filter_query)

        cursor = self.__job_collection.find(filter_query)
        if sort_params:
            cursor = cursor.sort(sort_params)

        cursor = cursor.skip(skip).limit(limit)
        jobs = await cursor.to_list(length=limit)

        return jobs, total_items
