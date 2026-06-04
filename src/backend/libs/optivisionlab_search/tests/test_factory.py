"""Tests for SearchStrategyFactory."""

import pytest

from optivisionlab_search import (
    SearchStrategyFactory,
    SearchStrategy,
    GridSearchStrategy,
    BayesianSearchStrategy,
    GeneticAlgorithm,
)


class TestFactoryCreateStrategy:
    """Tests for SearchStrategyFactory.create_strategy."""

    def test_grid_search_by_name(self):
        strategy = SearchStrategyFactory.create_strategy('grid_search')
        assert isinstance(strategy, GridSearchStrategy)

    def test_grid_search_prefix(self):
        strategy = SearchStrategyFactory.create_strategy('grid')
        assert isinstance(strategy, GridSearchStrategy)

    def test_bayesian_search_by_name(self):
        strategy = SearchStrategyFactory.create_strategy('bayesian_search')
        assert isinstance(strategy, BayesianSearchStrategy)

    def test_bayesian_prefix(self):
        strategy = SearchStrategyFactory.create_strategy('bayes')
        assert isinstance(strategy, BayesianSearchStrategy)

    def test_bayesian_skopt_prefix(self):
        strategy = SearchStrategyFactory.create_strategy('skopt')
        assert isinstance(strategy, BayesianSearchStrategy)

    def test_genetic_algorithm_by_name(self):
        strategy = SearchStrategyFactory.create_strategy('genetic_algorithm')
        assert isinstance(strategy, GeneticAlgorithm)

    def test_genetic_prefix(self):
        strategy = SearchStrategyFactory.create_strategy('genetic')
        assert isinstance(strategy, GeneticAlgorithm)

    def test_ga_prefix(self):
        strategy = SearchStrategyFactory.create_strategy('ga')
        assert isinstance(strategy, GeneticAlgorithm)

    def test_case_insensitive(self):
        strategy = SearchStrategyFactory.create_strategy('Grid_Search')
        assert isinstance(strategy, GridSearchStrategy)

    def test_with_config(self):
        config = {'cv': 3, 'n_jobs': 2}
        strategy = SearchStrategyFactory.create_strategy('grid_search', config)
        assert isinstance(strategy, GridSearchStrategy)
        assert strategy.config['n_jobs'] == 2

    def test_unknown_strategy_raises(self):
        with pytest.raises(ValueError, match="Search strategy không xác định"):
            SearchStrategyFactory.create_strategy('unknown_strategy')

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            SearchStrategyFactory.create_strategy('')


class TestFactoryIsAvailable:
    """Tests for SearchStrategyFactory.is_strategy_available."""

    def test_grid_available(self):
        assert SearchStrategyFactory.is_strategy_available('grid_search') is True

    def test_bayesian_available(self):
        assert SearchStrategyFactory.is_strategy_available('bayesian') is True

    def test_genetic_available(self):
        assert SearchStrategyFactory.is_strategy_available('genetic') is True

    def test_ga_available(self):
        assert SearchStrategyFactory.is_strategy_available('ga') is True

    def test_unknown_not_available(self):
        assert SearchStrategyFactory.is_strategy_available('random_search') is False


class TestFactoryGetAvailable:
    """Tests for SearchStrategyFactory.get_available_strategies."""

    def test_returns_list(self):
        strategies = SearchStrategyFactory.get_available_strategies()
        assert isinstance(strategies, list)
        assert len(strategies) > 0


class TestStrategyIsSubclass:
    """Verify all strategies inherit from SearchStrategy."""

    def test_grid_is_search_strategy(self):
        assert issubclass(GridSearchStrategy, SearchStrategy)

    def test_bayesian_is_search_strategy(self):
        assert issubclass(BayesianSearchStrategy, SearchStrategy)

    def test_genetic_is_search_strategy(self):
        assert issubclass(GeneticAlgorithm, SearchStrategy)
