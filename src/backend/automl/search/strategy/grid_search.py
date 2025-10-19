from typing import Dict, Any, List, Tuple
import itertools
import time
import copy
import hashlib

import numpy as np
from sklearn.base import BaseEstimator
from sklearn.model_selection import StratifiedKFold, cross_validate
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from joblib import Parallel, delayed

from automl.search.strategy.base import SearchStrategy

class GridSearchStrategy(SearchStrategy):
    """Grid Search implementation"""

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """Return a default configuration for this strategy"""
        config = SearchStrategy.get_default_config()
        config.update({
            'pre_dispatch': '2*n_jobs',
            'return_train_score': False,
            'parallel_evaluation': True,  # Enable parallel evaluation
            'cache_evaluations': True,  # Cache evaluation results
            'batch_size': 10,  # Batch size for parallel processing
        })

        return config
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._evaluation_cache = {}  # Cache for evaluated parameter combinations
        self._model_copies = []  # Pre-created model copies for parallel evaluation
    
    def _get_params_hash(self, params: Dict[str, Any], model_class: str) -> str:
        """Generate a hash for caching parameter combinations."""
        params_str = str(sorted(params.items()))
        hash_input = f"{model_class}_{params_str}"
        return hashlib.md5(hash_input.encode()).hexdigest()
    
    def _evaluate_single_params(self, params: Dict[str, Any], model: BaseEstimator, 
                               X: np.ndarray, y: np.ndarray, cv, scoring_config) -> Dict[str, Any]:
        """Evaluate a single parameter combination using cross-validation."""
        try:
            # Check cache first
            cache_key = self._get_params_hash(params, model.__class__.__name__)
            if self.config.get('cache_evaluations', True) and cache_key in self._evaluation_cache:
                return self._evaluation_cache[cache_key].copy()
            
            # Set parameters
            model.set_params(**params)
            
            # Use cross_validate for efficient evaluation
            scores = cross_validate(
                model, X, y,
                cv=cv,
                scoring=scoring_config,
                n_jobs=1,  # Use 1 job here since we're parallelizing at a higher level
                return_train_score=self.config.get('return_train_score', False),
                error_score='raise'
            )
            
            result = {
                'test_scores': scores,
                'params': params,
                'fit_time': np.mean(scores.get('fit_time', [0])),
                'score_time': np.mean(scores.get('score_time', [0]))
            }
            
            # Cache the result
            if self.config.get('cache_evaluations', True):
                self._evaluation_cache[cache_key] = result
            
            return result
            
        except Exception as e:
            # Return error result
            return {
                'test_scores': None,
                'params': params,
                'fit_time': 0,
                'score_time': 0,
                'error': str(e)
            }
    
    def _evaluate_params_batch(self, param_combinations: List[Dict[str, Any]], model: BaseEstimator,
                              X: np.ndarray, y: np.ndarray, cv, scoring_config) -> List[Dict[str, Any]]:
        """Evaluate a batch of parameter combinations in parallel."""
        if self.config.get('parallel_evaluation', True) and len(param_combinations) > 1:
            n_jobs = min(self.config.get('n_jobs', 1), len(param_combinations))
            if n_jobs > 1 or n_jobs == -1:
                # Pre-create model copies for better memory management
                if not self._model_copies or len(self._model_copies) < n_jobs:
                    actual_n_jobs = n_jobs if n_jobs != -1 else 4  # Limit to 4 for -1
                    self._model_copies = [copy.deepcopy(model) for _ in range(min(actual_n_jobs, len(param_combinations)))]
                
                # Parallel evaluation
                results = Parallel(n_jobs=n_jobs, backend='threading' if len(param_combinations) < 10 else 'loky')(
                    delayed(self._evaluate_single_params)(
                        params, self._model_copies[i % len(self._model_copies)], X, y, cv, scoring_config
                    )
                    for i, params in enumerate(param_combinations)
                )
                return results
        
        # Sequential evaluation
        return [self._evaluate_single_params(params, model, X, y, cv, scoring_config) 
                for params in param_combinations]

    def _grid_search_core(self, param_grid, model_func, data, targets, cv, scoring, metric_sort, return_train_score):
        """Core grid search implementation with parallel evaluation."""
        # Convert scoring to cross_validate compatible format if needed
        if scoring is None:
            from sklearn.metrics import make_scorer
            scoring = {
                'accuracy': make_scorer(accuracy_score),
                'precision': make_scorer(precision_score, average='macro', zero_division=0),
                'recall': make_scorer(recall_score, average='macro', zero_division=0),
                'f1': make_scorer(f1_score, average='macro', zero_division=0)
            }
        
        # Ensure scoring is in the right format for cross_validate
        if not isinstance(scoring, dict):
            scoring = {'score': scoring}
            metric_sort = 'score'

        if metric_sort not in scoring:
            raise ValueError(f"metric_sort '{metric_sort}' not in scoring metrics")

        # Generate all parameter combinations
        keys = list(param_grid.keys())
        combinations = list(itertools.product(*(param_grid[key] for key in keys)))
        all_params = [dict(zip(keys, combo)) for combo in combinations]
        
        print(f"Grid Search: Evaluating {len(all_params)} parameter combinations...")
        
        # Create model instance for evaluation
        if callable(model_func):
            model = model_func()
        else:
            model = model_func
        
        # Batch evaluation
        batch_size = self.config.get('batch_size', 10)
        all_results = []
        
        for i in range(0, len(all_params), batch_size):
            batch_params = all_params[i:i+batch_size]
            batch_results = self._evaluate_params_batch(
                batch_params, model, data, targets, cv, scoring
            )
            all_results.extend(batch_results)
            
            # Progress indication
            if self.config.get('verbose', 1) > 0:
                print(f"Progress: {min(i+batch_size, len(all_params))}/{len(all_params)} combinations evaluated")
        
        # Process results and build cv_results_
        cv_results_ = {
            'params': [],
            'mean_test_score': [],
            'std_test_score': [],
            'rank_test_score': [],
            'mean_fit_time': [],
            'std_fit_time': [],
            'mean_score_time': [],
            'std_score_time': []
        }
        
        # Add metric-specific keys
        for metric in scoring.keys():
            cv_results_[f'mean_test_{metric}'] = []
            cv_results_[f'std_test_{metric}'] = []
            if return_train_score:
                cv_results_[f'mean_train_{metric}'] = []
                cv_results_[f'std_train_{metric}'] = []
        
        best_score = float('-inf')
        best_params = None
        best_all_scores = None

        # Process all results
        for idx, result in enumerate(all_results):
            params = result['params']
            cv_results_['params'].append(params)

            # Handle error case
            if result.get('test_scores') is None:
                # Failed evaluation
                for metric in scoring.keys():
                    cv_results_[f'mean_test_{metric}'].append(0.0)
                    cv_results_[f'std_test_{metric}'].append(0.0)
                    if return_train_score:
                        cv_results_[f'mean_train_{metric}'].append(0.0)
                        cv_results_[f'std_train_{metric}'].append(0.0)
                cv_results_['mean_test_score'].append(0.0)
                cv_results_['std_test_score'].append(0.0)
                cv_results_['mean_fit_time'].append(0.0)
                cv_results_['std_fit_time'].append(0.0)
                cv_results_['mean_score_time'].append(0.0)
                cv_results_['std_score_time'].append(0.0)
                continue
            
            # Extract scores from result
            test_scores = result['test_scores']
            
            # Calculate mean and std for each metric
            average_score = {}
            std_score = {}
            
            for metric in scoring.keys():
                metric_key = f'test_{metric}'
                if metric_key in test_scores:
                    scores_array = test_scores[metric_key]
                    average_score[metric] = np.mean(scores_array)
                    std_score[metric] = np.std(scores_array)
                    cv_results_[f'mean_test_{metric}'].append(average_score[metric])
                    cv_results_[f'std_test_{metric}'].append(std_score[metric])
                else:
                    average_score[metric] = 0.0
                    std_score[metric] = 0.0
                    cv_results_[f'mean_test_{metric}'].append(0.0)
                    cv_results_[f'std_test_{metric}'].append(0.0)
            
            # Handle train scores if requested
            if return_train_score:
                for metric in scoring.keys():
                    train_key = f'train_{metric}'
                    if train_key in test_scores:
                        train_scores_array = test_scores[train_key]
                        cv_results_[f'mean_train_{metric}'].append(np.mean(train_scores_array))
                        cv_results_[f'std_train_{metric}'].append(np.std(train_scores_array))
                    else:
                        cv_results_[f'mean_train_{metric}'].append(0.0)
                        cv_results_[f'std_train_{metric}'].append(0.0)
            
            # Overall scores
            cv_results_['mean_test_score'].append(average_score.get(metric_sort, 0.0))
            cv_results_['std_test_score'].append(std_score.get(metric_sort, 0.0))
            
            # Timing information
            cv_results_['mean_fit_time'].append(result.get('fit_time', 0.0))
            cv_results_['std_fit_time'].append(0.0)  # We don't have std for timing in this implementation
            cv_results_['mean_score_time'].append(result.get('score_time', 0.0))
            cv_results_['std_score_time'].append(0.0)
            
            # Track best score
            current_score = average_score.get(metric_sort, 0.0)
            if current_score > best_score:
                best_score = current_score
                best_params = params
                best_all_scores = average_score

        # Create rankings for each metric
        for metric in scoring.keys():
            test_scores = cv_results_[f'mean_test_{metric}']
            ranks = np.argsort(np.argsort(-np.array(test_scores))) + 1
            cv_results_[f'rank_test_{metric}'] = ranks.tolist()
        
        # Also create an overall ranking based on the sorting metric
        test_scores = cv_results_[f'mean_test_{metric_sort}']
        ranks = np.argsort(np.argsort(-np.array(test_scores))) + 1
        cv_results_['rank_test_score'] = ranks.tolist()

        # Clear caches after search completes
        self._evaluation_cache.clear()
        if hasattr(self, '_model_copies'):
            self._model_copies.clear()
        
        return best_params, best_score, best_all_scores, cv_results_

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
            tuple: (best_params, best_score, best_all_scores, cv_results)
                - best_params: Dictionary of best parameters
                - best_score: Best score achieved
                - best_all_scores: Dictionary with all metric scores for best parameters
                - cv_results: Dictionary with detailed cross-validation results
        """
        self.set_config(**{k: v for k, v in kwargs.items() if k in self.config})

        best_params, best_score, best_all_scores, cv_results = self._grid_search_core(
            param_grid=param_grid,
            model_func=model,
            data=X,
            targets=y,
            cv=self.config['cv'],
            scoring=self.config['scoring'],
            metric_sort=self.config['metric_sort'],
            return_train_score=self.config.get('return_train_score', False)
        )

        return best_params, best_score, best_all_scores, cv_results