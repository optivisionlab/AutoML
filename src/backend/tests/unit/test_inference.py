import io
import json
import pickle
import zipfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from src.core.exceptions import CustomException
from src.modules.preprocessing import TabularPreprocessor
from src.modules.inference.registry import InferenceModelRegistry
from src.modules.inference.service import InferenceService
from src.modules.inference.schemas import PredictRequest


class TestInferenceModelRegistry(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        InferenceModelRegistry.clear()

    async def test_cache_and_eviction(self):
        clf = RandomForestClassifier(n_estimators=10)
        clf.fit([[1, 2], [3, 4]], [0, 1])
        model_bytes = pickle.dumps(clf)

        job_id = "job_123"
        storage_info = {"bucket_name": "models", "object_name": "path/model.pkl"}

        with patch("src.shared.minio_service.get_object", new_callable=AsyncMock) as mock_get_object:
            mock_get_object.return_value = model_bytes

            model1 = await InferenceModelRegistry.get_model(job_id, storage_info)
            self.assertIsNotNone(model1)
            mock_get_object.assert_called_once()

            mock_get_object.reset_mock()
            model2 = await InferenceModelRegistry.get_model(job_id, storage_info)
            self.assertEqual(model1, model2)
            mock_get_object.assert_not_called()

            evicted = InferenceModelRegistry.evict_model(job_id)
            self.assertTrue(evicted)
            self.assertNotIn(job_id, InferenceModelRegistry._cache)


class TestInferenceService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_db = MagicMock()
        self.mock_jobs = MagicMock()
        self.mock_jobs.find_one = AsyncMock()
        self.mock_jobs.update_one = AsyncMock()
        self.mock_jobs.count_documents = AsyncMock()
        self.mock_db.tbl_Job = self.mock_jobs
        self.service = InferenceService(self.mock_db)

        self.user_oid = ObjectId()
        self.current_user = {
            "_id": self.user_oid,
            "username": "tester",
            "role": "user",
        }

        # Train a mock dataset with preprocessor bundle
        raw_df = pd.DataFrame({
            "feature_x": [1.0, 3.0, 5.0, 7.0],
            "feature_y": [2.0, 4.0, 6.0, 8.0],
            "category_col": ["red", "blue", "red", "blue"],
            "target_col": ["ClassA", "ClassB", "ClassA", "ClassB"],
        })
        (X_train, y_train), _, _, feature_cols, self.preprocessor = TabularPreprocessor.prepare_data(
            df=raw_df,
            target_col="target_col",
        )

        self.model = RandomForestClassifier(n_estimators=10, random_state=42)
        self.model.fit(X_train, y_train)

        self.artifact = {
            "model": self.model,
            "preprocessor": self.preprocessor,
            "feature_names": feature_cols,
            "target_name": "target_col",
            "problem_type": "classification",
        }
        self.artifact_bytes = pickle.dumps(self.artifact)

        self.job_oid = ObjectId()
        self.job_id = str(self.job_oid)
        self.mock_job_doc = {
            "_id": self.job_oid,
            "user": {"id": str(self.user_oid), "name": "tester"},
            "status": 1,
            "activate": 1,
            "best_model": "RandomForestClassifier",
            "best_score": 0.95,
            "best_params": {"n_estimators": 10},
            "model": {"bucket_name": "models", "object_name": f"{self.user_oid}/{self.job_id}/model.pkl"},
            "config": {
                "list_feature": feature_cols,
                "target": "target_col",
            },
        }

    async def test_toggle_model_activation(self):
        self.mock_jobs.find_one.return_value = self.mock_job_doc
        self.mock_jobs.update_one.return_value = MagicMock(modified_count=1)

        resp = await self.service.toggle_model_activation(
            current_user=self.current_user,
            job_id=self.job_id,
            activate=0,
            base_url="http://api.hautoml.com",
        )
        self.assertEqual(resp.activate, 0)
        self.assertEqual(resp.status, "INACTIVE")
        self.mock_jobs.update_one.assert_called()

        resp2 = await self.service.toggle_model_activation(
            current_user=self.current_user,
            job_id=self.job_id,
            activate=1,
            base_url="http://api.hautoml.com",
        )
        self.assertEqual(resp2.activate, 1)
        self.assertEqual(resp2.status, "ACTIVE")
        self.assertIn("curl", resp2.code_snippets.curl)
        self.assertIn("import requests", resp2.code_snippets.python)

    async def test_get_deployment_info(self):
        self.mock_jobs.find_one.return_value = self.mock_job_doc

        info = await self.service.get_deployment_info(
            current_user=self.current_user,
            job_id=self.job_id,
            base_url="http://localhost:9999",
        )
        self.assertEqual(info.job_id, self.job_id)
        self.assertEqual(info.model_name, "RandomForestClassifier")
        self.assertEqual(info.features, ["feature_x", "feature_y", "category_col"])
        self.assertIn("curl -X POST", info.code_snippets.curl)
        self.assertIn("fetch(", info.code_snippets.javascript)
        self.assertIn("HttpClient", info.code_snippets.csharp)
        self.assertIn("curl_init", info.code_snippets.php)

    @patch("src.shared.minio_service.get_object", new_callable=AsyncMock)
    async def test_predict_success_with_decoded_labels(self, mock_get_object):
        mock_get_object.return_value = self.artifact_bytes
        self.mock_jobs.find_one.return_value = self.mock_job_doc

        req = PredictRequest(
            data=[
                {"feature_x": 1.5, "feature_y": 2.5, "category_col": "red"},
                {"feature_x": 6.5, "feature_y": 7.5, "category_col": "blue"},
            ]
        )

        res = await self.service.predict(
            current_user=self.current_user,
            job_id=self.job_id,
            request=req,
        )

        self.assertEqual(res.total_samples, 2)
        self.assertEqual(len(res.predictions), 2)
        self.assertIn(res.predictions[0], ["ClassA", "ClassB"])
        self.assertIn(res.predictions[1], ["ClassA", "ClassB"])
        self.assertGreaterEqual(res.latency_ms, 0.0)

    async def test_predict_when_inactive_raises_forbidden(self):
        inactive_job = dict(self.mock_job_doc)
        inactive_job["activate"] = 0
        self.mock_jobs.find_one.return_value = inactive_job

        req = PredictRequest(data=[{"feature_x": 1.0, "feature_y": 2.0, "category_col": "red"}])

        with self.assertRaises(CustomException) as ctx:
            await self.service.predict(
                current_user=self.current_user,
                job_id=self.job_id,
                request=req,
            )
        self.assertEqual(ctx.exception.status_code, 403)

    async def test_predict_missing_columns_raises_bad_request(self):
        self.mock_jobs.find_one.return_value = self.mock_job_doc

        with patch("src.shared.minio_service.get_object", new_callable=AsyncMock) as mock_get_object:
            mock_get_object.return_value = self.artifact_bytes

            req = PredictRequest(data=[{"feature_x": 1.0}])

            with self.assertRaises(CustomException) as ctx:
                await self.service.predict(
                    current_user=self.current_user,
                    job_id=self.job_id,
                    request=req,
                )
            self.assertEqual(ctx.exception.status_code, 400)

    @patch("src.shared.minio_service.get_object", new_callable=AsyncMock)
    async def test_predict_file_csv_success(self, mock_get_object):
        mock_get_object.return_value = self.artifact_bytes
        self.mock_jobs.find_one.return_value = self.mock_job_doc

        csv_content = b"feature_x,feature_y,category_col\n1.5,2.5,red\n6.5,7.5,blue\n"
        mock_file = AsyncMock()
        mock_file.filename = "test_data.csv"
        mock_file.read.return_value = csv_content

        filename, media_type, buffer = await self.service.predict_file(
            current_user=self.current_user,
            job_id=self.job_id,
            file=mock_file,
        )

        self.assertEqual(filename, "predicted_test_data.csv")
        self.assertEqual(media_type, "text/csv")
        df_out = pd.read_csv(buffer)
        self.assertEqual(len(df_out), 2)
        self.assertIn("prediction", df_out.columns)
        self.assertEqual(len(df_out["prediction"]), 2)
        self.assertIn(df_out["prediction"].iloc[0], ["ClassA", "ClassB"])

    @patch("src.shared.minio_service.get_object", new_callable=AsyncMock)
    async def test_predict_file_excel_success(self, mock_get_object):
        mock_get_object.return_value = self.artifact_bytes
        self.mock_jobs.find_one.return_value = self.mock_job_doc

        df_in = pd.DataFrame({
            "feature_x": [1.5, 6.5],
            "feature_y": [2.5, 7.5],
            "category_col": ["red", "blue"]
        })
        excel_buf = io.BytesIO()
        df_in.to_excel(excel_buf, index=False, engine="openpyxl")
        excel_buf.seek(0)

        mock_file = AsyncMock()
        mock_file.filename = "test_data.xlsx"
        mock_file.read.return_value = excel_buf.getvalue()

        filename, media_type, buffer = await self.service.predict_file(
            current_user=self.current_user,
            job_id=self.job_id,
            file=mock_file,
        )

        self.assertEqual(filename, "predicted_test_data.xlsx")
        self.assertIn("spreadsheetml", media_type)
        df_out = pd.read_excel(buffer)
        self.assertEqual(len(df_out), 2)
        self.assertIn("prediction", df_out.columns)

    async def test_export_notebook(self):
        self.mock_jobs.find_one.return_value = self.mock_job_doc

        filename, nb_bytes = await self.service.export_notebook(
            current_user=self.current_user,
            job_id=self.job_id,
        )
        self.assertTrue(filename.endswith(".ipynb"))
        nb_dict = json.loads(nb_bytes.decode("utf-8"))
        self.assertEqual(nb_dict["nbformat"], 4)
        self.assertGreater(len(nb_dict["cells"]), 0)

    @patch("src.shared.minio_service.get_object", new_callable=AsyncMock)
    async def test_export_docker_package(self, mock_get_object):
        mock_get_object.return_value = self.artifact_bytes
        self.mock_jobs.find_one.return_value = self.mock_job_doc

        filename, zip_bytes = await self.service.export_docker_package(
            current_user=self.current_user,
            job_id=self.job_id,
        )
        self.assertTrue(filename.endswith(".zip"))

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            file_list = z.namelist()
            self.assertIn("model.pkl", file_list)
            self.assertIn("app.py", file_list)
            self.assertIn("requirements.txt", file_list)
            self.assertIn("Dockerfile", file_list)
            self.assertIn("README.md", file_list)

            app_code = z.read("app.py").decode("utf-8")
            self.assertIn("FastAPI", app_code)
            self.assertIn("model.predict", app_code)

    @patch("src.shared.minio_service.get_object", new_callable=AsyncMock)
    async def test_export_model_binary(self, mock_get_object):
        mock_get_object.return_value = self.artifact_bytes
        self.mock_jobs.find_one.return_value = self.mock_job_doc

        filename, binary_bytes = await self.service.export_model_binary(
            current_user=self.current_user,
            job_id=self.job_id,
        )
        self.assertTrue(filename.endswith(".pkl"))
        self.assertEqual(binary_bytes, self.artifact_bytes)

    async def test_get_user_jobs_all(self):
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.to_list = AsyncMock(return_value=[self.mock_job_doc])

        self.mock_jobs.count_documents.return_value = 1
        self.mock_jobs.find.return_value = mock_cursor

        jobs, meta = await self.service.get_user_jobs(
            user_id=str(self.user_oid),
            current_page=1,
            page_size=10,
            activate=None,
            data_name="iris",
            sort_name="asc",
            sort_time="desc",
        )

        self.assertEqual(len(jobs), 1)
        self.assertEqual(meta["total_items"], 1)
        self.assertEqual(jobs[0].id, self.job_id)
        self.mock_jobs.count_documents.assert_called_once()
        query_arg = self.mock_jobs.count_documents.call_args[0][0]
        self.assertNotIn("activate", query_arg)
        self.assertEqual(query_arg["data.name"]["$regex"], "iris")

    async def test_get_user_jobs_active_models(self):
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.skip.return_value = mock_cursor
        mock_cursor.limit.return_value = mock_cursor
        mock_cursor.to_list = AsyncMock(return_value=[self.mock_job_doc])

        self.mock_jobs.count_documents.return_value = 1
        self.mock_jobs.find.return_value = mock_cursor

        models, meta = await self.service.get_user_jobs(
            user_id=str(self.user_oid),
            current_page=1,
            page_size=10,
            activate=1,
        )

        self.assertEqual(len(models), 1)
        self.assertEqual(meta["total_items"], 1)
        self.mock_jobs.count_documents.assert_called()
        query_arg = self.mock_jobs.count_documents.call_args[0][0]
        self.assertEqual(query_arg["activate"], 1)


if __name__ == "__main__":
    unittest.main()
