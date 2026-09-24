# Local Libraries
import io
import json
import math
import time
import zipfile
import logging
from typing import Any

# Third-party Libraries
import numpy as np
import pandas as pd
from fastapi import status, UploadFile
from pymongo.asynchronous.database import AsyncDatabase

# Local Libraries
from src.core import exceptions
from src.shared import constants, minio_service
from src.modules.trainings import TrainingRepository
from src.modules.inference.schemas import (
    DeploymentInfoResponse,
    FeatureSchemaItem,
    PredictRequest,
    PredictResponse,
    JobItemResponse,
)
from src.modules.inference.registry import InferenceModelRegistry
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

    @staticmethod
    def _parse_input_file(file_bytes: bytes, filename: str) -> tuple[pd.DataFrame, str]:
        if not file_bytes:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty.",
                error_code=constants.ErrorCode.BAD_REQUEST,
            )

        ext = filename.split(".")[-1].lower() if "." in filename else "csv"
        try:
            if ext in ["xlsx", "xls"]:
                df = pd.read_excel(io.BytesIO(file_bytes))
            else:
                df = pd.read_csv(io.BytesIO(file_bytes))
        except Exception as e:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse uploaded file: {str(e)}",
                error_code=constants.ErrorCode.BAD_REQUEST,
            )

        if df.empty:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded dataset contains no data rows.",
                error_code=constants.ErrorCode.BAD_REQUEST,
            )

        df.columns = df.columns.astype(str).str.strip()
        return df, ext

    @staticmethod
    def _export_dataframe_to_buffer(df: pd.DataFrame, ext: str, original_filename: str) -> tuple[str, str, io.BytesIO]:
        output_buffer = io.BytesIO()
        out_filename = f"predicted_{original_filename}"

        if ext in ["xlsx", "xls"]:
            df.to_excel(output_buffer, index=False, engine="openpyxl")
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            df.to_csv(output_buffer, index=False, encoding="utf-8-sig")
            media_type = "text/csv"

        output_buffer.seek(0)
        return out_filename, media_type, output_buffer

    @staticmethod
    def _run_inference(artifact: Any, df_input: pd.DataFrame, expected_features: list[str]) -> list[Any]:
        if isinstance(artifact, dict) and "model" in artifact:
            model = artifact["model"]
            preprocessor = artifact.get("preprocessor")
        else:
            model = artifact
            preprocessor = None

        if preprocessor is not None:
            X = preprocessor.transform(df_input)
            raw_predictions = model.predict(X)
            return preprocessor.inverse_transform_target(raw_predictions)

        # Fallback for raw estimators
        df_feat = df_input[expected_features].copy() if expected_features else df_input.copy()
        for col in df_feat.columns:
            if df_feat[col].dtype == "object" or df_feat[col].dtype.name == "category":
                mode_val = df_feat[col].mode()
                fill_val = mode_val.iloc[0] if not mode_val.empty else "0"
                df_feat[col] = pd.to_numeric(df_feat[col].fillna(fill_val), errors="coerce").fillna(0)
            else:
                median_val = df_feat[col].median()
                df_feat[col] = df_feat[col].fillna(median_val if not pd.isna(median_val) else 0.0)

        X = df_feat.to_numpy(dtype=np.float64)
        raw_predictions = model.predict(X)
        return [
            int(p) if isinstance(p, (np.integer, int))
            else float(p) if isinstance(p, (np.floating, float))
            else str(p)
            for p in raw_predictions
        ]

    def _build_deployment_info_response(
        self,
        job_doc: dict[str, Any],
        job_id: str,
        base_url: str,
    ) -> DeploymentInfoResponse:
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
        base_url: str = "http://localhost:9999",
    ) -> DeploymentInfoResponse:
        job_doc = await self._get_validated_job(current_user, job_id)
        await self.repo.update_activation(job_id, activate)
        job_doc["activate"] = activate

        if activate == 0:
            InferenceModelRegistry.evict_model(job_id)

        return self._build_deployment_info_response(job_doc, job_id, base_url)

    async def get_deployment_info(
        self,
        current_user: dict,
        job_id: str,
        base_url: str = "http://localhost:9999",
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
        artifact = await InferenceModelRegistry.get_model(job_id, storage_info)

        config = job_doc.get("config", {})
        expected_features = config.get("list_feature", [])

        df_input = pd.DataFrame(request.data)
        if expected_features:
            missing_cols = [col for col in expected_features if col not in df_input.columns]
            if missing_cols:
                raise exceptions.CustomException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required feature columns: {missing_cols}",
                    error_code=constants.ErrorCode.BAD_REQUEST,
                )

        start_time = time.perf_counter()
        predictions = self._run_inference(artifact, df_input, expected_features)
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
        artifact = await InferenceModelRegistry.get_model(job_id, storage_info)

        file_bytes = await file.read()
        filename_orig = file.filename or "data.csv"
        df, ext = self._parse_input_file(file_bytes, filename_orig)

        config = job_doc.get("config", {})
        expected_features = config.get("list_feature", [])
        target_col = config.get("target", "target")

        if expected_features:
            missing_cols = [col for col in expected_features if col not in df.columns]
            if missing_cols:
                raise exceptions.CustomException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required feature columns in uploaded file: {missing_cols}",
                    error_code=constants.ErrorCode.BAD_REQUEST,
                )

        predictions = self._run_inference(artifact, df, expected_features)

        pred_col = f"prediction_{target_col}" if target_col in df.columns else "prediction"
        df_result = df.copy()
        df_result[pred_col] = predictions

        return self._export_dataframe_to_buffer(df_result, ext, filename_orig)

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
