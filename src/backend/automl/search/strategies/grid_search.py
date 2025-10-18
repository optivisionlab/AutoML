from typing import Dict, Any

import numpy as np
from sklearn.base import BaseEstimator

from sklearn.model_selection import GridSearchCV
from ..base import SearchStrategy
from ...search.search_algorithms import grid_search as CustomGridSearch

class GridSearchStrategy(SearchStrategy):
    """Grid Search implementation"""

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """Return a default configuration for this strategy"""
        config = SearchStrategy.get_default_config()
        config.update({
            'pre_dispatch': '2*n_jobs',
            'return_train_score': False
        })

        return config

    def search(self, model: BaseEstimator, param_grid: Dict[str, Any], X: np.ndarray, y: np.ndarray, **kwargs):
        """
        Perform grid search hyperparameter optimization.

        Args:
            model: The estimator to optimize
            param_grid: Dictionary with parameters names as keys and lists of parameter settings to try
            X: Training feature data
            y: Training target data
            **kwargs: Additional configuration parameters

        Returns:
            tuple: (best_params, best_score, cv_results)
        """
        self.set_config(**{k: v for k, v in kwargs.items() if k in self.config})

        best_params, best_score, best_all_scores, cv_results = CustomGridSearch(
            param_grid=param_grid,
            model_func=model,
            data=X,
            targets=y,
            cv=self.config['cv'],
            scoring=self.config['scoring'],
            metric_sort=self.config['metric_sort'],
            return_train_score=self.config['return_train_score']
        )

        return best_params, best_score, cv_results