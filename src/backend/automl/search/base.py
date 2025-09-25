from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional
from sklearn.base import  BaseEstimator
import numpy as np
from sklearn.model_selection import StratifiedKFold


class SearchStrategy(ABC):
    """Base class for all search strategies."""

    def __init__(self, **kwargs):
        self.config = self.get_default_config()
        self.config.update(kwargs)

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """Return a default configuration for this strategy"""
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

        return {
            'cv': cv,
            'scoring': None,
            'metric_sort': 'accuracy',
            'n_jobs': -1,
            'verbose': 0,
            'random_state': None,
            'error_score': 'raise'
        }

    @abstractmethod
    def search(self, model: BaseEstimator, param_grid: Dict[str, Any], X: np.ndarray, y: np.ndarray, **kwargs):
        """Execute the search algorithm.

        Returns:
            tuple: (best_params, best_score, cv_results)))
        """
        pass

    def set_config(self, **kwargs):
        """Update configuration"""
        self.config.update(kwargs)
        return self