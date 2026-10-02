# Standard Libraries
import logging
import asyncio
from typing import Any

# Third-party Libraries
import pymapreduce

# Local Libraries
from src.config import settings
from src.shared import MapReduceManager, ModelInferenceActor


# Logging
logger = logging.getLogger(__name__)


class InferenceActorRegistry:
    _actors: dict[str, Any] = {}
    _lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    async def get_or_create_actor(cls, job_id: str, storage_info: dict[str, str]) -> Any:
        if job_id in cls._actors:
            return cls._actors[job_id]

        async with cls._lock:
            if job_id in cls._actors:
                return cls._actors[job_id]

            bucket_name = storage_info.get("bucket_name", "models")
            object_name = storage_info.get("object_name")

            if not object_name:
                raise ValueError(f"Storage path for job '{job_id}' is empty or invalid.")

            await MapReduceManager.get_driver()

            actor_handle = await ModelInferenceActor.remote(
                bucket_name=bucket_name,
                object_name=object_name,
                minio_endpoint=settings.MINIO.ENDPOINT,
                access_key=settings.MINIO.ACCESS_KEY,
                secret_key=settings.MINIO.SECRET_KEY,
                secure=(settings.PROJECT.ENVIRONMENT != "development"),
            )

            cls._actors[job_id] = actor_handle
            return actor_handle

    @classmethod
    async def invoke_actor(cls, job_id: str, storage_info: dict[str, str], method_name: str, *args: Any, **kwargs: Any) -> Any:
        actor = await cls.get_or_create_actor(job_id, storage_info)
        try:
            method = getattr(actor, method_name)
            return await method.remote(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Actor '{job_id}' call '{method_name}' failed ({e}), refreshing instance...")
            await cls.evict_actor(job_id)
            actor = await cls.get_or_create_actor(job_id, storage_info)
            method = getattr(actor, method_name)

            return await method.remote(*args, **kwargs)

    @classmethod
    async def evict_actor(cls, job_id: str) -> bool:
        actor_handle = cls._actors.pop(job_id, None)
        if actor_handle is not None:
            try:
                await pymapreduce.kill(actor_handle)
            except Exception as e:
                logger.warning(f"Error while killing actor for job '{job_id}': {e}")
            return True
        return False

    @classmethod
    async def clear(cls) -> None:
        async with cls._lock:
            for job_id, handle in list(cls._actors.items()):
                try:
                    await pymapreduce.kill(handle)
                except Exception as e:
                    logger.debug(f"Error destroying actor '{job_id}': {e}")
            cls._actors.clear()


# Alias for compatibility
InferenceModelRegistry = InferenceActorRegistry
