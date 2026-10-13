import io
import pickle
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId

import numpy as np
import pandas as pd
from sklearn.datasets import load_iris, load_diabetes
from sklearn.pipeline import Pipeline
from sklearn.tree import DecisionTreeClassifier
from sklearn.linear_model import Ridge
from sklearn.model_selection import KFold

from src.core import constants
from src.modules.preprocessing import TimeSeriesForecaster
from src.modules.trainings.repository import TrainingRepository
from src.modules.trainings.service import TrainingService
from src.modules.trainings.executor import (
    build_trainable_model,
    tune_and_fit_model,
    evaluate_trained_model,
)


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
    @patch("src.modules.trainings.service.MapReduceManager.get_driver")
    @patch("src.modules.trainings.service.TrainingService._dispatch_and_collect_tasks")
    async def test_train_automl_pipeline_classification(self, mock_dispatch, mock_driver):
        mock_driver.return_value = AsyncMock()
        from src.modules.models.service import ModelService
        from sklearn.tree import DecisionTreeClassifier
        from sklearn.naive_bayes import GaussianNB

        clf1 = DecisionTreeClassifier().fit([[0], [1]], [0, 1])
        clf2 = GaussianNB().fit([[0], [1]], [0, 1])

        mock_dispatch.return_value = [
            {
                "model_name": "DecisionTreeClassifier",
                "scores": {"accuracy": 0.95, "f1": 0.94},
                "best_params": {},
                "model_bytes": ModelService.serialize_model(clf1),
            },
            {
                "model_name": "GaussianNB",
                "scores": {"accuracy": 0.88, "f1": 0.87},
                "best_params": {},
                "model_bytes": ModelService.serialize_model(clf2),
            },
        ]

        iris = load_iris(as_frame=True)
        df = iris.frame

        result = await TrainingService.train_automl_pipeline(
            df=df,
            target_col="target",
            metric_sort="accuracy",
            problem_type="classification",
        )

        self.assertIsNotNone(result.best_model)
        self.assertEqual(result.best_model, "DecisionTreeClassifier")
        self.assertEqual(result.best_score, 0.95)
        self.assertIsNotNone(result.best_model_bytes)
        self.assertEqual(len(result.model_scores), 2)
        self.assertEqual(result.cv_strategy.tier, 1)

        artifact = pickle.loads(result.best_model_bytes)
        self.assertEqual(artifact["problem_type"], "classification")
        self.assertIsNotNone(artifact["preprocessor"])

    @patch("src.modules.trainings.service.MapReduceManager.get_driver")
    @patch("src.modules.trainings.service.TrainingService._dispatch_and_collect_tasks")
    async def test_train_automl_pipeline_regression(self, mock_dispatch, mock_driver):
        mock_driver.return_value = AsyncMock()
        from src.modules.models.service import ModelService
        from sklearn.linear_model import LinearRegression
        from sklearn.tree import DecisionTreeRegressor

        reg1 = LinearRegression().fit([[0], [1]], [0.0, 1.0])
        reg2 = DecisionTreeRegressor().fit([[0], [1]], [0.0, 1.0])

        mock_dispatch.return_value = [
            {
                "model_name": "LinearRegression",
                "scores": {"r2": 0.85, "mse": 12.5},
                "best_params": {},
                "model_bytes": ModelService.serialize_model(reg1),
            },
            {
                "model_name": "DecisionTreeRegressor",
                "scores": {"r2": 0.72, "mse": 25.0},
                "best_params": {},
                "model_bytes": ModelService.serialize_model(reg2),
            },
        ]

        diabetes = load_diabetes(as_frame=True)
        df = diabetes.frame

        result = await TrainingService.train_automl_pipeline(
            df=df,
            target_col="target",
            metric_sort="r2",
            problem_type="regression",
        )

        self.assertIsNotNone(result.best_model)
        self.assertEqual(result.best_model, "LinearRegression")
        self.assertEqual(result.best_score, 0.85)
        self.assertIsNotNone(result.best_model_bytes)
        self.assertEqual(len(result.model_scores), 2)
        self.assertEqual(result.cv_strategy.name, "ContinuousRepeatedStratifiedKFold")

        artifact = pickle.loads(result.best_model_bytes)
        self.assertEqual(artifact["problem_type"], "regression")
        self.assertIsNotNone(artifact["preprocessor"])

    @patch("src.modules.trainings.service.MapReduceManager.get_driver")
    @patch("src.modules.trainings.service.TrainingService._dispatch_and_collect_tasks")
    async def test_train_automl_pipeline_time_series(self, mock_dispatch, mock_driver):
        mock_driver.return_value = AsyncMock()
        from src.modules.models.service import ModelService
        from src.modules.preprocessing import build_time_series_pipeline

        pipe = build_time_series_pipeline(Ridge())
        # Fit dummy data so pipe is fitted
        pipe.fit(pd.DataFrame({"feat": [1.0, 2.0, 3.0]}), np.array([1.0, 2.0, 3.0]))

        mock_dispatch.return_value = [
            {
                "model_name": "Ridge",
                "scores": {"r2": 0.91, "mse": 5.0},
                "best_params": {"alpha": 1.0},
                "model_bytes": ModelService.serialize_model(pipe),
            }
        ]

        dates = pd.date_range("2024-01-01", periods=30, freq="D")
        df = pd.DataFrame({
            "timestamp": dates,
            "target": np.linspace(10, 20, 30),
            "feat": np.linspace(20, 30, 30),
        })

        result = await TrainingService.train_automl_pipeline(
            df=df,
            target_col="target",
            metric_sort="r2",
            problem_type=constants.ProblemType.TIME_SERIES,
        )

        self.assertIsNotNone(result.best_model)
        self.assertEqual(result.best_model, "Ridge")
        self.assertEqual(result.best_score, 0.91)
        self.assertIsNotNone(result.best_model_bytes)

        artifact = pickle.loads(result.best_model_bytes)
        self.assertEqual(artifact["problem_type"], constants.ProblemType.TIME_SERIES)
        self.assertIsInstance(artifact["model"], TimeSeriesForecaster)

    @patch("src.modules.trainings.service.TrainingService.train_automl_pipeline")
    async def test_process_training_job_pipeline_flow(self, mock_pipeline):
        from src.modules.trainings.schemas import AutoMLPipelineResult
        from src.modules.preprocessing.schemas import CVStrategyConfig
        from src.modules.trainings.schemas import ModelScoreItem

        mock_pipeline.return_value = AutoMLPipelineResult(
            best_model_id=0,
            best_model="DecisionTreeClassifier",
            best_score=0.95,
            best_params={},
            best_model_bytes=b"fake_model_bytes",
            feature_names=["f1", "f2"],
            model_scores=[
                ModelScoreItem(model_id=0, model_name="DecisionTreeClassifier", scores={"accuracy": 0.95}, best_params={})
            ],
            cv_strategy=CVStrategyConfig(tier=1, name="StratifiedKFold", n_splits=5, description="5-fold CV"),
        )

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
                    "problem_type": "classification",
                    "target": "target",
                    "metric_sort": "accuracy",
                    "list_feature": ["sepal length (cm)", "sepal width (cm)", "petal length (cm)", "petal width (cm)"]
                }
            )

            self.assertIn("best_model", result)
            self.assertIn("best_score", result)
            mock_minio.get_object.assert_called_once_with("datasets", "iris.parquet")
            mock_minio.upload_object.assert_called_once()
            mock_repo.update_success.assert_called_once()
            mock_notif.push_notification.assert_called_once()


