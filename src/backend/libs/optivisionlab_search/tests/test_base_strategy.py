"""Tests for SearchStrategy base class and utility functions."""

import numpy as np
import pytest
from sklearn.tree import DecisionTreeClassifier

from optivisionlab_search.strategy.base import SearchStrategy, normalize_param_grid


class TestNormalizeParamGrid:
    """Tests for the normalize_param_grid utility function."""

    def test_none_returns_empty_dict_list(self):
        result = normalize_param_grid(None)
        assert result == [{}]

    def test_empty_dict_returns_list_with_empty_dict(self):
        result = normalize_param_grid({})
        assert result == [{}]

    def test_single_dict_wraps_in_list(self):
        grid = {'C': [1, 10], 'kernel': ['rbf']}
        result = normalize_param_grid(grid)
        assert result == [grid]

    def test_list_of_dicts_passes_through(self):
        grids = [{'C': [1, 10]}, {'C': [0.1], 'kernel': ['linear']}]
        result = normalize_param_grid(grids)
        assert result == grids

    def test_empty_list_returns_empty_dict_list(self):
        result = normalize_param_grid([])
        assert result == [{}]

    def test_invalid_list_raises_value_error(self):
        with pytest.raises(ValueError, match="param_grid list chứa phần tử không phải dict"):
            normalize_param_grid([1, 2, 3])

    def test_invalid_type_raises_value_error(self):
        with pytest.raises(ValueError, match="param_grid phải là dict hoặc list of dicts"):
            normalize_param_grid("invalid")


class TestConvertNumpyTypes:
    """Tests for SearchStrategy.convert_numpy_types static method."""

    def test_numpy_int(self):
        result = SearchStrategy.convert_numpy_types(np.int64(42))
        assert isinstance(result, int)
        assert result == 42

    def test_numpy_float(self):
        result = SearchStrategy.convert_numpy_types(np.float64(3.14))
        assert isinstance(result, float)
        assert abs(result - 3.14) < 1e-10

    def test_numpy_array(self):
        result = SearchStrategy.convert_numpy_types(np.array([1, 2, 3]))
        assert isinstance(result, list)
        assert result == [1, 2, 3]

    def test_dict_with_numpy_values(self):
        data = {'a': np.int64(1), 'b': np.float64(2.5), 'c': 'text'}
        result = SearchStrategy.convert_numpy_types(data)
        assert isinstance(result['a'], int)
        assert isinstance(result['b'], float)
        assert result['c'] == 'text'

    def test_nested_list(self):
        data = [np.int64(1), [np.float64(2.5), np.int32(3)]]
        result = SearchStrategy.convert_numpy_types(data)
        assert result == [1, [2.5, 3]]
        assert isinstance(result[0], int)
        assert isinstance(result[1][0], float)

    def test_tuple_conversion(self):
        data = (np.int64(1), np.float64(2.0))
        result = SearchStrategy.convert_numpy_types(data)
        assert isinstance(result, tuple)
        assert result == (1, 2.0)

    def test_plain_python_types_unchanged(self):
        data = {'a': 1, 'b': 2.5, 'c': 'text', 'd': None}
        result = SearchStrategy.convert_numpy_types(data)
        assert result == data


class TestSearchStrategyDefaultConfig:
    """Tests for SearchStrategy.get_default_config."""

    def test_returns_dict(self):
        config = SearchStrategy.get_default_config()
        assert isinstance(config, dict)

    def test_has_required_keys(self):
        config = SearchStrategy.get_default_config()
        required_keys = ['cv', 'scoring', 'metric_sort', 'n_jobs', 'verbose',
                         'error_score', 'log_dir', 'save_log', 'max_time']
        for key in required_keys:
            assert key in config, f"Missing key: {key}"

    def test_default_metric_sort(self):
        config = SearchStrategy.get_default_config()
        assert config['metric_sort'] == 'accuracy'

    def test_default_max_time_is_none(self):
        config = SearchStrategy.get_default_config()
        assert config['max_time'] is None


class TestTimerUtilities:
    """Tests for timer utilities in SearchStrategy base class."""

    def test_start_timer_initializes_state(self):
        """Cannot instantiate ABC directly, use a concrete subclass indirectly."""
        from optivisionlab_search import GridSearchStrategy
        strategy = GridSearchStrategy()
        strategy._start_timer()
        assert strategy._search_start_time is not None
        assert strategy._time_limit_reached is False

    def test_check_time_status_no_limit(self):
        from optivisionlab_search import GridSearchStrategy
        strategy = GridSearchStrategy()
        strategy._start_timer()
        remaining, exceeded = strategy._check_time_status()
        assert remaining is None
        assert exceeded is False

    def test_check_time_status_with_limit(self):
        from optivisionlab_search import GridSearchStrategy
        strategy = GridSearchStrategy(max_time=100)
        strategy._start_timer()
        remaining, exceeded = strategy._check_time_status()
        assert remaining is not None
        assert remaining > 0
        assert exceeded is False

    def test_should_start_next_iteration_no_limit(self):
        from optivisionlab_search import GridSearchStrategy
        strategy = GridSearchStrategy()
        strategy._start_timer()
        assert strategy._should_start_next_iteration() is True

    def test_should_apply_early_stopping_with_time_limit(self):
        from optivisionlab_search import GridSearchStrategy
        strategy = GridSearchStrategy(max_time=100)
        # When time limit is set, early stopping should NOT apply
        assert strategy._should_apply_early_stopping() is False

    def test_should_apply_early_stopping_without_time_limit(self):
        from optivisionlab_search import GridSearchStrategy
        strategy = GridSearchStrategy()
        # When no time limit, early stopping SHOULD apply
        assert strategy._should_apply_early_stopping() is True
