"""
optivisionlab-search: Hyperparameter optimization strategies for AutoML.

Provides Grid Search, Bayesian Optimization, and Genetic Algorithm
strategies for hyperparameter tuning of scikit-learn models.
"""

from optivisionlab_search.strategy.base import SearchStrategy, normalize_param_grid
from optivisionlab_search.strategy.grid_search import GridSearchStrategy
from optivisionlab_search.strategy.bayesian_search import BayesianSearchStrategy
from optivisionlab_search.strategy.genetic_algorithm import GeneticAlgorithm
from optivisionlab_search.factory import SearchStrategyFactory

__all__ = [
    'SearchStrategy',
    'normalize_param_grid',
    'GridSearchStrategy',
    'BayesianSearchStrategy',
    'GeneticAlgorithm',
    'SearchStrategyFactory',
]

__version__ = '0.1.0'
