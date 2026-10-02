# Standard Libraries
import io
import os
import sys
import pickle
import asyncio
import logging
from pathlib import Path
from typing import Any

# Third-party Libraries
import numpy as np
import pandas as pd
from miniopy_async import Minio
import pymapreduce

# Local Libraries
from src.config import settings
from src.shared import constants


# Logging
logger = logging.getLogger(__name__)


@pymapreduce.remote(idle_timeout=settings.PYMAPREDUCE.ACTOR_IDLE_TIMEOUT)
class ModelInferenceActor:
    def __init__(
        self,
        bucket_name: str,
        object_name: str,
        minio_endpoint: str,
        access_key: str,
        secret_key: str,
        secure: bool = False,
        **kwargs: Any,
    ):
        self.bucket_name = bucket_name
        self.object_name = object_name

        async def _fetch_artifact():
            client = Minio(
                endpoint=minio_endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=secure,
            )
            response = await client.get_object(bucket_name, object_name)
            try:
                return await response.read()
            finally:
                response.close()
                if hasattr(response, "release"):
                    response.release()

        raw_bytes = asyncio.run(_fetch_artifact())
        if isinstance(raw_bytes, io.BytesIO):
            raw_bytes = raw_bytes.getvalue()

        artifact = pickle.loads(raw_bytes)
        if isinstance(artifact, dict) and "model" in artifact:
            self.model = artifact["model"]
            self.preprocessor = artifact.get("preprocessor")
            self.feature_names = artifact.get("feature_names", [])
            self.target_name = artifact.get("target_name", "target")
            self.problem_type = artifact.get("problem_type", "classification")
        else:
            self.model = artifact
            self.preprocessor = None
            self.feature_names = []
            self.target_name = "target"
            self.problem_type = "classification"

    def predict(
        self,
        records: list[dict[str, Any]],
        expected_features: list[str] | None = None,
    ) -> list[Any]:
        if not records:
            return []

        df_input = pd.DataFrame(records)
        df_input.columns = df_input.columns.astype(str).str.strip()

        if self.preprocessor is not None:
            X = self.preprocessor.transform(df_input)
            raw_preds = self.model.predict(X)
            raw_preds = self.preprocessor.inverse_transform_target(raw_preds)
        else:
            feats = expected_features or self.feature_names
            df_feat = df_input[feats].copy() if feats else df_input.copy()
            for col in df_feat.columns:
                if df_feat[col].dtype == "object" or df_feat[col].dtype.name == "category":
                    mode_val = df_feat[col].mode()
                    fill_val = mode_val.iloc[0] if not mode_val.empty else "0"
                    df_feat[col] = pd.to_numeric(df_feat[col].fillna(fill_val), errors="coerce").fillna(0)
                else:
                    median_val = df_feat[col].median()
                    df_feat[col] = df_feat[col].fillna(median_val if not pd.isna(median_val) else 0.0)

            X = df_feat.to_numpy(dtype=np.float64)
            raw_preds = self.model.predict(X)

        return [
            int(p) if isinstance(p, (np.integer, int))
            else float(p) if isinstance(p, (np.floating, float))
            else str(p)
            for p in raw_preds
        ]

    def predict_file(
        self,
        file_bytes: bytes,
        filename: str,
        expected_features: list[str] | None = None,
        target_col: str | None = None,
    ) -> tuple[str, str, bytes]:
        if not file_bytes:
            raise ValueError("Uploaded file is empty.")

        ext = filename.split(".")[-1].lower() if "." in filename else "csv"
        if ext in ["xlsx", "xls"]:
            df = pd.read_excel(io.BytesIO(file_bytes))
        else:
            df = pd.read_csv(io.BytesIO(file_bytes))

        if df.empty:
            raise ValueError("Uploaded dataset contains no data rows.")

        df.columns = df.columns.astype(str).str.strip()
        records = df.to_dict(orient="records")
        preds = self.predict(records, expected_features=expected_features)

        pred_target = target_col or self.target_name or "target"
        pred_col_name = f"predicted_{pred_target}"
        df[pred_col_name] = preds

        output_buffer = io.BytesIO()
        out_filename = f"predicted_{filename}"

        if ext in ["xlsx", "xls"]:
            df.to_excel(output_buffer, index=False, engine="openpyxl")
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            df.to_csv(output_buffer, index=False, encoding="utf-8-sig")
            media_type = "text/csv"

        return out_filename, media_type, output_buffer.getvalue()


