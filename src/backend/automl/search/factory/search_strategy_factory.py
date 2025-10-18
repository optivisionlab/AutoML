"""
Search Strategy Factory Pattern Implementation
This module provides a factory for creating different search strategy instances.
"""

from typing import Dict, Any, Optional
from automl.search.base import SearchStrategy
from automl.search.strategy.grid_search import GridSearchStrategy
from automl.search.strategy.genetic_algorithm import GeneticAlgorithm
from automl.search.strategy.bayesian_search import BayesianSearchStrategy


class SearchStrategyFactory:
    """Factory class for creating search strategy instances."""
    
    # Registry of available search strategy
    _strategies = {
        'grid': GridSearchStrategy,
        'gridsearch': GridSearchStrategy,
        'grid_search': GridSearchStrategy,
        'genetic': GeneticAlgorithm,
        'ga': GeneticAlgorithm,
        'GA': GeneticAlgorithm,
        'genetic_algorithm': GeneticAlgorithm,
        'bayesian': BayesianSearchStrategy,
        'bayes': BayesianSearchStrategy,
        'bayesian_search': BayesianSearchStrategy,
        'skopt': BayesianSearchStrategy,
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
        
        # Get the strategy class
        strategy_class = cls._strategies.get(strategy_name)
        
        if strategy_class is None:
            available_strategies = list(set(cls._strategies.values()))
            available_names = [name for name, cls_type in cls._strategies.items() 
                             if cls_type in available_strategies[:3]]  # Get main names
            raise ValueError(
                f"Unknown search strategy: '{strategy_name}'. "
                f"Available strategy: {', '.join(['grid', 'genetic', 'bayesian'])}"
            )
        
        # Create and return the strategy instance
        if config:
            return strategy_class(**config)
        else:
            return strategy_class()
    
    @classmethod
    def register_strategy(cls, name: str, strategy_class: type):
        """
        Register a new search strategy with the factory.
        
        Args:
            name: Name to register the strategy under
            strategy_class: The strategy class to register
        """
        if not issubclass(strategy_class, SearchStrategy):
            raise TypeError(f"Strategy class must inherit from SearchStrategy")
        
        cls._strategies[name.lower()] = strategy_class
    
    @classmethod
    def get_available_strategies(cls) -> Dict[str, type]:
        """
        Get a dictionary of all available strategy.
        
        Returns:
            Dict mapping strategy names to their classes
        """
        return cls._strategies.copy()
    
    @classmethod
    def is_strategy_available(cls, strategy_name: str) -> bool:
        """
        Check if a strategy is available in the factory.
        
        Args:
            strategy_name: Name of the strategy to check
            
        Returns:
            bool: True if the strategy is available, False otherwise
        """
        return strategy_name.lower().strip() in cls._strategies
