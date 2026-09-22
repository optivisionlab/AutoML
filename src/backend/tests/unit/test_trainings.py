# Standard Libraries
import unittest
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId

# Third-party Libraries
import pandas as pd
from sklearn.datasets import load_iris

# Local Libraries
from src.modules.trainings.repository import TrainingRepository
from src.modules.trainings.service import TrainingService


class TestTrainingRepository(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_db = MagicMock()
        self.mock_jobs = AsyncMock()
        self.mock_data = AsyncMock()
        self.mock_db.tbl_Job = self.mock_jobs
        self.mock_db.tbl_Data = self.mock_data
        self.repo = TrainingRepository(self.mock_db)

    async def test_get_job_by_id(self):
        job_oid = ObjectId()
        self.mock_jobs.find_one.return_value = {"_id": job_oid, "status": 0}

        result = await self.repo.get_job_by_id(str(job_oid))
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], 0)
        self.mock_jobs.find_one.assert_called_once_with({"_id": job_oid})

    async def test_update_success(self):
        job_id = str(ObjectId())
        payload = {
            "best_model_id": 0,
            "best_model": "RandomForestClassifier",
            "model": {"bucket_name": "models", "object_name": f"user/{job_id}/RF_1.pkl"},
            "best_params": {"n_estimators": 100},
            "best_score": 0.98,
            "model_scores": [{"model_id": 0, "model_name": "RF", "scores": {"accuracy": 0.98}}],
            "time_limit_reached": False,
            "completed_models": 6,
            "total_models": 6
        }
        await self.repo.update_success(job_id, payload)
        self.mock_jobs.update_one.assert_called_once()
        args, _ = self.mock_jobs.update_one.call_args
        self.assertEqual(args[1]["$set"]["status"], 1)
        self.assertEqual(args[1]["$set"]["best_model"], "RandomForestClassifier")

    async def test_update_failure(self):
        job_id = str(ObjectId())
        await self.repo.update_failure(job_id, "Out of memory error")
        self.mock_jobs.update_one.assert_called_once()
        args, _ = self.mock_jobs.update_one.call_args
        self.assertEqual(args[1]["$set"]["status"], -1)
        self.assertEqual(args[1]["$set"]["infor"], "Out of memory error")


class TestTrainingService(unittest.IsolatedAsyncioTestCase):
    async def test_train_automl_pipeline_in_memory(self):
        iris = load_iris(as_frame=True)
        df = iris.frame

        result = await TrainingService.train_automl_pipeline(
            df=df,
            target_col="target",
            metric_sort="accuracy",
            models_to_train=["DecisionTreeClassifier", "GaussianNB"]
        )

        self.assertIsNotNone(result.best_model)
        self.assertIsNotNone(result.best_score)
        self.assertIsNotNone(result.best_model_bytes)
        self.assertEqual(len(result.model_scores), 2)
        self.assertTrue(result.best_score > 0.8)
        self.assertEqual(result.cv_strategy.tier, 1)

    async def test_process_training_job_pipeline_flow(self):
        import io
        from unittest.mock import patch

        iris = load_iris(as_frame=True)
        df = iris.frame
        parquet_buf = io.BytesIO()
        df.to_parquet(parquet_buf, index=False)
        parquet_bytes = parquet_buf.getvalue()

        mock_repo = AsyncMock()
        mock_repo.get_dataset_info.return_value = {
            "dataName": "Iris",
            "data_link": {"bucket_name": "datasets", "object_name": "iris.parquet"}
        }
        mock_notif = AsyncMock()
        service = TrainingService(repo=mock_repo, notif_service=mock_notif)

        with patch("src.modules.trainings.service.minio_service") as mock_minio:
            mock_minio.get_object = AsyncMock(return_value=parquet_bytes)
            mock_minio.upload_object = AsyncMock()

            result = await service.process_training_job(
                job_id="test_job_123",
                dataset_id="test_ds_123",
                user_id="test_user_123",
                config={
                    "target": "target",
                    "metric_sort": "accuracy",
                    "models": ["DecisionTreeClassifier", "GaussianNB"]
                }
            )

            self.assertIn("best_model", result)
            self.assertIn("best_score", result)
            mock_minio.get_object.assert_called_once_with("datasets", "iris.parquet")
            mock_minio.upload_object.assert_called_once()
            mock_repo.update_success.assert_called_once()
            mock_notif.push_notification.assert_called_once()


if __name__ == "__main__":
    unittest.main()

