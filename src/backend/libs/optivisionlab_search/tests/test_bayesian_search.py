"""Tests for BayesianSearchStrategy with a small dataset (Iris)."""

import numpy as np
import pytest
from sklearn.datasets import load_iris
from sklearn.metrics import accuracy_score, f1_score, make_scorer
from sklearn.tree import DecisionTreeClassifier

from optivisionlab_search import BayesianSearchStrategy


@pytest.fixture
def iris_data():
    """Load Iris dataset for testing."""
    X, y = load_iris(return_X_y=True)
    return X, y


@pytest.fixture
def simple_scoring():
    """Simple scoring configuration."""
    return {
        'accuracy': make_scorer(accuracy_score),
    }


class TestBayesianSearchBasic:
    """Basic tests for BayesianSearchStrategy."""

    def test_search_returns_correct_tuple(self, iris_data, simple_scoring):
        X, y = iris_data
        strategy = BayesianSearchStrategy(
            scoring=simple_scoring,
            metric_sort='accuracy',
            n_calls=5,
            n_initial_points=2,
            random_state=42,
            verbose=0,
        )
        result = strategy.search(
            model=DecisionTreeClassifier(random_state=42),
            param_grid={'max_depth': [2, 3, 5, 10]},
            X=X, y=y,
        )
        assert len(result) == 5
        best_params, best_score, best_all_scores, cv_results, time_limit = result
        assert isinstance(best_params, dict)
        assert isinstance(best_score, float)
        assert isinstance(best_all_scores, dict)
        assert isinstance(cv_results, dict)
        assert isinstance(time_limit, bool)

    def test_best_score_is_positive(self, iris_data, simple_scoring):
        X, y = iris_data
        strategy = BayesianSearchStrategy(
            scoring=simple_scoring,
            metric_sort='accuracy',
            n_calls=5,
            n_initial_points=2,
            random_state=42,
            verbose=0,
        )
        _, best_score, _, _, _ = strategy.search(
            model=DecisionTreeClassifier(random_state=42),
            param_grid={'max_depth': [2, 3, 5, 10]},
            X=X, y=y,
        )
        assert best_score > 0

    def test_best_params_are_from_grid(self, iris_data, simple_scoring):
        X, y = iris_data
        strategy = BayesianSearchStrategy(
            scoring=simple_scoring,
            metric_sort='accuracy',
            n_calls=5,
            n_initial_points=2,
            random_state=42,
            verbose=0,
        )
        best_params, _, _, _, _ = strategy.search(
            model=DecisionTreeClassifier(random_state=42),
            param_grid={'max_depth': [2, 3, 5, 10]},
            X=X, y=y,
        )
        assert 'max_depth' in best_params
        assert best_params['max_depth'] in [2, 3, 5, 10]


class TestBayesianSearchEmptyParams:
    """Tests for edge case with empty/no params."""

    def test_empty_param_grid_uses_defaults(self, iris_data, simple_scoring):
        X, y = iris_data
        strategy = BayesianSearchStrategy(
            scoring=simple_scoring,
            metric_sort='accuracy',
            n_calls=5,
            random_state=42,
            verbose=0,
        )
        best_params, best_score, _, _, _ = strategy.search(
            model=DecisionTreeClassifier(random_state=42),
            param_grid={},
            X=X, y=y,
        )
        assert isinstance(best_params, dict)
        assert best_score > 0


class TestBayesianSearchMultiGrid:
    """Tests for list-of-dicts param_grid."""

    def test_multi_grid_search(self, iris_data, simple_scoring):
        X, y = iris_data
        strategy = BayesianSearchStrategy(
            scoring=simple_scoring,
            metric_sort='accuracy',
            n_calls=5,
            n_initial_points=2,
            random_state=42,
            verbose=0,
        )
        param_grid = [
            {'max_depth': [3, 5]},
            {'max_depth': [10], 'min_samples_split': [2, 5]},
        ]
        best_params, best_score, _, _, _ = strategy.search(
            model=DecisionTreeClassifier(random_state=42),
            param_grid=param_grid,
            X=X, y=y,
        )
        assert best_score > 0


class TestBayesianSearchNumpyTypeSafety:
    """Tests to ensure results contain no numpy types."""

    def test_results_are_native_python_types(self, iris_data, simple_scoring):
        X, y = iris_data
        strategy = BayesianSearchStrategy(
            scoring=simple_scoring,
            metric_sort='accuracy',
            n_calls=5,
            n_initial_points=2,
            random_state=42,
            verbose=0,
        )
        best_params, best_score, best_all_scores, _, _ = strategy.search(
            model=DecisionTreeClassifier(random_state=42),
            param_grid={'max_depth': [2, 5, 10]},
            X=X, y=y,
        )
        assert isinstance(best_score, (int, float))
        for k, v in best_params.items():
            assert not isinstance(v, (np.integer, np.floating)), f"numpy type in best_params: {k}={v}"
