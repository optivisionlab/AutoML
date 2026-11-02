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
    clean_best_params,
)
from src.modules.trainings.pipeline import PIPELINE_NODES, PipelineTracker, build_trials, pipeline_from_job


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


class TestPipelineTrials(unittest.TestCase):
    def test_build_trials_normalizes_scores(self):
        history = [
            {"params": {"alpha": 0.1}, "scores": {"mse": -2.5, "r2": 0.8}, "is_pruned": False},
            {"params": {"alpha": 1.0}, "scores": {"mse": -1e6, "r2": float("nan")}, "is_pruned": False},
            {"params": {"alpha": 10.0}, "scores": {"mse": -1e6, "r2": -1e6}, "is_pruned": True},
        ]
        trials, best_trial = build_trials(history, best_index=0, metric_list=["mse", "r2"])

        self.assertEqual(best_trial, 0)
        self.assertEqual(trials[0], {"params": {"alpha": 0.1}, "status": "succeeded", "scores": {"mse": 2.5, "r2": 0.8}})
        self.assertEqual(trials[1]["scores"], {"mse": None, "r2": None})
        self.assertEqual(trials[2]["status"], "pruned")
        self.assertEqual(trials[2]["scores"], {"mse": None, "r2": None})

    def test_build_trials_deduplicates_and_remaps_best(self):
        history = [
            {"params": {"model__alpha": 1.0}, "scores": {"r2": 0.5}},
            {"params": {"model__alpha": 2.0}, "scores": {"r2": 0.7}},
            {"params": {"model__alpha": 1.0}, "scores": {"r2": 0.5}},
            {"params": {"model__alpha": 3.0}, "scores": {"r2": 0.9}},
        ]
        trials, best_trial = build_trials(history, best_index=3, metric_list=["r2"], clean_params=clean_best_params)

        self.assertEqual([t["params"] for t in trials], [{"alpha": 1.0}, {"alpha": 2.0}, {"alpha": 3.0}])
        self.assertEqual(best_trial, 2)

    def test_build_trials_from_real_search(self):
        from src.modules.models.service import ModelService

        X, y = load_diabetes(return_X_y=True)
        scoring = ModelService.build_scoring_dict(["mse", "r2"], problem_type=constants.ProblemType.REGRESSION)
        _, best_params, search = tune_and_fit_model(
            estimator=Ridge(),
            param_grid=[{"alpha": [0.01, 1.0, 100.0]}],
            cv=KFold(n_splits=3, shuffle=True, random_state=42),
            scoring=scoring,
            metric_sort="r2",
            X_train=X,
            y_train=y,
        )
        trials, best_trial = build_trials(search.trials_history_, search.best_index_, ["mse", "r2"])

        self.assertEqual(len(trials), 3)
        self.assertEqual(trials[best_trial]["params"], best_params)
        self.assertTrue(all(t["scores"]["mse"] > 0 for t in trials))
        best_r2 = trials[best_trial]["scores"]["r2"]
        self.assertEqual(best_r2, max(t["scores"]["r2"] for t in trials))

    def test_tracker_abort_marks_running_and_skips_queued(self):
        tracker = PipelineTracker("job", "data", "regression", "grid_search", "r2", "y", ["x"], None)
        tracker.set_models(["r2"], ["Ridge", "Lasso"], "r2")
        tracker.finish("read_dataset")
        tracker.start("preprocessing")
        tracker.abort("boom")
        pipeline = tracker.to_dict()

        self.assertEqual(pipeline["status"], "failed")
        self.assertEqual(pipeline["error"], {"message": "boom"})
        self.assertEqual(pipeline["read_dataset"]["status"], "succeeded")
        self.assertEqual(pipeline["preprocessing"]["status"], "failed")
        self.assertEqual(pipeline["preprocessing"]["error"], {"message": "boom"})
        self.assertEqual(pipeline["save_result"]["status"], "skipped")
        self.assertEqual(pipeline["train"]["output"]["models"]["Ridge"]["status"], "failed")


