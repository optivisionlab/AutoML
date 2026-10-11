# Standard Libraries
import io
import json
import math
import time
import zipfile
import logging
from typing import Any

# Third-party Libraries
from fastapi import status, UploadFile
from pymongo.asynchronous.database import AsyncDatabase

# Local Libraries
from src.core import exceptions, constants, utils
from src.config import settings
from src.shared import minio_service, MapReduceManager, kafka_service
from src.modules.trainings import TrainingRepository
from src.modules.inference.schemas import (
    DeploymentInfoResponse,
    FeatureSchemaItem,
    PredictRequest,
    PredictResponse,
    JobItemResponse,
)
from src.modules.inference.registry import InferenceActorRegistry
from src.modules.inference.templates import (
    CodeSnippetGenerator,
    DockerPackageTemplate,
    NotebookTemplate,
)


# Logging
logger = logging.getLogger(__name__)


class InferenceService:
    def __init__(self, db: AsyncDatabase):
        self.db = db
        self.repo = TrainingRepository(db)

    @staticmethod
    async def _resolve_actor_output(out: Any) -> Any:
        if hasattr(out, "object_id"):
            driver = await MapReduceManager.get_driver()
            return await driver.get(out)
        return out

    async def _get_validated_job(self, current_user: dict, job_id: str) -> dict[str, Any]:
        job_doc = await self.repo.get_job_by_id(job_id)
        if not job_doc:
            raise exceptions.CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model training job '{job_id}' not found.",
                error_code=constants.ErrorCode.NOT_FOUND,
            )

        user_id = str(current_user.get("_id", ""))
        user_role = current_user.get("role", "user")
        job_user_id = str(job_doc.get("user", {}).get("id", ""))

        if user_role != "admin" and user_id != job_user_id:
            raise exceptions.CustomException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access or deploy this model.",
                error_code=constants.ErrorCode.FORBIDDEN,
            )

        if job_doc.get("status") != 1:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Model training has not completed successfully yet.",
                error_code=constants.ErrorCode.BAD_REQUEST,
            )

        return job_doc

    def _build_deployment_info_response(self, job_doc: dict[str, Any], job_id: str, base_url: str) -> DeploymentInfoResponse:
        config = job_doc.get("config", {})
        features = config.get("list_feature", [])
        model_name = job_doc.get("best_model", "AutoML_Model")
        activate_val = job_doc.get("activate", 0)
        best_score = job_doc.get("best_score")

        endpoint_url = f"{base_url.rstrip('/')}/api/v1/inference/models/{job_id}/predict"

        sample_record: dict[str, Any] = {}
        features_schema: list[FeatureSchemaItem] = []

        for feat in features:
            sample_record[feat] = 1.0
            features_schema.append(FeatureSchemaItem(name=feat, data_type="float", sample_value=1.0))

        if not sample_record:
            sample_record = {"feature_1": 1.0, "feature_2": 0.5}
            features_schema = [
                FeatureSchemaItem(name="feature_1", data_type="float", sample_value=1.0),
                FeatureSchemaItem(name="feature_2", data_type="float", sample_value=0.5),
            ]

        sample_payload = {"data": [sample_record]}
        snippets = CodeSnippetGenerator.generate_all(
            endpoint_url=endpoint_url,
            sample_payload=sample_payload,
        )

        return DeploymentInfoResponse(
            job_id=job_id,
            dataset_id=job_doc.get("data", {}).get("id"),
            model_name=model_name,
            status="ACTIVE" if activate_val == 1 else "INACTIVE",
            activate=activate_val,
            best_score=best_score,
            endpoint_url=endpoint_url,
            features=features,
            features_schema=features_schema,
            sample_payload=sample_payload,
            code_snippets=snippets,
        )

    async def toggle_model_activation(
        self,
        current_user: dict,
        job_id: str,
        activate: int,
        base_url: str = f"http://{settings.BACKEND.HOST}:{settings.BACKEND.PORT}",
    ) -> DeploymentInfoResponse:
        job_doc = await self._get_validated_job(current_user, job_id)
        await self.repo.update_activation(job_id, activate)
        job_doc["activate"] = activate

        if activate == 0:
            await InferenceActorRegistry.evict_actor(job_id)

        return self._build_deployment_info_response(job_doc, job_id, base_url)

    async def get_deployment_info(
        self,
        current_user: dict,
        job_id: str,
        base_url: str = f"http://{settings.BACKEND.HOST}:{settings.BACKEND.PORT}",
    ) -> DeploymentInfoResponse:
        job_doc = await self._get_validated_job(current_user, job_id)

        return self._build_deployment_info_response(job_doc, job_id, base_url)

    async def predict(
        self,
        current_user: dict,
        job_id: str,
        request: PredictRequest,
    ) -> PredictResponse:
        job_doc = await self._get_validated_job(current_user, job_id)

        if job_doc.get("activate", 0) != 1:
            raise exceptions.CustomException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Model API for job '{job_id}' is currently INACTIVE. Please activate the model before making predictions.",
                error_code=constants.ErrorCode.FORBIDDEN,
            )

        storage_info = job_doc.get("model", {})
        config = job_doc.get("config", {})
        expected_features = config.get("list_feature", [])

        if expected_features and request.data:
            first_row = request.data[0]
            missing_cols = [col for col in expected_features if col not in first_row]
            if missing_cols:
                raise exceptions.CustomException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required feature columns: {missing_cols}",
                    error_code=constants.ErrorCode.BAD_REQUEST,
                )

        start_time = time.perf_counter()
        raw_preds = await InferenceActorRegistry.invoke_actor(
            job_id, storage_info, "predict", request.data, expected_features
        )
        predictions = await self._resolve_actor_output(raw_preds)
        latency_ms = (time.perf_counter() - start_time) * 1000.0

        return PredictResponse(
            job_id=job_id,
            model_name=job_doc.get("best_model", "AutoML_Model"),
            predictions=predictions,
            latency_ms=round(latency_ms, 2),
            total_samples=len(request.data),
        )

    async def predict_file(
        self,
        current_user: dict,
        job_id: str,
        file: UploadFile,
    ) -> tuple[str, str, io.BytesIO]:
        job_doc = await self._get_validated_job(current_user, job_id)

        if job_doc.get("activate", 0) != 1:
            raise exceptions.CustomException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Model API for job '{job_id}' is currently INACTIVE. Please activate the model before making predictions.",
                error_code=constants.ErrorCode.FORBIDDEN,
            )

        storage_info = job_doc.get("model", {})

        max_batch_mb = 100
        utils.validate_file_size(
            file,
            max_size_mb=max_batch_mb,
            error_message=f"Batch prediction file size exceeds the maximum allowed limit of {max_batch_mb}MB.",
        )

        file_bytes = await file.read()
        if not file_bytes:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
                error_code=constants.ErrorCode.BAD_REQUEST,
            )

        utils.validate_file_bytes_size(
            file_bytes,
            max_size_mb=max_batch_mb,
            error_message=f"Batch prediction file size exceeds the maximum allowed limit of {max_batch_mb}MB.",
        )

        if not file.filename:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file must have a valid filename with an extension (.csv, .xlsx, .xls).",
                error_code=constants.ErrorCode.BAD_REQUEST,
            )

        filename_orig = file.filename
        ext = filename_orig.split(".")[-1].lower() if "." in filename_orig else ""
        if ext not in ["csv", "xlsx", "xls"]:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{ext}'. Only CSV and Excel (.xlsx, .xls) files are supported for batch prediction.",
                error_code=constants.ErrorCode.BAD_REQUEST,
            )

        config = job_doc.get("config", {})
        expected_features = config.get("list_feature", [])
        target_col = config.get("target", "target")

        try:
            raw_out = await InferenceActorRegistry.invoke_actor(
                job_id,
                storage_info,
                "predict_file",
                file_bytes=file_bytes,
                filename=filename_orig,
                expected_features=expected_features,
                target_col=target_col,
            )
            out_filename, media_type, out_bytes = await self._resolve_actor_output(raw_out)
        except Exception as e:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to perform inference on uploaded file: {str(e)}",
                error_code=constants.ErrorCode.BAD_REQUEST,
            )

        output_buffer = io.BytesIO(out_bytes)
        output_buffer.seek(0)
        return out_filename, media_type, output_buffer

    async def export_notebook(self, current_user: dict, job_id: str) -> tuple[str, bytes]:
        job_doc = await self._get_validated_job(current_user, job_id)

        model_name = job_doc.get("best_model", "RandomForestClassifier")
        best_params = job_doc.get("best_params", {})
        best_score = job_doc.get("best_score", 0.0)
        config = job_doc.get("config", {})
        features = config.get("list_feature", [])
        target = config.get("target", "target")

        notebook = NotebookTemplate.generate_notebook_dict(
            model_name=model_name,
            best_params=best_params,
            best_score=best_score,
            features=features,
            target=target,
        )

        content_bytes = json.dumps(notebook, indent=2).encode("utf-8")
        filename = f"hautoml_{model_name}_{job_id[:8]}.ipynb"
        return filename, content_bytes

    async def export_docker_package(self, current_user: dict, job_id: str) -> tuple[str, bytes]:
        job_doc = await self._get_validated_job(current_user, job_id)

        model_name = job_doc.get("best_model", "AutoML_Model")
        config = job_doc.get("config", {})
        features = config.get("list_feature", [])

        storage_info = job_doc.get("model", {})
        bucket_name = storage_info.get("bucket_name", "models")
        object_name = storage_info.get("object_name")

        raw_model_bytes = await minio_service.get_object(bucket_name, object_name)
        if isinstance(raw_model_bytes, io.BytesIO):
            raw_model_bytes = raw_model_bytes.getvalue()

        app_py_code = DockerPackageTemplate.generate_app_py(model_name, features)
        readme_md = DockerPackageTemplate.generate_readme_md(model_name, job_id, features)

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("model.pkl", raw_model_bytes)
            zip_file.writestr("app.py", app_py_code)
            zip_file.writestr("requirements.txt", DockerPackageTemplate.REQUIREMENTS_TXT)
            zip_file.writestr("Dockerfile", DockerPackageTemplate.DOCKERFILE)
            zip_file.writestr("README.md", readme_md)

        zip_buffer.seek(0)
        filename = f"hautoml_docker_{model_name}_{job_id[:8]}.zip"
        return filename, zip_buffer.getvalue()

    async def export_model_binary(self, current_user: dict, job_id: str) -> tuple[str, bytes]:
        job_doc = await self._get_validated_job(current_user, job_id)

        model_name = job_doc.get("best_model", "AutoML_Model")
        storage_info = job_doc.get("model", {})
        bucket_name = storage_info.get("bucket_name", "models")
        object_name = storage_info.get("object_name")

        raw_bytes = await minio_service.get_object(bucket_name, object_name)
        if isinstance(raw_bytes, io.BytesIO):
            raw_bytes = raw_bytes.getvalue()

        filename = f"{model_name}_{job_id[:8]}.pkl"
        return filename, raw_bytes

    async def get_user_jobs(
        self,
        user_id: str,
        current_page: int,
        page_size: int,
        activate: int | None = None,
        data_name: str | None = None,
        sort_name: str | None = None,
        sort_time: str | None = None,
        is_admin: bool = False,
    ) -> tuple[list[JobItemResponse], dict[str, Any]]:
        skip = (current_page - 1) * page_size
        db_sort = []

        if sort_name:
            db_sort.append(("data.name", 1 if sort_name == "asc" else -1))

        if sort_time:
            db_sort.append(("create_at", 1 if sort_time == "asc" else -1))
        elif not db_sort:
            db_sort.append(("create_at", -1))

        raw_jobs, total_items = await self.repo.get_jobs_with_count(
            user_id=user_id,
            skip=skip,
            limit=page_size,
            activate=activate,
            data_name=data_name,
            sort_params=db_sort,
            is_admin=is_admin,
        )

        formatted_jobs = []
        for doc in raw_jobs:
            doc["_id"] = str(doc["_id"])
            formatted_jobs.append(JobItemResponse(**doc))

        total_pages = math.ceil(total_items / page_size) if total_items > 0 else 0
        meta = {
            "total_items": total_items,
            "current_page": current_page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

        return formatted_jobs, meta

    async def cancel_job(self, current_user: dict, job_id: str) -> dict[str, Any]:
        job_doc = await self.repo.get_job_by_id(job_id)
        if not job_doc:
            raise exceptions.CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model training job '{job_id}' not found.",
                error_code=constants.ErrorCode.NOT_FOUND,
            )

        user_id = str(current_user.get("_id", ""))
        user_role = current_user.get("role", "user")
        job_user_id = str(job_doc.get("user", {}).get("id", ""))

        if user_role != "admin" and user_id != job_user_id:
            raise exceptions.CustomException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to cancel this job.",
                error_code=constants.ErrorCode.FORBIDDEN,
            )

        job_status = job_doc.get("status")
        if job_status != constants.JobStatus.RUNNING:
            status_desc = "completed" if job_status == constants.JobStatus.SUCCESS else ("cancelled" if job_status == constants.JobStatus.CANCELLED else "failed")
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel job with status {job_status} ({status_desc}). Only running or pending jobs can be cancelled",
                error_code=constants.ErrorCode.BAD_REQUEST,
            )

        # Update job status in DB to cancelled
        await self.repo.update_cancelled(job_id, "Training job was cancelled by user")

        # Notify consumer via Kafka so the worker process can be killed immediately
        cancel_payload = {
            "action": "cancel",
            "job_id": str(job_id),
            "user_id": user_id,
        }

        await kafka_service.send_message(
            value=cancel_payload,
            key=str(job_id),
        )

        return {"job_id": str(job_id), "status": constants.JobStatus.CANCELLED}
