# Standard Libraries
import io
import time
import pickle
import logging
import asyncio
from typing import Any

# Local Libraries
from src.shared import minio_service


# Logging
logger = logging.getLogger(__name__)


class InferenceModelRegistry:
    """
    In-memory Model Registry with LRU caching for low-latency inference serving
    """
    _cache: dict[str, dict[str, Any]] = {}
    _lock = asyncio.Lock()
    _max_cache_size: int = 50

    @classmethod
    async def get_model(cls, job_id: str, storage_info: dict[str, str]) -> Any:
        """
        Retrieve fitted model object from in-memory cache or download from MinIO
        """
        # Fast read from cache
        if job_id in cls._cache:
            cls._cache[job_id]["last_accessed"] = time.time()
            return cls._cache[job_id]["model"]

        async with cls._lock:
            # Double-check after acquiring lock
            if job_id in cls._cache:
                cls._cache[job_id]["last_accessed"] = time.time()
                return cls._cache[job_id]["model"]

            bucket_name = storage_info.get("bucket_name", "models")
            object_name = storage_info.get("object_name")

            if not object_name:
                raise ValueError(f"Storage path for job '{job_id}' is empty or invalid")

            logger.info(f"Cache miss for model job '{job_id}'. Fetching from MinIO: s3://{bucket_name}/{object_name}")
            raw_bytes = await minio_service.get_object(bucket_name, object_name)

            if isinstance(raw_bytes, io.BytesIO):
                raw_bytes = raw_bytes.getvalue()

            model = pickle.loads(raw_bytes)

            # Evict oldest entry if cache exceeds maximum size
            if len(cls._cache) >= cls._max_cache_size:
                oldest_job_id = min(cls._cache.keys(), key=lambda k: cls._cache[k]["last_accessed"])
                cls._cache.pop(oldest_job_id, None)
                logger.info(f"Evicted oldest model '{oldest_job_id}' from memory cache")

            cls._cache[job_id] = {
                "model": model,
                "bucket_name": bucket_name,
                "object_name": object_name,
                "cached_at": time.time(),
                "last_accessed": time.time(),
            }
            logger.info(f"Model for job '{job_id}' successfully cached in memory")
            return model

    @classmethod
    def evict_model(cls, job_id: str) -> bool:
        """
        Remove a specific model from in-memory cache upon deactivation or deletion
        """
        if job_id in cls._cache:
            cls._cache.pop(job_id, None)
            logger.info(f"Model '{job_id}' evicted from memory cache")
            return True
        return False

    @classmethod
    def clear(cls) -> None:
        """
        Clear all cached models from memory
        """
        cls._cache.clear()
        logger.info("InferenceModelRegistry memory cache cleared")