class MapReduceManager:
    """
    Singleton Manager for PyMapReduce Driver and Cluster connection lifecycle
    """
    _driver: pymapreduce.Driver | None = None
    _is_initialized: bool = False
    _lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    async def get_driver(cls) -> pymapreduce.Driver:
        """
        Get or initialize the singleton PyMapReduce Driver instance
        """
        if cls._driver and cls._is_initialized:
            return cls._driver

        async with cls._lock:
            if cls._driver and cls._is_initialized:
                return cls._driver

            mode = settings.PYMAPREDUCE.MODE
            head_addr = settings.PYMAPREDUCE.HEAD_ADDRESS

            backend_dir = str(Path(__file__).resolve().parent.parent.parent)
            runtime_env = {
                "working_dir": backend_dir,
                "excludes": ["deploy", "tests", "demo", "docs", "MapReduce", "dataset"],
            }

            if mode == constants.MapReduceMode.LOCAL:
                logger.info(f"Initializing PyMapReduce in LOCAL EMBEDDED mode at {head_addr}...")
                # Initialize local HeadNode with retry in case of WAL recovery
                last_err = None
                for attempt in range(1, 4):
                    try:
                        cls._driver = await pymapreduce.init(
                            address=head_addr,
                            runtime_env=runtime_env
                        )
                        break
                    except Exception as err:
                        last_err = err
                        logger.warning(f"PyMapReduce init attempt {attempt}/3 failed: {err}. Retrying in 0.5s...")
                        await asyncio.sleep(0.5)

                if cls._driver is None:
                    raise RuntimeError(f"Failed to initialize PyMapReduce HeadNode after 3 attempts: {last_err}")

                # Start local worker utilizing all available CPU cores automatically
                asyncio.ensure_future(
                    pymapreduce.start_worker(head_addr, idle_timeout=settings.PYMAPREDUCE.IDLE_TIMEOUT)
                )

                # Allow a short moment for the local worker to register with HeadNode
                await asyncio.sleep(1.0)
                logger.info("PyMapReduce Local Cluster successfully initialized and worker registered")
            else:
                # CLUSTER mode
                logger.info(f"Connecting to PyMapReduce Cluster at HeadNode '{head_addr}' with runtime_env working_dir={backend_dir}...")
                last_err = None
                for attempt in range(1, 4):
                    try:
                        cls._driver = await pymapreduce.connect(
                            head_node=head_addr,
                            runtime_env=runtime_env
                        )
                        break
                    except Exception as err:
                        last_err = err
                        logger.warning(f"PyMapReduce connect attempt {attempt}/3 failed: {err}. Retrying in 0.5s...")
                        await asyncio.sleep(0.5)

                if cls._driver is None:
                    raise RuntimeError(f"Failed to connect to PyMapReduce Cluster after 3 attempts: {last_err}")

                logger.info("Successfully connected to PyMapReduce Cluster")

            cls._is_initialized = True
            return cls._driver

    @classmethod
    async def shutdown(cls) -> None:
        """
        Gracefully shutdown the driver connection.
        """
        async with cls._lock:
            if cls._driver and cls._is_initialized:
                try:
                    mode = settings.PYMAPREDUCE.MODE
                    if mode == constants.MapReduceMode.LOCAL:
                        await cls._driver.shutdown()
                    logger.info("PyMapReduce Driver shutdown completed")
                except Exception as e:
                    logger.warning(f"Error while shutting down PyMapReduce Driver: {e}")
                finally:
                    cls._driver = None
                    cls._is_initialized = False
