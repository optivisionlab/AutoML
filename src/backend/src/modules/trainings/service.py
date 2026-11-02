# Standard Libraries
import io
import pickle
import logging
import asyncio
from typing import Any, Awaitable, Callable

# Third-party Libraries
import pandas as pd
from sklearn.base import BaseEstimator

# Local Libraries
from src.core import search_space, constants
from src.shared import minio_service, MapReduceManager
from src.modules.notifications import NotificationService
from src.modules.preprocessing import TabularPreprocessor, FittedPreprocessor, CVStrategyConfig, TimeSeriesForecaster
from src.modules.trainings.tasks import train_single_model_task
from src.modules.trainings.schemas import (
    AutoMLPipelineResult,
    ModelScoreItem,
    JobSuccessPayload,
    ModelStorageInfo,
)
from src.modules.trainings.repository import TrainingRepository
from src.modules.trainings.pipeline import PipelineTracker


# Logging
logger = logging.getLogger(__name__)


def _column_types(preprocessor: FittedPreprocessor) -> dict[str, list[str]]:
    """
    Feature columns per transformer group (num / cat / text_<col>) of the fitted ColumnTransformer
    """
    column_types: dict[str, list[str]] = {"numeric": [], "categorical": [], "text": []}
    transformer = getattr(preprocessor, "preprocessor", None)
    for name, _, columns in getattr(transformer, "transformers_", []):
        if name == "num":
            column_types["numeric"] += [str(c) for c in columns]
        elif name == "cat":
            column_types["categorical"] += [str(c) for c in columns]
        elif name.startswith("text_"):
            column_types["text"] += [str(c) for c in columns]
    return column_types


