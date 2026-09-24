import unittest
import numpy as np
import pandas as pd

from src.modules.preprocessing import (
    TabularPreprocessor,
    FittedPreprocessor,
    preprocess_classification_data,
    preprocess_regression_data,
    determine_classification_cv_tier,
    determine_regression_cv_tier,
    prepare_classification_data,
    prepare_regression_data,
)
from src.modules.models.service import ModelService, LOWER_IS_BETTER_METRICS
from src.modules.models.registry import MODEL_CLASS_MAP


class TestPreprocessingPipeline(unittest.TestCase):
    def test_classification_preprocessing(self):
        df = pd.DataFrame({
            "num_feat": [1.0, 2.0, np.nan, 4.0, 5.0, 6.0],
            "cat_feat": ["cat", "dog", "cat", "bird", "dog", "bird"],
            "text_feat": ["apple pie", "orange juice", "apple tart", "lemon juice", "sweet orange", "lemon pie"],
            "target": ["A", "B", "A", "B", "A", "B"]
        })
        
        (X_train, y_train), holdout_data, cv_strategy, feature_names, preprocessor = (
            TabularPreprocessor.prepare_data(df, target_col="target", problem_type="classification")
        )
        
        self.assertEqual(preprocessor.problem_type, "classification")
        self.assertIsNotNone(preprocessor.preprocessor)
        self.assertIsNotNone(preprocessor.target_encoder)
        self.assertEqual(len(feature_names), 3)
        self.assertEqual(y_train.ndim, 1)
        self.assertIsNone(holdout_data)  # Tier 1 has no holdout
        
        # Test transform on new data
        test_df = pd.DataFrame({
            "num_feat": [2.5],
            "cat_feat": ["dog"],
            "text_feat": ["orange juice"]
        })
        X_test = preprocessor.transform(test_df)
        self.assertIsInstance(X_test, np.ndarray)
        
        # Test inverse transform target
        inv = preprocessor.inverse_transform_target(np.array([0, 1]))
        self.assertEqual(list(inv), ["A", "B"])

    def test_regression_preprocessing(self):
        df = pd.DataFrame({
            "num_feat": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0],
            "cat_feat": ["low", "high", "low", "medium", "high", "medium", "low", "high"],
            "target": [100.5, 200.0, 305.2, 410.0, 500.1, 620.0, 710.5, 805.0]
        })
        
        (X_train, y_train), holdout_data, cv_strategy, feature_names, preprocessor = (
            TabularPreprocessor.prepare_data(df, target_col="target", problem_type="regression")
        )
        
        self.assertEqual(preprocessor.problem_type, "regression")
        self.assertIsNone(preprocessor.target_encoder)
        self.assertEqual(len(feature_names), 2)
        self.assertEqual(y_train.dtype, np.float64)
        self.assertIsNone(holdout_data)  # Tier 1 has no holdout
        
        # Test transform on new data
        test_df = pd.DataFrame({
            "num_feat": [45.0],
            "cat_feat": ["medium"]
        })
        X_test = preprocessor.transform(test_df)
        self.assertIsInstance(X_test, np.ndarray)
        
        # Test inverse transform target (identity for regression)
        preds = np.array([123.45, 678.90])
        inv = preprocessor.inverse_transform_target(preds)
        np.testing.assert_array_almost_equal(inv, preds)

    def test_models_service_metrics(self):
        from sklearn.dummy import DummyRegressor
        X = np.array([[1], [2], [3]])
        y = np.array([10.0, 20.0, 30.0])
        model = DummyRegressor(strategy="mean")
        model.fit(X, y)
        
        metrics = ModelService.evaluate_holdout(model, X, y, metric_list=["r2", "mse", "mae", "rmse", "mape"], problem_type="regression")
        self.assertIn("r2", metrics)
        self.assertIn("mse", metrics)
        self.assertIn("mae", metrics)
        self.assertIn("rmse", metrics)
        self.assertIn("mape", metrics)
        
        for metric in ["mse", "mae", "mape", "rmse"]:
            self.assertIn(metric, LOWER_IS_BETTER_METRICS)

    def test_regression_model_registry(self):
        reg_models = [
            "LinearRegression",
            "DecisionTreeRegressor",
            "RandomForestRegressor",
            "GradientBoostingRegressor",
            "XGBRegressor",
            "Ridge",
            "Lasso",
            "SVR",
            "KNeighborsRegressor",
        ]
        for name in reg_models:
            self.assertIn(name, MODEL_CLASS_MAP)
            model_cls = MODEL_CLASS_MAP[name]
            self.assertIsNotNone(model_cls)


    def test_continuous_stratified_cv_splitters(self):
        from src.modules.preprocessing.regression import (
            create_target_bins,
            ContinuousStratifiedKFold,
            ContinuousRepeatedStratifiedKFold,
        )
        from src.modules.trainings.executor import build_cv_splitter
        
        y = np.linspace(0, 100, 100)
        bins = create_target_bins(y)
        self.assertEqual(len(bins), 100)
        self.assertTrue(len(np.unique(bins)) >= 2)
        
        X = np.random.randn(100, 4)
        cskf = ContinuousStratifiedKFold(n_splits=5, random_state=42)
        splits = list(cskf.split(X, y))
        self.assertEqual(len(splits), 5)
        for train_idx, val_idx in splits:
            self.assertEqual(len(train_idx) + len(val_idx), 100)
            
        crskf = ContinuousRepeatedStratifiedKFold(n_splits=5, n_repeats=3, random_state=42)
        r_splits = list(crskf.split(X, y))
        self.assertEqual(len(r_splits), 15)
        
        # Test build_cv_splitter for regression
        cv1 = build_cv_splitter({"tier": 1, "n_splits": 5, "n_repeats": 5, "name": "ContinuousRepeatedStratifiedKFold"}, problem_type="regression")
        self.assertIsInstance(cv1, ContinuousRepeatedStratifiedKFold)
        
        cv2 = build_cv_splitter({"tier": 2, "n_splits": 5, "name": "ContinuousStratifiedKFold"}, problem_type="regression")
        self.assertIsInstance(cv2, ContinuousStratifiedKFold)


if __name__ == "__main__":
    unittest.main()
