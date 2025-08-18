from typing import Dict, Any

import numpy as np
from sklearn.base import BaseEstimator

from sklearn.model_selection import GridSearchCV
from ..base import SearchStrategy

class GridSearchStrategy(SearchStrategy):
    """Grid Search implementation"""

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        config = super().get_default_config()
        config.update({
            'pre_dispatch': '2*n_jobs',
            'return_train_score': False
        })

        return config

    def search(self, model: BaseEstimator, param_grid: Dict[str, Any], X: np.ndarray, y: np.ndarray, **kwargs):
        self.set_config(**{k: v for k, v in kwargs.items() if k in self.config})

        grid_search = GridSearchCV(
            estimator=model,
            param_grid=param_grid,
            cv = self.config['cv'],
            scoring = self.config['scoring'],
            refit=self.config['metric_sort'],
            n_jobs=self.config['n_jobs'],
            verbose=self.config['verbose'],
            error_score=self.config['error_score'],
            pre_dispatch=self.config['pre_dispatch'],
            return_train_score=self.config['return_train_score']
        )

        grid_search.fit(X, y)
        return grid_search.best_params_, grid_search.best_score_, grid_search.cv_results_