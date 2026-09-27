# Standard Libraries
import unittest
import numpy as np
from sklearn.datasets import load_iris, load_diabetes
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.model_selection import KFold, StratifiedKFold

# Local Libraries
from src.modules.models.service import ModelService
from src.modules.hpo import (
    GridSearch,
    RandomSearch,
    BayesianSearch,
    GeneticAlgorithmSearch,
)


class TestHPOAlgorithms(unittest.TestCase):
    def setUp(self):
        # Classification dataset
        iris = load_iris()
        self.X_cls = iris.data
        self.y_cls = iris.target
        self.cls_scoring = ModelService.build_scoring_dict(["accuracy", "f1"], problem_type="classification")
        self.cls_cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
        self.cls_param_grid = {
            "max_depth": [2, 3, 5],
            "min_samples_split": [2, 5],
        }

        # Regression dataset
        diabetes = load_diabetes()
        self.X_reg = diabetes.data
        self.y_reg = diabetes.target
        self.reg_scoring = ModelService.build_scoring_dict(["r2", "mse"], problem_type="regression")
        self.reg_cv = KFold(n_splits=3, shuffle=True, random_state=42)
        self.reg_param_grid = {
            "max_depth": [3, 5, 8],
            "min_samples_split": [2, 4],
        }

    def test_grid_search_classification(self):
        searcher = GridSearch(
            estimator=DecisionTreeClassifier(random_state=42),
            param_grid=self.cls_param_grid,
            cv=self.cls_cv,
            scoring=self.cls_scoring,
            refit="accuracy",
            n_jobs=1,
            verbose=0,
        )
        searcher.fit(self.X_cls, self.y_cls)

        self.assertIsNotNone(searcher.best_estimator_)
        self.assertIn("max_depth", searcher.best_params_)
        self.assertGreater(searcher.best_score_, 0.8)
        self.assertEqual(len(searcher.cv_results_["params"]), 6)
        self.assertIn("mean_test_accuracy", searcher.cv_results_)
        self.assertIn("mean_test_f1", searcher.cv_results_)
        self.assertIn("rank_test_accuracy", searcher.cv_results_)
        self.assertEqual(len(searcher.trials_history_), 6)

        # Test predict
        preds = searcher.predict(self.X_cls)
        self.assertEqual(len(preds), len(self.y_cls))

    def test_random_search_regression(self):
        searcher = RandomSearch(
            estimator=DecisionTreeRegressor(random_state=42),
            param_grid=self.reg_param_grid,
            n_iter=4,
            cv=self.reg_cv,
            scoring=self.reg_scoring,
            refit="r2",
            random_state=42,
            n_jobs=1,
            verbose=0,
        )
        searcher.fit(self.X_reg, self.y_reg)

        self.assertIsNotNone(searcher.best_estimator_)
        self.assertIn("max_depth", searcher.best_params_)
        self.assertEqual(len(searcher.cv_results_["params"]), 4)
        self.assertIn("mean_test_r2", searcher.cv_results_)
        self.assertIn("mean_test_mse", searcher.cv_results_)
        self.assertEqual(len(searcher.trials_history_), 4)

    def test_bayesian_search_classification(self):
        searcher = BayesianSearch(
            estimator=DecisionTreeClassifier(random_state=42),
            param_grid=self.cls_param_grid,
            n_calls=6,
            n_initial_points=2,
            cv=self.cls_cv,
            scoring=self.cls_scoring,
            refit="accuracy",
            random_state=42,
            n_jobs=1,
            verbose=0,
        )
        searcher.fit(self.X_cls, self.y_cls)

        self.assertIsNotNone(searcher.best_estimator_)
        self.assertIn("max_depth", searcher.best_params_)
        self.assertGreater(searcher.best_score_, 0.8)
        self.assertGreaterEqual(len(searcher.trials_history_), 1)

    def test_genetic_algorithm_classification(self):
        searcher = GeneticAlgorithmSearch(
            estimator=DecisionTreeClassifier(random_state=42),
            param_grid=self.cls_param_grid,
            population_size=4,
            n_generations=2,
            cv=self.cls_cv,
            scoring=self.cls_scoring,
            refit="accuracy",
            random_state=42,
            n_jobs=1,
            verbose=0,
        )
        searcher.fit(self.X_cls, self.y_cls)

        self.assertIsNotNone(searcher.best_estimator_)
        self.assertIn("max_depth", searcher.best_params_)
        self.assertGreater(searcher.best_score_, 0.8)
        self.assertGreaterEqual(len(searcher.trials_history_), 1)

    def test_empty_param_grid(self):
        searcher = GridSearch(
            estimator=DecisionTreeClassifier(random_state=42),
            param_grid={},
            cv=self.cls_cv,
            scoring=self.cls_scoring,
            refit="accuracy",
            n_jobs=1,
            verbose=0,
        )
        searcher.fit(self.X_cls, self.y_cls)

        self.assertIsNotNone(searcher.best_estimator_)
        self.assertEqual(searcher.best_params_, {})
        self.assertEqual(len(searcher.trials_history_), 1)


if __name__ == "__main__":
    unittest.main()