class TestPipelineFromJob(unittest.TestCase):
    def _job(self, **fields):
        return {
            "_id": ObjectId(),
            "config": {"problem_type": "regression", "target": "y", "list_feature": ["x"], "metric_sort": "r2"},
            "data": {"id": "data-1", "name": "demo"},
            **fields,
        }

    def test_queued_job_has_all_nodes_queued(self):
        job = self._job(status=constants.JobStatus.RUNNING)
        pipeline = pipeline_from_job(job)

        self.assertEqual(pipeline["job_id"], str(job["_id"]))
        self.assertEqual(pipeline["source"], "tracked")
        self.assertEqual(pipeline["status"], "queued")
        self.assertEqual(pipeline["read_dataset"]["params"]["id_data"], "data-1")
        self.assertTrue(all(pipeline[key]["status"] == "queued" for key in PIPELINE_NODES))

    def test_legacy_success_job_has_one_trial_per_model(self):
        job = self._job(
            status=constants.JobStatus.SUCCESS,
            best_model="Ridge",
            model={"bucket_name": "models", "object_name": "u/j/Ridge_1.pkl"},
            orther_model_scores=[
                {"model_id": 0, "model_name": "Ridge", "scores": {"r2": 0.8, "mse": 0.2}, "best_params": {"alpha": 1.0}},
                {"model_id": 1, "model_name": "Lasso", "scores": {"r2": 0.5, "mse": -0.4}, "best_params": {}},
            ],
        )
        pipeline = pipeline_from_job(job)
        models = pipeline["train"]["output"]["models"]

        self.assertEqual(pipeline["source"], "legacy")
        self.assertEqual(pipeline["status"], "succeeded")
        self.assertEqual(pipeline["model_selection"]["params"]["metrics"], {"r2": "maximize", "mse": "minimize"})
        self.assertEqual(models["Ridge"]["best_trial"], 0)
        self.assertEqual(models["Ridge"]["trials"], [
            {"params": {"alpha": 1.0}, "status": "succeeded", "scores": {"r2": 0.8, "mse": 0.2}},
        ])
        self.assertEqual(models["Lasso"]["trials"][0]["scores"]["mse"], 0.4)
        self.assertEqual(pipeline["select_best"]["output"], {"best_model": "Ridge", "score_source": None})
        self.assertEqual(pipeline["save_result"]["output"]["object_name"], "u/j/Ridge_1.pkl")
        self.assertTrue(all(pipeline[key]["status"] == "succeeded" for key in PIPELINE_NODES))

    def test_old_engine_job_document(self):
        # Shape written by the previous automl/engine.py: model bytes inline, estimator repr, no Kafka fields
        job = self._job(
            job_id="1f0c-uuid",
            status=1,
            best_model="RandomForestClassifier(max_depth=5)",
            model=pickle.dumps(DecisionTreeClassifier()),
            orther_model_scores=[
                {"model_id": 0, "model_name": "RandomForestClassifier", "best_params": {"max_depth": 5}, "scores": {"accuracy": 0.93}},
                "not-a-model-entry",
            ],
            time_limit_reached=False,
        )
        pipeline = pipeline_from_job(job)

        self.assertEqual(pipeline["status"], "succeeded")
        self.assertEqual(pipeline["select_best"]["output"]["best_model"], "RandomForestClassifier")
        self.assertIsNone(pipeline["save_result"]["output"]["object_name"])
        self.assertEqual(list(pipeline["train"]["output"]["models"]), ["RandomForestClassifier"])

    def test_string_status_and_missing_fields(self):
        job = {"_id": ObjectId(), "status": "-1", "infor": "boom", "config": None, "data": "legacy-id"}
        pipeline = pipeline_from_job(job)

        self.assertEqual(pipeline["status"], "failed")
        self.assertEqual(pipeline["error"], {"message": "boom"})
        self.assertIsNone(pipeline["read_dataset"]["params"]["id_data"])

    def test_legacy_failed_job_keeps_error(self):
        pipeline = pipeline_from_job(self._job(status=constants.JobStatus.FAILED, infor="No data"))

        self.assertEqual(pipeline["status"], "failed")
        self.assertEqual(pipeline["error"], {"message": "No data"})
        self.assertTrue(all(pipeline[key]["status"] == "skipped" for key in PIPELINE_NODES))