class TrainingService:
    def __init__(self, repo: TrainingRepository, notif_service: NotificationService):
        self.repo = repo
        self.notif_service = notif_service

    @staticmethod
    def _prepare_pipeline_inputs(
        df: pd.DataFrame,
        target_col: str,
        feature_cols: list[str] | None,
        problem_type: str = constants.ProblemType.CLASSIFICATION,
    ) -> tuple[bytes, bytes | None, CVStrategyConfig, list[str], FittedPreprocessor, dict[str, Any]]:
        (X_train, y_train), test_data, cv_config, feature_names, preprocessor = TabularPreprocessor.prepare_data(
            df=df,
            target_col=target_col,
            feature_cols=feature_cols,
            problem_type=problem_type,
        )
        logger.info(f"Dataset preprocessed. Applied CV Strategy: {cv_config.description}")

        train_bytes = pickle.dumps((X_train, y_train))
        test_bytes = pickle.dumps(test_data) if test_data is not None else None

        holdout_rows = len(test_data[1]) if test_data is not None else 0
        data_summary = {
            "train_rows": int(len(y_train)),
            "holdout_rows": int(holdout_rows),
            "dropped_rows": int(len(df) - len(y_train) - holdout_rows),
            "n_features": int(X_train.shape[1]) if getattr(X_train, "ndim", 0) == 2 else None,
            "column_types": _column_types(preprocessor),
            "class_distribution": None,
        }
        if problem_type == constants.ProblemType.CLASSIFICATION:
            # Labels as encoded by the classification preprocessor (rows without a target are dropped)
            class_counts = df[target_col].dropna().astype(str).value_counts()
            data_summary["class_distribution"] = {str(label): int(count) for label, count in class_counts.items()}

        return train_bytes, test_bytes, cv_config, feature_names, preprocessor, data_summary

    @staticmethod
    async def _dispatch_and_collect_tasks(
        driver: Any,
        space_models: dict[str, list[dict[str, Any]]],
        train_bytes: bytes,
        test_bytes: bytes | None,
        cv_config: CVStrategyConfig,
        metric_list: list[str],
        metric_sort: str,
        problem_type: str = constants.ProblemType.CLASSIFICATION,
        search_algorithm: str = constants.SearchAlgorithm.TPESEARCH,
        timeout: int | None = None
    ) -> list[dict[str, Any]]:
        tasks = [
            train_single_model_task.remote(
                model_name,
                param_grid,
                train_bytes,
                test_bytes,
                cv_config,
                metric_list,
                metric_sort,
                problem_type,
                search_algorithm
            )
            for model_name, param_grid in space_models.items()
        ]

        task_futures = [asyncio.create_task(task_coroutine) for task_coroutine in tasks]

        logger.info(
            f"Dispatched {len(tasks)} parallel {problem_type} model training tasks to PyMapReduce (timeout={timeout}s)..."
        )
        wait_timeout = float(timeout) if timeout and timeout > 0 else None
        completed_futures, pending_futures = await asyncio.wait(
            task_futures,
            timeout=wait_timeout,
            return_when=asyncio.ALL_COMPLETED,
        )
        for pending_future in pending_futures:
            pending_future.cancel()

        raw_outputs = []
        for completed_future in completed_futures:
            try:
                raw_outputs.append(completed_future.result())
            except Exception as exc:
                logger.warning(f"Training task encountered an error: {exc}")

        valid_results: list[dict[str, Any]] = []
        for raw_output in raw_outputs:
            if hasattr(raw_output, "object_id"):
                resolved_val = await driver.get(raw_output)
                if isinstance(resolved_val, dict):
                    valid_results.append(resolved_val)
            elif isinstance(raw_output, dict):
                valid_results.append(raw_output)

        if not valid_results:
            raise ValueError("No successful model training results received from PyMapReduce workers within the timeout.")

        return valid_results

    @staticmethod
    def _evaluate_and_select_best_model(
        valid_results: list[dict[str, Any]],
        metric_sort: str
    ) -> tuple[ModelScoreItem, dict[str, Any], float, list[ModelScoreItem]]:
        model_scores = [
            ModelScoreItem(
                model_id=model_index,
                model_name=result_data.get("model_name", ""),
                scores=result_data.get("scores", {}),
                best_params=result_data.get("best_params", {}),
            )
            for model_index, result_data in enumerate(valid_results)
        ]

        normalized_metric = metric_sort.strip().lower().replace(" ", "_")

        # Select best model: Minimize error metrics, Maximize accuracy/R2
        if normalized_metric in constants.LOWER_IS_BETTER_METRICS:
            best_model_entry = min(
                model_scores,
                key=lambda score_item: score_item.scores.get(normalized_metric, float("inf")),
            )
        else:
            best_model_entry = max(
                model_scores,
                key=lambda score_item: score_item.scores.get(normalized_metric, -float("inf")),
            )

        best_raw_result = next(
            result_data for result_data in valid_results if result_data.get("model_name") == best_model_entry.model_name
        )

        best_score = best_model_entry.scores.get(
            normalized_metric,
            best_raw_result.get("primary_score", 0.0),
        )

        return best_model_entry, best_raw_result, best_score, model_scores

    @classmethod
    async def train_automl_pipeline(
        cls,
        df: pd.DataFrame,
        target_col: str | None = None,
        feature_cols: list[str] | None = None,
        metric_sort: str | None = None,
        problem_type: str = constants.ProblemType.CLASSIFICATION,
        search_algorithm: str = constants.SearchAlgorithm.TPESEARCH,
        timeout: int | None = None,
        tracker: PipelineTracker | None = None,
        on_progress: Callable[[], Awaitable[None]] | None = None,
    ) -> AutoMLPipelineResult:
        async def progress() -> None:
            if on_progress is not None:
                await on_progress()

        if df is None or df.empty:
            raise ValueError("Input DataFrame is empty or invalid.")

        driver = await MapReduceManager.get_driver()

        target_col = target_col or str(df.columns[-1])
        if problem_type == constants.ProblemType.REGRESSION:
            space_models = search_space.REGRESSION_MODELS
            metric_list = search_space.REGRESSION_METRIC_LIST
            metric_sort = metric_sort or "r2"
        elif problem_type == constants.ProblemType.TIME_SERIES:
            space_models = search_space.TIME_SERIES_MODELS
            metric_list = search_space.TIME_SERIES_METRIC_LIST
            metric_sort = metric_sort or "rmse"
        else:
            space_models = search_space.CLASSIFICATION_MODELS
            metric_list = search_space.CLASSIFICATION_METRIC_LIST
            metric_sort = metric_sort or "accuracy"

        if tracker:
            # Validation, splitting and encoding run in one call: only preprocessing is marked running so a
            # failure is reported on a single node; the split node is recorded once the CV strategy is known
            tracker.start("preprocessing")
            await progress()

        train_bytes, test_bytes, cv_config, feature_names, preprocessor, data_summary = cls._prepare_pipeline_inputs(
            df=df,
            target_col=target_col,
            feature_cols=feature_cols,
            problem_type=problem_type,
        )

        if tracker:
            split_output = {"train_rows": data_summary["train_rows"], "holdout_rows": data_summary["holdout_rows"]}
            tracker.start("split_holdout_data")
            if cv_config.has_holdout:
                tracker.node("split_holdout_data")["params"] = {"method": "train_test_split", "test_size": cv_config.test_size}
                tracker.finish("split_holdout_data", split_output)
            else:
                tracker.skip("split_holdout_data", split_output)
            tracker.node("preprocessing")["params"].update({"target": target_col, "list_feature": feature_names})
            tracker.finish("preprocessing", {
                "dropped_rows": data_summary["dropped_rows"],
                "n_features": data_summary["n_features"],
                "column_types": data_summary["column_types"],
                "class_distribution": data_summary["class_distribution"],
            })

            tracker.start("model_selection")
            tracker.set_models(metric_list, list(space_models), metric_sort)
            tracker.node("model_selection")["params"]["cv"] = {
                "name": cv_config.name,
                "n_splits": cv_config.n_splits,
                "n_repeats": cv_config.n_repeats,
                "description": cv_config.description,
            }
            tracker.finish("model_selection")

            tracker.start("train")
            for model_name in space_models:
                tracker.set_model_status(model_name, "running")
            await progress()

        valid_results = await cls._dispatch_and_collect_tasks(
            driver=driver,
            space_models=space_models,
            train_bytes=train_bytes,
            test_bytes=test_bytes,
            cv_config=cv_config,
            metric_list=metric_list,
            metric_sort=metric_sort,
            problem_type=problem_type,
            search_algorithm=search_algorithm,
            timeout=timeout,
        )

        if tracker:
            returned = {result_data.get("model_name") for result_data in valid_results}
            for result_data in valid_results:
                tracker.set_model_result(
                    model_name=result_data.get("model_name", ""),
                    trials=result_data.get("trials") or [],
                    best_trial=result_data.get("best_trial"),
                    holdout_scores=result_data.get("scores") if cv_config.has_holdout else None,
                )
            for model_name in space_models:
                if model_name not in returned:
                    tracker.set_model_error(model_name, "Training task failed or exceeded the timeout.")
            tracker.finish("train")
            tracker.start("select_best")

        best_entry, best_raw, best_score, model_scores = cls._evaluate_and_select_best_model(
            valid_results=valid_results,
            metric_sort=metric_sort
        )

        if tracker:
            tracker.finish("select_best", {
                "best_model": best_entry.model_name,
                "score_source": "holdout" if cv_config.has_holdout else "cv",
            })
            await progress()

        best_estimator = pickle.loads(best_raw["model_bytes"])
        artifact_bytes = cls._package_serving_artifact(
            best_estimator=best_estimator,
            preprocessor=preprocessor,
            feature_names=feature_names,
            target_col=target_col,
            problem_type=problem_type,
            cv_config=cv_config,
            df=df,
        )

        return AutoMLPipelineResult(
            best_model_id=best_entry.model_id,
            best_model=best_entry.model_name,
            best_params=best_entry.best_params,
            best_score=best_score,
            model_scores=model_scores,
            best_model_bytes=artifact_bytes,
            cv_strategy=cv_config,
            feature_names=feature_names,
        )

    @classmethod
    def _package_serving_artifact(
        cls,
        best_estimator: BaseEstimator,
        preprocessor: FittedPreprocessor,
        feature_names: list[str],
        target_col: str,
        problem_type: str,
        cv_config: CVStrategyConfig,
        df: pd.DataFrame,
    ) -> bytes:
        serving_model = best_estimator
        if problem_type == constants.ProblemType.TIME_SERIES:
            serving_model = TimeSeriesForecaster(
                pipeline=best_estimator,
                config=cv_config,
                df=df,
                target_col=target_col,
                feature_cols=feature_names,
            )

        artifact = {
            "model": serving_model,
            "preprocessor": preprocessor,
            "feature_names": feature_names,
            "target_name": target_col,
            "problem_type": problem_type,
        }
        return pickle.dumps(artifact)

    async def _load_dataset_df(self, dataset_id: str) -> tuple[pd.DataFrame, str, str]:
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
        return df, dataset_name, f"{bucket_name}/{object_name}"

    @staticmethod
    async def _save_best_model_artifact(
        user_id: str,
        job_id: str,
        best_model_name: str,
        model_bytes: bytes,
        version: int = 1,
    ) -> tuple[str, ModelStorageInfo]:
        dest_model_path = f"{user_id}/{job_id}/{best_model_name}_{version}.pkl"
        await minio_service.upload_object(
            bucket_name="models",
            object_name=dest_model_path,
            object_bytes=model_bytes,
        )
        storage_info = ModelStorageInfo(bucket_name="models", object_name=dest_model_path)
        return dest_model_path, storage_info

    async def _save_pipeline(self, job_id: str, tracker: PipelineTracker) -> None:
        # Pipeline JSON is progress reporting only: a storage error must not fail the training job
        try:
            await self.repo.update_pipeline(job_id, tracker.to_dict())
        except Exception as exc:
            logger.warning(f"Failed to save pipeline state for job {job_id}: {exc}")

    async def _on_job_success(
        self,
        job_id: str,
        user_id: str,
        dataset_name: str,
        pipeline_result: AutoMLPipelineResult,
        storage_info: ModelStorageInfo,
    ) -> dict[str, Any]:
        final_result_payload = JobSuccessPayload(
            best_model_id=pipeline_result.best_model_id,
            best_model=pipeline_result.best_model,
            model=storage_info,
            best_params=pipeline_result.best_params,
            best_score=pipeline_result.best_score,
            model_scores=pipeline_result.model_scores,
        )

        await self.repo.update_success(job_id, final_result_payload)

        try:
            await self.notif_service.push_notification(
                user_id=user_id,
                job_id=job_id,
                status=str(constants.JobStatus.SUCCESS),
                message=f"Bộ dữ liệu [{dataset_name}] huấn luyện thành công.",
                metadata={
                    "best_model": pipeline_result.best_model,
                    "best_score": pipeline_result.best_score,
                },
            )
        except Exception as notif_err:
            logger.error(f"Failed to push training success notification for job {job_id}: {notif_err}", exc_info=True)

        return final_result_payload.model_dump()

    async def _on_job_failure(
        self,
        job_id: str,
        user_id: str,
        dataset_name: str,
        error_msg: str,
    ) -> None:
        await self.repo.update_failure(job_id, error_msg)

        try:
            await self.notif_service.push_notification(
                user_id=user_id,
                job_id=job_id,
                status=str(constants.JobStatus.FAILED),
                message=f"Bộ dữ liệu [{dataset_name}] huấn luyện thất bại.",
                metadata={"error_details": error_msg},
            )
        except Exception as notif_err:
            logger.error(f"Failed to push training failure notification for job {job_id}: {notif_err}", exc_info=True)

    async def process_training_job(
        self,
        job_id: str,
        dataset_id: str,
        user_id: str,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        dataset_name = "Unknown"
        if "config" in config and isinstance(config["config"], dict):
            config = config["config"]

        problem_type = config.get("problem_type") or constants.ProblemType.CLASSIFICATION
        target_col = config.get("target")
        feature_cols = config.get("list_feature")
        metric_sort = config.get("metric_sort")
        search_algorithm = config.get("search_algorithm") or constants.SearchAlgorithm.TPESEARCH
        timeout = config.get("timeout") or None

        tracker = PipelineTracker(
            job_id=job_id,
            dataset_id=dataset_id,
            problem_type=problem_type,
            search_algorithm=search_algorithm,
            metric_sort=metric_sort,
            target=target_col,
            feature_cols=feature_cols,
            timeout=timeout,
        )

        async def save_pipeline() -> None:
            await self._save_pipeline(job_id, tracker)

        try:
            logger.info(f"Processing AutoML Job: ID={job_id}, Dataset={dataset_id}, User={user_id}")

            tracker.start("read_dataset")
            await save_pipeline()
            df, dataset_name, data_url = await self._load_dataset_df(dataset_id)
            tracker.finish("read_dataset", {"data_url": data_url, "n_rows": len(df), "n_columns": len(df.columns)})

            pipeline_result = await self.train_automl_pipeline(
                df=df,
                target_col=target_col,
                feature_cols=feature_cols,
                metric_sort=metric_sort,
                problem_type=problem_type,
                search_algorithm=search_algorithm,
                timeout=timeout,
                tracker=tracker,
                on_progress=save_pipeline,
            )

            tracker.start("save_result")
            _, storage_info = await self._save_best_model_artifact(
                user_id=user_id,
                job_id=job_id,
                best_model_name=pipeline_result.best_model,
                model_bytes=pipeline_result.best_model_bytes,
            )
            tracker.finish("save_result", {"object_name": storage_info.object_name})
            tracker.complete()
            await save_pipeline()

            return await self._on_job_success(
                job_id=job_id,
                user_id=user_id,
                dataset_name=dataset_name,
                pipeline_result=pipeline_result,
                storage_info=storage_info,
            )

        except asyncio.CancelledError:
            error_msg = "Training job was cancelled by user."
            logger.info(f"AutoML Job {job_id} cancelled.")
            tracker.abort(error_msg, status="cancelled")
            await save_pipeline()
            await self._on_job_failure(
                job_id=job_id,
                user_id=user_id,
                dataset_name=dataset_name,
                error_msg=error_msg,
            )
            raise
        except Exception as e:
            error_msg = f"Training failure: {str(e)}"
            logger.error(f"AutoML Job {job_id} failed: {error_msg}", exc_info=True)
            tracker.abort(error_msg)
            await save_pipeline()
            await self._on_job_failure(
                job_id=job_id,
                user_id=user_id,
                dataset_name=dataset_name,
                error_msg=error_msg,
            )
            raise e
