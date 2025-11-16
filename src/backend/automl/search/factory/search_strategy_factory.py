"""
Search Strategy Factory Pattern Implementation
This module provides a factory for creating different search strategy instances.
"""

from typing import Dict, Any, Optional
from automl.search.strategy.base import SearchStrategy
from automl.search.strategy.grid_search import GridSearchStrategy
from automl.search.strategy.genetic_algorithm import GeneticAlgorithm
from automl.search.strategy.bayesian_search import BayesianSearchStrategy


class SearchStrategyFactory:
    """Factory class for creating search strategy instances."""
    
    # Registry of available search strategy
    _strategies = {
        'grid_search': GridSearchStrategy,
        'genetic_algorithm': GeneticAlgorithm,
        'bayesian_search': BayesianSearchStrategy
    }
    
    @classmethod
    def create_strategy(cls, strategy_name: str, config: Optional[Dict[str, Any]] = None) -> SearchStrategy:
        """
        Create a search strategy instance based on the strategy name.
        
        Args:
            strategy_name: Name of the search strategy (e.g., 'grid', 'genetic', 'bayesian')
            config: Optional configuration dictionary for the strategy
            
        Returns:
            SearchStrategy: An instance of the requested search strategy
            
        Raises:
            ValueError: If the strategy name is not recognized
        """
        # Normalize strategy name to lowercase
        strategy_name = strategy_name.lower().strip()
        
        # Determine strategy class using startswith pattern matching
        strategy_class = None
        
        if strategy_name.startswith('grid'):
            strategy_class = GridSearchStrategy
        elif strategy_name.startswith('genetic') or strategy_name.startswith('ga'):
            strategy_class = GeneticAlgorithm
        elif strategy_name.startswith('bayesian') or strategy_name.startswith('bayes') or strategy_name.startswith('skopt'):
            strategy_class = BayesianSearchStrategy
        else:
            raise ValueError(
                f"Unknown search strategy: '{strategy_name}'. "
                f"Available strategies: grid*, genetic*/ga*, bayesian*/bayes*/skopt*"
            )
        
        # Create and return the strategy instance
        if config:
            return strategy_class(**config)
        else:
            return strategy_class()
    
    @classmethod
    def get_available_strategies(cls) -> list:
        """
        Get a list of all available strategy patterns.
        
        Returns:
            List of strategy name patterns
        """
        return ['grid*', 'genetic*/ga*', 'bayesian*/bayes*/skopt*']
    
    @classmethod
    def is_strategy_available(cls, strategy_name: str) -> bool:
        """
        Check if a strategy is available in the factory.
        
        Args:
            strategy_name: Name of the strategy to check
            
        Returns:
            bool: True if the strategy is available, False otherwise
        """
        strategy_name = strategy_name.lower().strip()
        return (
            strategy_name.startswith('grid') or
            strategy_name.startswith('genetic') or
            strategy_name.startswith('ga') or
            strategy_name.startswith('bayesian') or
            strategy_name.startswith('bayes') or
            strategy_name.startswith('skopt')
        )
