"""Tests for GridSearchStrategy with a small dataset (Iris)."""

import numpy as np
import pytest
from sklearn.datasets import load_iris
from sklearn.metrics import accuracy_score, f1_score, make_scorer
from sklearn.tree import DecisionTreeClassifier
from sklearn.svm import SVC

from optivisionlab_search import GridSearchStrategy


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


@pytest.fixture
def multi_scoring():
    """Multi-metric scoring configuration."""
    return {
        'accuracy': make_scorer(accuracy_score),
        'f1_macro': make_scorer(f1_score, average='macro'),
    }


class TestGridSearchBasic:
    """Basic tests for GridSearchStrategy."""

    def test_search_returns_correct_tuple(self, iris_data, simple_scoring):
        X, y = iris_data
        strategy = GridSearchStrategy(
            scoring=simple_scoring,
            metric_sort='accuracy',
            verbose=0,
        )
        result = strategy.search(
            model=DecisionTreeClassifier(random_state=42),
            param_grid={'max_depth': [2, 5]},
            X=X, y=y,
        )
        assert len(result) == 5
        best_params, best_score, best_all_scores, cv_results, time_limit = result
        assert isinstance(best_params, dict)
        assert isinstance(best_score, float)
        assert isinstance(best_all_scores, dict)
        assert isinstance(cv_results, dict)
        assert isinstance(time_limit, bool)

    def test_best_params_contains_searched_keys(self, iris_data, simple_scoring):
        X, y = iris_data
        strategy = GridSearchStrategy(
            scoring=simple_scoring,
            metric_sort='accuracy',
            verbose=0,
        )
        best_params, _, _, _, _ = strategy.search(
            model=DecisionTreeClassifier(random_state=42),
            param_grid={'max_depth': [2, 3, 5, 10]},
            X=X, y=y,
        )
        assert 'max_depth' in best_params
        assert best_params['max_depth'] in [2, 3, 5, 10]

    def test_best_score_is_positive(self, iris_data, simple_scoring):
        X, y = iris_data
        strategy = GridSearchStrategy(
            scoring=simple_scoring,
            metric_sort='accuracy',
            verbose=0,
        )
        _, best_score, _, _, _ = strategy.search(
            model=DecisionTreeClassifier(random_state=42),
            param_grid={'max_depth': [3, 5]},
            X=X, y=y,
        )
        assert best_score > 0

    def test_cv_results_has_correct_keys(self, iris_data, simple_scoring):
        X, y = iris_data
        strategy = GridSearchStrategy(
            scoring=simple_scoring,
            metric_sort='accuracy',
            verbose=0,
        )
        _, _, _, cv_results, _ = strategy.search(
            model=DecisionTreeClassifier(random_state=42),
            param_grid={'max_depth': [3, 5]},
            X=X, y=y,
        )
        assert 'params' in cv_results
        assert 'mean_test_accuracy' in cv_results
        assert 'rank_test_accuracy' in cv_results
        assert len(cv_results['params']) == 2  # 2 combinations


class TestGridSearchMultiMetric:
    """Tests for multi-metric grid search."""

    def test_multi_metric_scores(self, iris_data, multi_scoring):
        X, y = iris_data
        strategy = GridSearchStrategy(
            scoring=multi_scoring,
            metric_sort='accuracy',
            verbose=0,
        )
        _, _, best_all_scores, cv_results, _ = strategy.search(
            model=DecisionTreeClassifier(random_state=42),
            param_grid={'max_depth': [3, 5]},
            X=X, y=y,
        )
        assert 'accuracy' in best_all_scores
        assert 'f1_macro' in best_all_scores
        assert 'mean_test_accuracy' in cv_results
        assert 'mean_test_f1_macro' in cv_results


class TestGridSearchEmptyParams:
    """Tests for edge case with empty/no params."""

    def test_empty_param_grid(self, iris_data, simple_scoring):
        X, y = iris_data
        strategy = GridSearchStrategy(
            scoring=simple_scoring,
            metric_sort='accuracy',
            verbose=0,
        )
        best_params, best_score, _, _, _ = strategy.search(
            model=DecisionTreeClassifier(random_state=42),
            param_grid={},
            X=X, y=y,
        )
        # Should still return a result with default params
        assert isinstance(best_params, dict)


class TestGridSearchListOfDicts:
    """Tests for list-of-dicts param_grid format."""

    def test_list_of_dicts_param_grid(self, iris_data, simple_scoring):
        X, y = iris_data
        strategy = GridSearchStrategy(
            scoring=simple_scoring,
            metric_sort='accuracy',
            verbose=0,
        )
        param_grid = [
            {'max_depth': [3, 5]},
            {'max_depth': [10], 'min_samples_split': [2, 5]},
        ]
        best_params, best_score, _, cv_results, _ = strategy.search(
            model=DecisionTreeClassifier(random_state=42),
            param_grid=param_grid,
            X=X, y=y,
        )
        assert best_score > 0
        # Total combinations: 2 + 2 = 4
        assert len(cv_results['params']) == 4


class TestGridSearchTimeLimited:
    """Tests for time-limited grid search."""

    def test_time_limit_flag_no_limit(self, iris_data, simple_scoring):
        X, y = iris_data
        strategy = GridSearchStrategy(
            scoring=simple_scoring,
            metric_sort='accuracy',
            verbose=0,
        )
        _, _, _, _, time_limit = strategy.search(
            model=DecisionTreeClassifier(random_state=42),
            param_grid={'max_depth': [3, 5]},
            X=X, y=y,
        )
        assert time_limit is False

    def test_time_limit_very_generous(self, iris_data, simple_scoring):
        X, y = iris_data
        strategy = GridSearchStrategy(
            scoring=simple_scoring,
            metric_sort='accuracy',
            max_time=300,  # 5 minutes - more than enough
            verbose=0,
        )
        _, _, _, _, time_limit = strategy.search(
            model=DecisionTreeClassifier(random_state=42),
            param_grid={'max_depth': [3, 5]},
            X=X, y=y,
        )
        assert time_limit is False


class TestGridSearchNumpyTypeSafety:
    """Tests to ensure results contain no numpy types (serialization safety)."""

    def test_results_are_native_python_types(self, iris_data, simple_scoring):
        X, y = iris_data
        strategy = GridSearchStrategy(
            scoring=simple_scoring,
            metric_sort='accuracy',
            verbose=0,
        )
        best_params, best_score, best_all_scores, _, _ = strategy.search(
            model=DecisionTreeClassifier(random_state=42),
            param_grid={'max_depth': [3, 5]},
            X=X, y=y,
        )
        # Check no numpy types
        assert isinstance(best_score, (int, float))
        for k, v in best_params.items():
            assert not isinstance(v, (np.integer, np.floating)), f"numpy type found in best_params: {k}={v}"
        for k, v in best_all_scores.items():
            assert not isinstance(v, (np.integer, np.floating)), f"numpy type found in best_all_scores: {k}={v}"