class TestTrainingExecutor(unittest.TestCase):
    def test_build_trainable_model_classification(self):
        param_grid = [{"max_depth": [3, 5]}]
        model, grid = build_trainable_model(DecisionTreeClassifier, param_grid, constants.ProblemType.CLASSIFICATION)
        self.assertIsInstance(model, DecisionTreeClassifier)
        self.assertEqual(grid, param_grid)

    def test_build_trainable_model_time_series(self):
        param_grid = [{"alpha": [0.1, 1.0]}]
        model, grid = build_trainable_model(Ridge, param_grid, constants.ProblemType.TIME_SERIES)
        self.assertIsInstance(model, Pipeline)
        self.assertEqual(grid, [{"model__alpha": [0.1, 1.0]}])

    def test_evaluate_trained_model(self):
        mock_search = MagicMock()
        mock_search.cv_results_ = {"mean_test_r2": [0.85]}
        mock_search.best_index_ = 0
        mock_search.best_score_ = 0.85

        scores, primary = evaluate_trained_model(
            best_estimator=MagicMock(),
            search=mock_search,
            test_data_bytes=None,
            metric_list=["r2"],
            metric_sort="r2",
        )
        self.assertEqual(scores, {"r2": 0.85})
        self.assertEqual(primary, 0.85)

    def test_tune_and_fit_model_strips_pipeline_prefix(self):
        from src.modules.preprocessing import build_time_series_pipeline
        from src.modules.models.service import ModelService

        pipe = build_time_series_pipeline(Ridge())
        X = pd.DataFrame({"feat": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]})
        y = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
        cv = KFold(n_splits=2)
        scoring = ModelService.build_scoring_dict(["r2"], problem_type=constants.ProblemType.REGRESSION)
        param_grid = [{"model__alpha": [0.1, 1.0]}]

        best_estimator, best_params, search = tune_and_fit_model(
            estimator=pipe,
            param_grid=param_grid,
            cv=cv,
            scoring=scoring,
            metric_sort="r2",
            X_train=X,
            y_train=y,
        )
        self.assertIsNotNone(best_estimator)
        self.assertIn("alpha", best_params)
        self.assertNotIn("model__alpha", best_params)

    def test_tune_and_fit_model_generic(self):
        from src.modules.models.service import ModelService
        X = np.array([[1.0], [2.0], [3.0], [4.0], [5.0], [6.0]])
        y = np.array([0, 0, 0, 1, 1, 1])
        cv = KFold(n_splits=2)
        scoring = ModelService.build_scoring_dict(["accuracy"], problem_type=constants.ProblemType.CLASSIFICATION)
        param_grid = [{"max_depth": [2, 3]}]

        best_estimator, best_params, search = tune_and_fit_model(
            estimator=DecisionTreeClassifier(),
            param_grid=param_grid,
            cv=cv,
            scoring=scoring,
            metric_sort="accuracy",
            X_train=X,
            y_train=y,
        )

        self.assertIsNotNone(best_estimator)
        self.assertIn("max_depth", best_params)
        self.assertIsNotNone(search)


if __name__ == "__main__":
    unittest.main()