class TestTrainingPipelineTracking(unittest.IsolatedAsyncioTestCase):
    @patch("src.modules.trainings.service.MapReduceManager.get_driver")
    @patch("src.modules.trainings.service.TrainingService._dispatch_and_collect_tasks")
    async def test_train_automl_pipeline_fills_tracker(self, mock_dispatch, mock_driver):
        from src.modules.models.service import ModelService
        from sklearn.linear_model import LinearRegression

        mock_driver.return_value = AsyncMock()
        mock_dispatch.return_value = [{
            "model_name": "LinearRegression",
            "scores": {"r2": 0.85, "mse": 12.5},
            "best_params": {"fit_intercept": True},
            "model_bytes": ModelService.serialize_model(LinearRegression().fit([[0], [1]], [0.0, 1.0])),
            "trials": [
                {"params": {"fit_intercept": True}, "status": "succeeded", "scores": {"r2": 0.85}},
                {"params": {"fit_intercept": False}, "status": "succeeded", "scores": {"r2": 0.40}},
            ],
            "best_trial": 0,
        }]
        tracker = PipelineTracker("job", "data", "regression", "grid_search", "r2", "target", None, None)
        on_progress = AsyncMock()

        with patch("src.modules.trainings.service.search_space.REGRESSION_MODELS",
                   {"LinearRegression": [{}], "Lasso": [{}]}):
            await TrainingService.train_automl_pipeline(
                df=load_diabetes(as_frame=True).frame,
                target_col="target",
                metric_sort="r2",
                problem_type="regression",
                tracker=tracker,
                on_progress=on_progress,
            )

        pipeline = tracker.to_dict()
        models = pipeline["train"]["output"]["models"]
        self.assertEqual(pipeline["split_holdout_data"]["status"], "skipped")
        self.assertEqual(pipeline["split_holdout_data"]["output"]["holdout_rows"], 0)
        self.assertEqual(pipeline["preprocessing"]["status"], "succeeded")
        self.assertEqual(len(pipeline["preprocessing"]["output"]["column_types"]["numeric"]), 10)
        self.assertIsNone(pipeline["preprocessing"]["output"]["class_distribution"])
        self.assertEqual(pipeline["model_selection"]["params"]["metrics"]["mse"], "minimize")
        self.assertEqual(models["LinearRegression"]["status"], "succeeded")
        self.assertEqual(models["LinearRegression"]["best_trial"], 0)
        self.assertEqual(len(models["LinearRegression"]["trials"]), 2)
        self.assertIsNone(models["LinearRegression"]["holdout_scores"])
        self.assertEqual(models["Lasso"]["status"], "failed")
        self.assertEqual(pipeline["select_best"]["output"], {"best_model": "LinearRegression", "score_source": "cv"})
        on_progress.assert_awaited()

    @patch("src.modules.trainings.service.MapReduceManager.get_driver")
    @patch("src.modules.trainings.service.TrainingService._dispatch_and_collect_tasks")
    async def test_train_automl_pipeline_fills_tracker_for_classification_with_holdout(self, mock_dispatch, mock_driver):
        from src.modules.models.service import ModelService
        from sklearn.naive_bayes import GaussianNB

        mock_driver.return_value = AsyncMock()
        mock_dispatch.return_value = [{
            "model_name": "GaussianNB",
            "scores": {"accuracy": 0.9, "f1_macro": 0.88},
            "best_params": {"var_smoothing": 1e-9},
            "model_bytes": ModelService.serialize_model(GaussianNB().fit([[0], [1]], [0, 1])),
            "trials": [{"params": {"var_smoothing": 1e-9}, "status": "succeeded", "scores": {"accuracy": 0.86, "f1_macro": 0.85}}],
            "best_trial": 0,
        }]
        # More than 10,000 rows selects the train/test split tier
        rng = np.random.default_rng(0)
        df = pd.DataFrame({"x1": rng.normal(size=10_500), "x2": rng.normal(size=10_500)})
        df["label"] = np.where(df["x1"] > 0.5, "yes", "no")
        df.loc[:9, "label"] = None
        tracker = PipelineTracker("job", "data", "classification", "grid_search", "f1_macro", "label", None, None)

        with patch("src.modules.trainings.service.search_space.CLASSIFICATION_MODELS", {"GaussianNB": [{}]}):
            await TrainingService.train_automl_pipeline(
                df=df,
                target_col="label",
                metric_sort="f1_macro",
                problem_type="classification",
                tracker=tracker,
            )

        pipeline = tracker.to_dict()
        model = pipeline["train"]["output"]["models"]["GaussianNB"]
        counts = df["label"].value_counts()
        self.assertEqual(pipeline["split_holdout_data"]["status"], "succeeded")
        self.assertEqual(pipeline["split_holdout_data"]["output"]["holdout_rows"], 2098)
        self.assertEqual(pipeline["preprocessing"]["output"]["dropped_rows"], 10)
        self.assertEqual(pipeline["preprocessing"]["output"]["class_distribution"],
                         {"no": int(counts["no"]), "yes": int(counts["yes"])})
        self.assertEqual(pipeline["model_selection"]["params"]["cv"]["name"], "TrainTestSplit+StratifiedKFold")
        self.assertTrue(all(d == "maximize" for d in pipeline["model_selection"]["params"]["metrics"].values()))
        self.assertEqual(model["trials"][0]["scores"]["f1_macro"], 0.85)
        self.assertEqual(model["holdout_scores"], {"accuracy": 0.9, "f1_macro": 0.88})
        self.assertEqual(pipeline["select_best"]["output"], {"best_model": "GaussianNB", "score_source": "holdout"})

    @patch("src.modules.trainings.service.MapReduceManager.get_driver")
    async def test_preprocessing_failure_marks_only_preprocessing(self, mock_driver):
        mock_driver.return_value = AsyncMock()
        tracker = PipelineTracker("job", "data", "classification", "grid_search", "accuracy", "missing", None, None)
        tracker.finish("read_dataset")

        with self.assertRaises(ValueError):
            await TrainingService.train_automl_pipeline(
                df=load_iris(as_frame=True).frame,
                target_col="missing",
                metric_sort="accuracy",
                problem_type="classification",
                tracker=tracker,
            )
        tracker.abort("Target column 'missing' not found")
        pipeline = tracker.to_dict()

        self.assertEqual(pipeline["preprocessing"]["status"], "failed")
        self.assertEqual(pipeline["preprocessing"]["error"], {"message": "Target column 'missing' not found"})
        self.assertEqual(pipeline["split_holdout_data"]["status"], "skipped")
        self.assertIsNone(pipeline["split_holdout_data"]["error"])
        self.assertTrue(all(pipeline[key]["status"] == "skipped" for key in ("model_selection", "train", "select_best", "save_result")))

    async def _run_job(self, train_side_effect):
        df = load_iris(as_frame=True).frame
        parquet_buf = io.BytesIO()
        df.to_parquet(parquet_buf, index=False)

        mock_repo = AsyncMock()
        mock_repo.get_dataset_info.return_value = {
            "dataName": "Iris",
            "data_link": {"bucket_name": "datasets", "object_name": "iris.parquet"},
        }
        service = TrainingService(repo=mock_repo, notif_service=AsyncMock())

        with patch("src.modules.trainings.service.minio_service") as mock_minio, \
                patch("src.modules.trainings.service.TrainingService.train_automl_pipeline", side_effect=train_side_effect):
            mock_minio.get_object = AsyncMock(return_value=parquet_buf.getvalue())
            mock_minio.upload_object = AsyncMock()
            try:
                await service.process_training_job("job_1", "ds_1", "user_1", {"problem_type": "classification", "target": "target"})
            except ValueError:
                pass

        return mock_repo.update_pipeline.call_args_list[-1].args[1]

    async def test_process_training_job_saves_succeeded_pipeline(self):
        from src.modules.trainings.schemas import AutoMLPipelineResult, ModelScoreItem
        from src.modules.preprocessing.schemas import CVStrategyConfig

        result = AutoMLPipelineResult(
            best_model_id=0,
            best_model="DecisionTreeClassifier",
            best_score=0.95,
            best_params={},
            best_model_bytes=b"fake_model_bytes",
            feature_names=["f1"],
            model_scores=[ModelScoreItem(model_id=0, model_name="DecisionTreeClassifier", scores={"accuracy": 0.95}, best_params={})],
            cv_strategy=CVStrategyConfig(tier=1, name="StratifiedKFold", n_splits=5, description="5-fold CV"),
        )
        pipeline = await self._run_job(AsyncMock(return_value=result))

        self.assertEqual(pipeline["status"], "succeeded")
        self.assertEqual(pipeline["read_dataset"]["output"]["data_url"], "datasets/iris.parquet")
        self.assertEqual(pipeline["save_result"]["output"]["object_name"], "user_1/job_1/DecisionTreeClassifier_1.pkl")

    async def test_process_training_job_saves_failed_pipeline(self):
        pipeline = await self._run_job(ValueError("no results"))

        self.assertEqual(pipeline["status"], "failed")
        self.assertEqual(pipeline["read_dataset"]["status"], "succeeded")
        self.assertEqual(pipeline["save_result"]["status"], "skipped")


class TestTrainingRepositoryPipeline(unittest.IsolatedAsyncioTestCase):
    async def test_update_pipeline(self):
        mock_db = MagicMock()
        mock_db.tbl_Job = AsyncMock()
        repo = TrainingRepository(mock_db)
        job_oid = ObjectId()

        await repo.update_pipeline(str(job_oid), {"status": "running"})
        mock_db.tbl_Job.update_one.assert_called_once_with({"_id": job_oid}, {"$set": {"pipeline": {"status": "running"}}})


if __name__ == "__main__":
    unittest.main()
