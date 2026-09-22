# Standard Libraries
import io
import pickle
import logging
import asyncio
from typing import Any

# Third-party Libraries
import pandas as pd

# Local Libraries
from src.shared import minio_service, search_space, MapReduceManager
from src.modules.notifications import NotificationService
from src.modules.preprocessing import TabularPreprocessor, CVStrategyConfig
from src.modules.trainings.tasks import train_single_model_task
from src.modules.trainings.schemas import AutoMLPipelineResult, ModelScoreItem, JobSuccessPayload, ModelStorageInfo
from src.modules.trainings.repository import TrainingRepository


# Logging
logger = logging.getLogger(__name__)


class TrainingService:
    """
    Service handling AutoML distributed training pipeline, model persistence and background training job lifecycle.
    """
    def __init__(self, repo: TrainingRepository, notif_service: NotificationService):
        self.repo = repo
        self.notif_service = notif_service

    # Distributed AutoML Pipeline Helpers
    @staticmethod
    def _prepare_pipeline_inputs(
        df: pd.DataFrame,
        target_col: str,
        feature_cols: list[str] | None
    ) -> tuple[bytes, bytes | None, CVStrategyConfig, list[str]]:
        """
        Preprocess tabular dataset in RAM and serialize data partitions for distributed workers.
        """
        (X_train, y_train), test_data, cv_config, feature_names = TabularPreprocessor.prepare_data(
            df=df,
            target_col=target_col,
            feature_cols=feature_cols,
        )
        logger.info(f"Dataset preprocessed. Applied CV Strategy: {cv_config.description}")

        train_bytes = pickle.dumps((X_train, y_train))
        test_bytes = pickle.dumps(test_data) if test_data is not None else None

        return train_bytes, test_bytes, cv_config, feature_names

    @staticmethod
    async def _dispatch_and_collect_tasks(
        driver: Any,
        models_to_train: list[str],
        custom_params: dict[str, Any],
        train_bytes: bytes,
        test_bytes: bytes | None,
        cv_config: CVStrategyConfig,
        metric_list: list[str],
        metric_sort: str,
    ) -> list[dict[str, Any]]:
        """
        Dispatch parallel training tasks to PyMapReduce cluster and collect results.
        """
        tasks = []
        for model_name in models_to_train:
            if model_name in search_space.CLASSIFICATION_MODELS:
                param_grid = custom_params.get(model_name) or search_space.CLASSIFICATION_MODELS[model_name]
            else:
                logger.warning(f"Model '{model_name}' not in predefined search space, using default.")
                param_grid = [{}]

            task_coro = train_single_model_task.remote(
                model_name,
                param_grid,
                train_bytes,
                test_bytes,
                cv_config,
                metric_list,
                metric_sort,
            )
            tasks.append(task_coro)

        logger.info(f"Dispatched {len(tasks)} parallel model training tasks to PyMapReduce...")
        raw_outputs = await asyncio.gather(*tasks)

        valid_results: list[dict[str, Any]] = []
        for out in raw_outputs:
            if hasattr(out, "object_id"):
                resolved_val = await driver.get(out.object_id)
                if isinstance(resolved_val, dict):
                    valid_results.append(resolved_val)
            elif isinstance(out, dict):
                valid_results.append(out)

        if not valid_results:
            raise ValueError("No successful model training results received from PyMapReduce workers.")

        return valid_results

    @staticmethod
    def _evaluate_and_select_best_model(
        valid_results: list[dict[str, Any]],
        metric_sort: str,
    ) -> tuple[ModelScoreItem, dict[str, Any], float, list[ModelScoreItem]]:
        """
        Extract model scores, rank models according to metric_sort, and identify the best candidate.
        """
        model_scores = [
            ModelScoreItem(
                model_id=idx,
                model_name=res.get("model_name", ""),
                scores=res.get("scores", {}),
                best_params=res.get("best_params", {}),
            )
            for idx, res in enumerate(valid_results)
        ]

        normalized_metric = metric_sort.strip().lower().replace(" ", "_")
        best_model_entry = max(
            model_scores,
            key=lambda x: x.scores.get(normalized_metric, -float("inf")),
        )

        best_raw_result = next(
            r for r in valid_results if r.get("model_name") == best_model_entry.model_name
        )

        best_score = best_model_entry.scores.get(
            normalized_metric,
            best_raw_result.get("primary_score", 0.0),
        )

        return best_model_entry, best_raw_result, best_score, model_scores

    # Main AutoML Pipeline Entrypoint
    @classmethod
    async def train_automl_pipeline(
        cls,
        df: pd.DataFrame,
        target_col: str | None = None,
        feature_cols: list[str] | None = None,
        metric_list: list[str] | None = None,
        metric_sort: str = "accuracy",
        models_to_train: list[str] | None = None,
        custom_params: dict[str, Any] | None = None
    ) -> AutoMLPipelineResult:
        """
        Pure in-memory AutoML training pipeline using PyMapReduce distributed tasks.
        """
        if df is None or df.empty:
            raise ValueError("Input DataFrame is empty or invalid.")

        driver = await MapReduceManager.get_driver()

        # Resolve defaults
        target_col = target_col or str(df.columns[-1])
        metric_list = metric_list or search_space.METRIC_LIST
        models_to_train = models_to_train or list(search_space.CLASSIFICATION_MODELS.keys())
        custom_params = custom_params or {}

        # Preprocess and serialize partitions
        train_bytes, test_bytes, cv_config, feature_names = cls._prepare_pipeline_inputs(
            df=df,
            target_col=target_col,
            feature_cols=feature_cols,
        )

        # Dispatch parallel tasks to cluster
        valid_results = await cls._dispatch_and_collect_tasks(
            driver=driver,
            models_to_train=models_to_train,
            custom_params=custom_params,
            train_bytes=train_bytes,
            test_bytes=test_bytes,
            cv_config=cv_config,
            metric_list=metric_list,
            metric_sort=metric_sort,
        )

        # Rank scores and pick best model
        best_entry, best_raw, best_score, model_scores = cls._evaluate_and_select_best_model(
            valid_results=valid_results,
            metric_sort=metric_sort,
        )

        return AutoMLPipelineResult(
            best_model_id=best_entry.model_id,
            best_model=best_entry.model_name,
            best_params=best_entry.best_params,
            best_score=best_score,
            model_scores=model_scores,
            best_model_bytes=best_raw["model_bytes"],
            cv_strategy=cv_config,
            feature_names=feature_names,
            time_limit_reached=False,
            completed_models=len(valid_results),
            total_models=len(models_to_train),
        )

    # Storage & Notification Lifecycle Helpers
    async def _load_dataset_df(self, dataset_id: str) -> tuple[pd.DataFrame, str]:
        """
        Fetch dataset metadata from DB and load Parquet file from MinIO into pandas DataFrame.
        """
        dataset_doc = await self.repo.get_dataset_info(dataset_id)
        if not dataset_doc or not dataset_doc.get("data_link"):
            raise ValueError(f"Dataset '{dataset_id}' not found or missing storage link.")

        dataset_name = dataset_doc.get("dataName", "Unknown")
        data_link = dataset_doc["data_link"]
        bucket_name = data_link.get("bucket_name")
        object_name = data_link.get("object_name")

        logger.info(f"Downloading dataset from MinIO: s3://{bucket_name}/{object_name}")
        parquet_data = await minio_service.get_object(bucket_name, object_name)
        df = pd.read_parquet(
            parquet_data if isinstance(parquet_data, io.BytesIO) else io.BytesIO(parquet_data)
        )
        return df, dataset_name

    @staticmethod
    async def _save_best_model_artifact(
        user_id: str,
        job_id: str,
        best_model_name: str,
        model_bytes: bytes,
        version: int = 1,
    ) -> tuple[str, ModelStorageInfo]:
        """
        Upload serialized Best Model binary to MinIO models bucket.
        """
        dest_model_path = f"{user_id}/{job_id}/{best_model_name}_{version}.pkl"
        await minio_service.upload_object(
            bucket_name="models",
            object_name=dest_model_path,
            object_bytes=model_bytes,
        )
        storage_info = ModelStorageInfo(bucket_name="models", object_name=dest_model_path)
        return dest_model_path, storage_info

    async def _on_job_success(
        self,
        job_id: str,
        user_id: str,
        dataset_name: str,
        pipeline_result: AutoMLPipelineResult,
        storage_info: ModelStorageInfo,
    ) -> dict[str, Any]:
        """
        Persist training success to database and send push notification.
        """
        final_result_payload = JobSuccessPayload(
            best_model_id=pipeline_result.best_model_id,
            best_model=pipeline_result.best_model,
            model=storage_info,
            best_params=pipeline_result.best_params,
            best_score=pipeline_result.best_score,
            model_scores=pipeline_result.model_scores,
            time_limit_reached=pipeline_result.time_limit_reached,
            completed_models=pipeline_result.completed_models,
            total_models=pipeline_result.total_models,
        )

        await self.repo.update_success(job_id, final_result_payload)

        asyncio.create_task(
            self.notif_service.push_notification(
                user_id=user_id,
                job_id=job_id,
                status="1",
                message=f"Bộ dữ liệu [{dataset_name}] huấn luyện thành công.",
                metadata={
                    "best_model": pipeline_result.best_model,
                    "best_score": pipeline_result.best_score,
                },
            )
        )

        return final_result_payload.model_dump()

    async def _on_job_failure(
        self,
        job_id: str,
        user_id: str,
        dataset_name: str,
        error_msg: str,
    ) -> None:
        """
        Persist training failure to database and send push notification.
        """
        await self.repo.update_failure(job_id, error_msg)

        asyncio.create_task(
            self.notif_service.push_notification(
                user_id=user_id,
                job_id=job_id,
                status="-1",
                message=f"Bộ dữ liệu [{dataset_name}] huấn luyện thất bại.",
                metadata={"error_details": error_msg},
            )
        )

    # Background Training Job Orchestrator
    async def process_training_job(
        self,
        job_id: str,
        dataset_id: str,
        user_id: str,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """
        End-to-end handler for a Kafka training job:
        1. Fetch data from MinIO
        2. Run distributed AutoML pipeline
        3. Save best model to MinIO
        4. Update DB and send notification
        """
        dataset_name = "Unknown"
        try:
            logger.info(f"Processing AutoML Job: ID={job_id}, Dataset={dataset_id}, User={user_id}")

            # Load dataset
            df, dataset_name = await self._load_dataset_df(dataset_id)

            # Extract configuration
            if "config" in config and isinstance(config["config"], dict):
                config = config["config"]

            target_col = config.get("target")
            feature_cols = config.get("features") or config.get("list_feature")
            metric_list = config.get("metrics")
            metric_sort = config.get("metric_sort") or "accuracy"
            models_to_train = config.get("models")
            custom_params = config.get("custom_params")

            # Execute AutoML pipeline
            pipeline_result = await self.train_automl_pipeline(
                df=df,
                target_col=target_col,
                feature_cols=feature_cols,
                metric_list=metric_list,
                metric_sort=metric_sort,
                models_to_train=models_to_train,
                custom_params=custom_params,
            )

            # Save best model artifact to MinIO
            _, storage_info = await self._save_best_model_artifact(
                user_id=user_id,
                job_id=job_id,
                best_model_name=pipeline_result.best_model,
                model_bytes=pipeline_result.best_model_bytes,
            )

            # Record success & notify user
            return await self._on_job_success(
                job_id=job_id,
                user_id=user_id,
                dataset_name=dataset_name,
                pipeline_result=pipeline_result,
                storage_info=storage_info,
            )

        except Exception as e:
            error_msg = f"Training failure: {str(e)}"
            logger.error(f"AutoML Job {job_id} failed: {error_msg}", exc_info=True)
            await self._on_job_failure(
                job_id=job_id,
                user_id=user_id,
                dataset_name=dataset_name,
                error_msg=error_msg,
            )
            raise e
