from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional, Union
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
            tuple: (best_params, best_score, cv_results)
        """
        pass

    def set_config(self, **kwargs):
        """Update configuration"""
        self.config.update(kwargs)
        return self
    
    @staticmethod
    def convert_numpy_types(obj: Any) -> Any:
        """Convert numpy types to native Python types recursively.
        
        This is important for JSON serialization and avoiding 
        unhashable type errors.
        
        Args:
            obj: Object to convert (can be dict, list, scalar, etc.)
            
        Returns:
            Object with all numpy types converted to native Python types
        """
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif hasattr(obj, 'item'):  # numpy scalar
            return obj.item()
        elif isinstance(obj, dict):
            return {key: SearchStrategy.convert_numpy_types(value) 
                   for key, value in obj.items()}
        elif isinstance(obj, list):
            return [SearchStrategy.convert_numpy_types(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(SearchStrategy.convert_numpy_types(item) for item in obj)
        else:
            return obj