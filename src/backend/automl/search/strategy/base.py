from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional, Union
from sklearn.base import  BaseEstimator
import numpy as np
import os
from datetime import datetime
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
            'error_score': 'raise',
            'log_dir': 'logs',
            'save_log': False
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
    
    def create_log_file_path(self, model: BaseEstimator, strategy_name: str = None) -> Optional[str]:
        """Create a log file path for saving search results.
        
        This method creates a standardized log file path based on the configuration.
        It ensures the log directory exists and generates a timestamped filename.
        
        Args:
            model: The model being used for search
            strategy_name: Optional name for the strategy (defaults to class name)
            
        Returns:
            str: Path to the log file if save_log is True, None otherwise
        """
        if not self.config.get('save_log', False):
            return None
            
        log_dir = self.config.get('log_dir', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_name = model.__class__.__name__
        
        # Use the provided strategy name or derive from the class name
        if strategy_name is None:
            # Convert the class name from CamelCase to snake_case
            class_name = self.__class__.__name__
            # Remove the 'Strategy' suffix if present
            if class_name.endswith('Strategy'):
                class_name = class_name[:-8]
            if class_name.endswith('SearchStrategy'):
                class_name = class_name[:-14]
            # Convert to snake_case
            import re
            strategy_name = re.sub(r'(?<!^)(?=[A-Z])', '_', class_name).lower()
        
        log_file = os.path.join(log_dir, f'{strategy_name}_{model_name}_{timestamp}.csv')
        return log_file
    
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
    
    def _finalize_results(self, best_params: Dict[str, Any], best_score: float, 
                         best_all_scores: Dict[str, float], cv_results: Dict[str, Any]) -> Tuple:
        """Clear caches and convert numpy types before returning results.
        
        This method should be called at the end of the search method to:
        1. Clear all caches to free memory
        2. Convert numpy types to native Python types for serialization
        
        Args:
            best_params: Best parameters found
            best_score: Best score achieved
            best_all_scores: All metric scores for best parameters
            cv_results: Detailed cross-validation results
            
        Returns:
            tuple: (best_params, best_score, best_all_scores, cv_results) with all numpy types converted
        """
        # Clear caches after the search completes
        if hasattr(self, '_decode_cache'):
            self._decode_cache.clear()
        if hasattr(self, '_evaluation_cache'):
            self._evaluation_cache.clear()
        if hasattr(self, '_model_copies'):
            self._model_copies.clear()
        
        # Convert all numpy types to native Python types
        best_params = self.convert_numpy_types(best_params)
        best_score = self.convert_numpy_types(best_score)
        best_all_scores = self.convert_numpy_types(best_all_scores)
        cv_results = self.convert_numpy_types(cv_results)
        
        return best_params, best_score, best_all_scores, cv_results