"""Tests for GeneticAlgorithm with a small dataset (Iris)."""

import numpy as np
import pytest
from sklearn.datasets import load_iris
from sklearn.metrics import accuracy_score, f1_score, make_scorer
from sklearn.tree import DecisionTreeClassifier

from optivisionlab_search import GeneticAlgorithm


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
def ga_strategy(simple_scoring):
    """Create a fast GA strategy for testing."""
    return GeneticAlgorithm(
        scoring=simple_scoring,
        metric_sort='accuracy',
        population_size=6,
        generation=3,
        elite_size=1,
        tournament_size=2,
        mutation_rate=0.2,
        crossover_rate=0.8,
        random_state=42,
        verbose=0,
        early_stopping_enabled=False,
    )


class TestGeneticAlgorithmBasic:
    """Basic tests for GeneticAlgorithm."""

    def test_search_returns_correct_tuple(self, iris_data, ga_strategy):
        X, y = iris_data
        result = ga_strategy.search(
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

    def test_best_score_is_positive(self, iris_data, ga_strategy):
        X, y = iris_data
        _, best_score, _, _, _ = ga_strategy.search(
            model=DecisionTreeClassifier(random_state=42),
            param_grid={'max_depth': [2, 3, 5, 10]},
            X=X, y=y,
        )
        assert best_score > 0

    def test_best_params_are_valid(self, iris_data, ga_strategy):
        X, y = iris_data
        best_params, _, _, _, _ = ga_strategy.search(
            model=DecisionTreeClassifier(random_state=42),
            param_grid={'max_depth': [2, 3, 5, 10]},
            X=X, y=y,
        )
        assert 'max_depth' in best_params
        assert best_params['max_depth'] in [2, 3, 5, 10]


class TestGeneticAlgorithmListOfDicts:
    """Tests for list-of-dicts param_grid format."""

    def test_multi_grid_search(self, iris_data, ga_strategy):
        X, y = iris_data
        param_grid = [
            {'max_depth': [3, 5]},
            {'max_depth': [10], 'min_samples_split': [2, 5]},
        ]
        best_params, best_score, _, _, _ = ga_strategy.search(
            model=DecisionTreeClassifier(random_state=42),
            param_grid=param_grid,
            X=X, y=y,
        )
        assert best_score > 0


class TestGeneticAlgorithmCvResults:
    """Tests for cv_results structure."""

    def test_cv_results_has_required_keys(self, iris_data, ga_strategy):
        X, y = iris_data
        _, _, _, cv_results, _ = ga_strategy.search(
            model=DecisionTreeClassifier(random_state=42),
            param_grid={'max_depth': [2, 3, 5, 10]},
            X=X, y=y,
        )
        assert 'params' in cv_results
        assert 'mean_test_score' in cv_results
        assert 'rank_test_score' in cv_results
        assert 'convergence_history' in cv_results
        assert 'best_generation' in cv_results
        assert 'total_evaluations' in cv_results

    def test_cv_results_has_metric_scores(self, iris_data, ga_strategy):
        X, y = iris_data
        _, _, _, cv_results, _ = ga_strategy.search(
            model=DecisionTreeClassifier(random_state=42),
            param_grid={'max_depth': [2, 3, 5, 10]},
            X=X, y=y,
        )
        assert 'mean_test_accuracy' in cv_results


class TestGeneticAlgorithmNumpyTypeSafety:
    """Tests to ensure results contain no numpy types."""

    def test_results_are_native_python_types(self, iris_data, ga_strategy):
        X, y = iris_data
        best_params, best_score, best_all_scores, _, _ = ga_strategy.search(
            model=DecisionTreeClassifier(random_state=42),
            param_grid={'max_depth': [2, 3, 5, 10]},
            X=X, y=y,
        )
        assert isinstance(best_score, (int, float))
        for k, v in best_params.items():
            assert not isinstance(v, (np.integer, np.floating)), f"numpy type in best_params: {k}={v}"


class TestGeneticAlgorithmEncoding:
    """Tests for parameter encoding/decoding."""

    def test_encode_categorical_params(self, simple_scoring):
        ga = GeneticAlgorithm(
            scoring=simple_scoring,
            metric_sort='accuracy',
            population_size=4,
            generation=1,
            random_state=42,
            verbose=0,
        )
        ga._encode_parameters({'max_depth': [2, 5, 10], 'criterion': ['gini', 'entropy']})
        assert 'max_depth' in ga.param_bounds
        assert 'criterion' in ga.param_bounds
        assert ga.param_types['max_depth'][0] == 'categorical'
        assert ga.param_types['criterion'][0] == 'categorical'

    def test_decode_individual(self, simple_scoring):
        ga = GeneticAlgorithm(
            scoring=simple_scoring,
            metric_sort='accuracy',
            population_size=4,
            generation=1,
            random_state=42,
            verbose=0,
        )
        ga._encode_parameters({'max_depth': [2, 5, 10]})
        individual = {'max_depth': 1.0, '_grid_idx': 0.0}
        decoded = ga._decode_individual(individual)
        assert decoded['max_depth'] == 5  # Index 1 -> value 5

    def test_create_individual(self, simple_scoring):
        ga = GeneticAlgorithm(
            scoring=simple_scoring,
            metric_sort='accuracy',
            population_size=4,
            generation=1,
            random_state=42,
            verbose=0,
        )
        ga._encode_parameters({'max_depth': [2, 5, 10]})
        individual = ga._create_individual()
        assert isinstance(individual, dict)
        assert 'max_depth' in individual
        assert '_grid_idx' in individual
