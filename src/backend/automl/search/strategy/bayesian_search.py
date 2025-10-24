from typing import Any, Dict, Tuple
import numpy as np
import pandas as pd
from datetime import datetime
import os
import logging
from sklearn.base import BaseEstimator
from sklearn.model_selection import cross_validate
from skopt import gp_minimize
from skopt.space import Categorical
from skopt.utils import use_named_args
from collections import Counter

from automl.search.strategy.base import SearchStrategy

# Configure logger for this module
logger = logging.getLogger(__name__)

class BayesianSearchStrategy(SearchStrategy):
    """
        Thực thi tìm kiếm siêu tham số bằng Tối ưu hóa Bayesian (Bayesian Optimization)
        sử dụng thư viện scikit-optimize.
    """

    def _detect_class_imbalance(self, y: np.ndarray) -> bool:
        """
        Phát hiện xem tập dữ liệu có mất cân bằng lớp hay không.
        
        Args:
            y: Mảng nhãn
            
        Returns:
            bool: True nếu mất cân bằng, False nếu cân bằng
        """
        # Đếm số lượng của mỗi lớp
        class_counts = Counter(y)
        total_samples = len(y)
        
        # Tính tỷ lệ của mỗi lớp
        class_ratios = {cls: count/total_samples for cls, count in class_counts.items()}
        
        # Tìm tỷ lệ nhỏ nhất và lớn nhất
        min_ratio = min(class_ratios.values())
        max_ratio = max(class_ratios.values())
        
        # Kiểm tra xem sự khác biệt có đáng kể không
        threshold = self.config.get('imbalance_threshold', 0.3)
        
        # Nếu chênh lệch giữa lớp nhỏ nhất và lớn nhất vượt ngưỡng, dữ liệu mất cân bằng
        return (max_ratio - min_ratio) > threshold
    
    def _get_averaging_method(self, y: np.ndarray) -> str:
        """
        Xác định phương pháp tính trung bình nào sẽ sử dụng dựa trên cấu hình và dữ liệu.
        
        Args:
            y: Mảng nhãn
            
        Returns:
            str: 'macro' hoặc 'weighted'
        """
        averaging = self.config.get('averaging', 'auto')
        
        if averaging == 'auto':
            # Tự động phát hiện dựa trên cân bằng lớp
            if self._detect_class_imbalance(y):
                logger.info("Phát hiện mất cân bằng lớp. Sử dụng trung bình có trọng số (weighted).")
                return 'weighted'
            else:
                logger.info("Phát hiện các lớp cân bằng. Sử dụng trung bình macro.")
                return 'macro'
        elif averaging in ['macro', 'weighted']:
            logger.info(f"Sử dụng trung bình {averaging} theo cấu hình.")
            return averaging
        else:
            logger.warning(f"Phương pháp tính trung bình '{averaging}' không hợp lệ. Mặc định dùng macro.")
            return 'macro'

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """Ghi đè cấu hình mặc định để thêm các tham số cho tối ưu hóa Bayesian"""
        base_config = SearchStrategy.get_default_config()
        bayesian_config = {
            'n_calls': 25,  # Reduced for faster runtime (was 50)
            'n_initial_points': 5,  # Reduced initial random exploration (default is 10)
            'acq_func': 'EI',  # Expected Improvement - faster than default 'gp_hedge'
            'acq_optimizer': 'sampling',  # Faster than 'lbfgs' for acquisition
            'scoring': 'accuracy',  # Hàm đánh giá mô hình
            'metrics': ['accuracy', 'precision', 'recall', 'f1'],
            'averaging': 'macro',  # Single averaging method is faster than 'both'
            'optimize_for': 'auto',  # 'auto', 'macro', 'weighted' 
            'imbalance_threshold': 0.3,  # Threshold for detecting class imbalance (auto mode)
            'early_stopping_enabled': True,  # Enable early stopping
            'early_stopping_patience': 5,  # Stop if no improvement for these many iterations
            'convergence_threshold': 0.001,  # Stop if improvement < threshold
        }
        base_config.update(bayesian_config)
        return base_config

    def search(self, model: BaseEstimator, param_grid: Dict[str, Any],
               X: np.ndarray, y: np.ndarray, **kwargs) -> Tuple[Dict[str, Any], float, Dict[str, float], Dict[str, Any]]:
        """
        Thực thi thuật toán tìm kiếm.

        Args:
            model (BaseEstimator): Mô hình scikit-learn.
            param_grid (Dict[str, Any]): Một dictionary trong đó key là tên tham số và 
                                         value là một dimension của skopt (Real, Integer, Categorical).
            X (np.ndarray): Dữ liệu features.
            y (np.ndarray): Dữ liệu target.
            **kwargs: Các tham số bổ sung cho gp_minimize.

        Returns:
            Tuple[Dict, float, Dict, Dict]: (best_params, best_score, best_all_scores, cv_results_)
                - best_params: Dictionary of best parameters
                - best_score: Best score achieved
                - best_all_scores: Dictionary with all metric scores for best parameters  
                - cv_results_: Dictionary with detailed cross-validation results
        """
        self.set_config(**kwargs)

        # Create a log file path using the base class method
        log_file = self.create_log_file_path(model, 'bayesian_search')

        # Chuyển đổi param_grid thành danh sách các dimension
        search_space = []
        param_names = []

        for param_name, param_value in param_grid.items():
            # Nếu param_value là dimension object (Real, Integer, Categorical)
            if hasattr(param_value, 'name'):
                if param_value.name is None:
                    param_value.name = param_name
                search_space.append(param_value)
                param_names.append(param_name)
            # Nếu param_value là list hoặc tuple, chuyển thành Categorical
            elif isinstance(param_value, (list, tuple)):
                dim = Categorical(param_value, name=param_name)
                search_space.append(dim)
                param_names.append(param_name)
            else:
                raise ValueError(f"Invalid parameter type for {param_name}: {type(param_value)}")

        # Danh sách để lưu lịch sử tìm kiếm
        search_history = []
        
        # Initialize cv_results_ dictionary similar to grid_search
        cv_results_ = {
            'params': [],
            'mean_test_score': [],
            'std_test_score': [],
            'rank_test_score': []
        }
        
        # Add metric-specific fields
        metrics = self.config.get('metrics', ['accuracy', 'precision', 'recall', 'f1'])
        for metric in metrics:
            cv_results_[f'mean_test_{metric}'] = []
            cv_results_[f'std_test_{metric}'] = []
            cv_results_[f'rank_test_{metric}'] = []
        
        # Track best metrics for all scores
        best_all_scores = None
        
        # Determine which metrics to compute
        averaging = self.config.get('averaging', 'both')
        optimize_for = self.config.get('optimize_for', 'auto')
        
        # If optimize_for is 'auto', detect based on class balance
        if optimize_for == 'auto':
            optimize_for = 'weighted' if self._detect_class_imbalance(y) else 'macro'
            if self.config.get('verbose', 1) > 0:
                logger.info(f"Auto-detected optimization target: {optimize_for}")

        # Định nghĩa hàm mục tiêu
        @use_named_args(search_space)
        def objective(**params):
            model.set_params(**params)

            # Get the scoring config - might be a dict or a string
            scoring_config = self.config.get('scoring')
            metrics = self.config.get('metrics', ['accuracy', 'precision', 'recall', 'f1'])
            
            # Determine the primary metric to optimize
            # If scoring is a dict, use metric_sort; otherwise use scoring as the primary metric
            if isinstance(scoring_config, dict):
                # When scoring is a dict (from engine.py), use metric_sort as primary metric
                primary_metric = self.config.get('metric_sort', 'accuracy')
                scoring_metrics = scoring_config  # Use the provided scoring dict directly
            else:
                # When scoring is a string (legacy behavior)
                primary_metric = scoring_config if scoring_config else 'accuracy'
                
                # Build scoring metrics dict based on averaging setting
                scoring_metrics = {}
                
                if averaging == 'both':
                    # Compute both macro and weighted metrics
                    scoring_metrics['accuracy'] = 'accuracy'
                    for metric in ['precision', 'recall', 'f1']:
                        if metric in metrics:
                            scoring_metrics[f'{metric}_macro'] = f'{metric}_macro'
                            scoring_metrics[f'{metric}_weighted'] = f'{metric}_weighted'
                    
                    # Add the primary scoring metric if not already included
                    if primary_metric != 'accuracy' and primary_metric in metrics:
                        if f'{primary_metric}_macro' not in scoring_metrics:
                            scoring_metrics[f'{primary_metric}_macro'] = f'{primary_metric}_macro'
                        if f'{primary_metric}_weighted' not in scoring_metrics:
                            scoring_metrics[f'{primary_metric}_weighted'] = f'{primary_metric}_weighted'
                            
                else:
                    # Use only specified averaging method
                    avg_method = averaging if averaging in ['macro', 'weighted'] else 'macro'
                    scoring_metrics['accuracy'] = 'accuracy'
                    for metric in metrics:
                        if metric == 'accuracy':
                            continue
                        scoring_metrics[metric] = f'{metric}_{avg_method}'

            cv_results = cross_validate(
                estimator=model,
                X=X,
                y=y,
                cv=self.config['cv'],
                n_jobs=self.config['n_jobs'],
                scoring=scoring_metrics,
                error_score=self.config['error_score'],
                return_train_score=False
            )

            # Store all metrics - will be converted later
            objective.last_metrics = {}
            
            if averaging == 'both':
                # Store both macro and weighted metrics - convert numpy types
                objective.last_metrics['accuracy'] = float(np.mean(cv_results['test_accuracy']))
                
                for metric in ['precision', 'recall', 'f1']:
                    if f'{metric}_macro' in scoring_metrics:
                        objective.last_metrics[f'{metric}_macro'] = float(np.mean(cv_results[f'test_{metric}_macro']))
                    if f'{metric}_weighted' in scoring_metrics:
                        objective.last_metrics[f'{metric}_weighted'] = float(np.mean(cv_results[f'test_{metric}_weighted']))
                
                # Choose which score to optimize based on configuration
                if primary_metric == 'accuracy':
                    score = objective.last_metrics['accuracy']
                else:
                    score = objective.last_metrics.get(f'{primary_metric}_{optimize_for}', 
                                                      objective.last_metrics.get('accuracy', 0.0))
            else:
                # Single averaging method - convert numpy types
                for key in scoring_metrics:
                    objective.last_metrics[key] = float(np.mean(cv_results[f'test_{key}']))
                score = objective.last_metrics.get(primary_metric, objective.last_metrics.get('accuracy', 0.0))

            # gp_minimize luôn tối thiểu hóa, vì vậy trả về -score
            return -score

        # Track for early stopping
        best_score_history = []
        early_stopping_patience = self.config.get('early_stopping_patience', 5)
        early_stopping_enabled = self.config.get('early_stopping_enabled', True)
        convergence_threshold = self.config.get('convergence_threshold', 0.001)
        
        # Hàm callback để lưu lịch sử
        def on_step(res):
            """Callback được gọi sau mỗi iteration để lưu kết quả"""
            nonlocal best_all_scores, best_score_history
            
            iteration = len(res.x_iters)
            # Convert numpy types to native Python types using base class method
            raw_params = {}
            for i, val in enumerate(res.x_iters[-1]):
                raw_params[param_names[i]] = val
            # Use the base class converter for comprehensive conversion
            current_params = SearchStrategy.convert_numpy_types(raw_params)
            
            current_score = float(-res.func_vals[-1]) if hasattr(res.func_vals[-1], 'item') else -res.func_vals[-1]
            best_score_so_far = float(-res.fun) if hasattr(res.fun, 'item') else -res.fun

            # Lấy tên model
            model_name = model.__class__.__name__

            # Lấy metrics từ iteration hiện tại và convert numpy types
            raw_metrics = getattr(objective, 'last_metrics', {})
            metrics = SearchStrategy.convert_numpy_types(raw_metrics)
            
            # Tạo bản ghi cho lịch sử
            record = {
                'model': model_name,
                'run_type': 'bayesian_search',
                'best_params': str(current_params),
                'accuracy': metrics.get('accuracy', 0.0),
            }
            
            # Thêm metrics dựa trên cấu hình averaging
            if averaging == 'both':
                # Thêm cả metric macro và weighted
                for metric_type in ['precision', 'recall', 'f1']:
                    record[f'{metric_type}_macro'] = metrics.get(f'{metric_type}_macro', 0.0)
                    record[f'{metric_type}_weighted'] = metrics.get(f'{metric_type}_weighted', 0.0)
                
                # In thông tin ra console với cả hai loại  
                if self.config.get('verbose', 1) > 0:
                    logger.info(f"Lần lặp {iteration}/{self.config['n_calls']}: ")
                    logger.info(f"  Độ chính xác={metrics.get('accuracy', 0.0):.4f}")
                    logger.info(f"  Macro   - P={metrics.get('precision_macro', 0.0):.4f}, "
                          f"R={metrics.get('recall_macro', 0.0):.4f}, "
                          f"F1={metrics.get('f1_macro', 0.0):.4f}")
                    logger.info(f"  Weighted- P={metrics.get('precision_weighted', 0.0):.4f}, "
                          f"R={metrics.get('recall_weighted', 0.0):.4f}, "
                          f"F1={metrics.get('f1_weighted', 0.0):.4f}")
                    logger.info(f"  Đang tối ưu cho: {optimize_for}")
                
            else:
                # Phương pháp averaging đơn
                avg_suffix = '' if averaging not in ['macro', 'weighted'] else f'_{averaging}'
                for metric_type in ['precision', 'recall', 'f1']:
                    key = f'{metric_type}{avg_suffix}' if avg_suffix else metric_type
                    record[metric_type] = metrics.get(key, 0.0)
                
                # In thông tin ra console
                if self.config.get('verbose', 1) > 0:
                    logger.info(f"Lần lặp {iteration}/{self.config['n_calls']}: "
                          f"Độ chính xác={metrics.get('accuracy', 0.0):.4f}, "
                          f"Precision={record.get('precision', 0.0):.4f}, "
                          f"Recall={record.get('recall', 0.0):.4f}, "
                          f"F1={record.get('f1', 0.0):.4f}")
            
            search_history.append(record)
            
            # Populate cv_results_
            cv_results_['params'].append(current_params)
            cv_results_['mean_test_score'].append(current_score)
            cv_results_['std_test_score'].append(0.0)  # Bayesian opt doesn't compute std per iteration
            
            # Add metrics to cv_results_
            cv_results_['mean_test_accuracy'].append(metrics.get('accuracy', 0.0))
            cv_results_['std_test_accuracy'].append(0.0)
            
            if averaging == 'both':
                # Add both macro and weighted metrics
                for metric_type in ['precision', 'recall', 'f1']:
                    # For compatibility, use the optimized version
                    if optimize_for == 'macro':
                        cv_results_[f'mean_test_{metric_type}'].append(metrics.get(f'{metric_type}_macro', 0.0))
                    else:
                        cv_results_[f'mean_test_{metric_type}'].append(metrics.get(f'{metric_type}_weighted', 0.0))
                    cv_results_[f'std_test_{metric_type}'].append(0.0)
            else:
                # Single averaging method
                avg_suffix = '' if averaging not in ['macro', 'weighted'] else f'_{averaging}'
                for metric_type in ['precision', 'recall', 'f1']:
                    key = f'{metric_type}{avg_suffix}' if avg_suffix else metric_type
                    cv_results_[f'mean_test_{metric_type}'].append(metrics.get(key, 0.0))
                    cv_results_[f'std_test_{metric_type}'].append(0.0)
            
            # Update best_all_scores if this is the best so far
            if current_score >= best_score_so_far:
                best_all_scores = SearchStrategy.convert_numpy_types(metrics.copy())
            
            # Track score history for early stopping
            best_score_history.append(best_score_so_far)
            
            # Check early stopping conditions
            if early_stopping_enabled and iteration >= early_stopping_patience:
                # Check if no improvement for patience iterations
                recent_scores = best_score_history[-early_stopping_patience:]
                if len(set(recent_scores)) == 1:  # No improvement
                    logger.info(f"Early stopping at iteration {iteration} (no improvement for {early_stopping_patience} iterations)")
                    return True  # This will stop gp_minimize
                
                # Check convergence threshold
                if len(best_score_history) > 1:
                    recent_improvement = best_score_history[-1] - best_score_history[-2]
                    if abs(recent_improvement) < convergence_threshold:
                        logger.info(f"Convergence detected at iteration {iteration} (improvement < {convergence_threshold:.4f})")
                        return True

            # Lưu log sau mỗi iteration nếu được yêu cầu
            if self.config['save_log']:
                df = pd.DataFrame(search_history)
                df.to_csv(log_file, index=False)

        # Lọc kwargs để chỉ giữ các tham số hợp lệ cho gp_minimize
        # Loại bỏ các tham số của SearchStrategy như 'scoring', 'cv', 'n_jobs', 'error_score'
        valid_gp_minimize_params = ['n_initial_points', 'acq_func', 'acq_optimizer',
                                    'x0', 'y0', 'noise', 'n_points', 'n_restarts_optimizer',
                                    'xi', 'kappa', 'verbose', 'callback', 'n_jobs']
        gp_kwargs = {k: v for k, v in kwargs.items() if k in valid_gp_minimize_params}
        
        # Add optimized parameters from config if not already specified
        if 'n_initial_points' not in gp_kwargs:
            gp_kwargs['n_initial_points'] = self.config.get('n_initial_points', 5)
        if 'acq_func' not in gp_kwargs:
            gp_kwargs['acq_func'] = self.config.get('acq_func', 'EI')
        if 'acq_optimizer' not in gp_kwargs:
            gp_kwargs['acq_optimizer'] = self.config.get('acq_optimizer', 'sampling')

        # Thêm callback vào gp_kwargs
        if 'callback' in gp_kwargs:
            if isinstance(gp_kwargs['callback'], list):
                gp_kwargs['callback'].append(on_step)
            else:
                gp_kwargs['callback'] = [gp_kwargs['callback'], on_step]
        else:
            gp_kwargs['callback'] = [on_step]

        # Thực thi tối ưu hóa Bayesian with parallel support
        # Ensure n_jobs is set for parallel acquisition function optimization
        if 'n_jobs' not in gp_kwargs:
            import multiprocessing
            gp_kwargs['n_jobs'] = self.config.get('n_jobs', multiprocessing.cpu_count())
        
        result = gp_minimize(
            func=objective,
            dimensions=search_space,
            n_calls=self.config['n_calls'],
            random_state=self.config['random_state'],
            **gp_kwargs
        )

        # Lấy tham số tốt nhất và điểm số tốt nhất
        # Convert numpy types to native Python types using base class method
        raw_best_params = {}
        for i, val in enumerate(result.x):
            raw_best_params[param_names[i]] = val
        best_params = SearchStrategy.convert_numpy_types(raw_best_params)
        
        best_score = float(-result.fun) if hasattr(result.fun, 'item') else -result.fun  # Đổi dấu để lấy giá trị dương
        
        # Compute rankings for cv_results_
        for metric in metrics:
            test_scores = cv_results_[f'mean_test_{metric}']
            if test_scores:
                ranks = np.argsort(np.argsort(-np.array(test_scores))) + 1
                cv_results_[f'rank_test_{metric}'] = ranks.tolist()
        
        # Overall ranking based on the optimization metric
        test_scores = cv_results_['mean_test_score']
        if test_scores:
            ranks = np.argsort(np.argsort(-np.array(test_scores))) + 1
            cv_results_['rank_test_score'] = ranks.tolist()
        
        # If best_all_scores was not set (shouldn't happen), create it from the final run
        if best_all_scores is None:
            raw_metrics = getattr(objective, 'last_metrics', {})
            best_all_scores = SearchStrategy.convert_numpy_types(raw_metrics)

        # In thông báo về vị trí file log
        if self.config['save_log']:
            logger.info(f"Đã lưu log tìm kiếm vào: {log_file}")

        # Convert all numpy types in cv_results_ to native Python types
        cv_results_ = SearchStrategy.convert_numpy_types(cv_results_)

        return best_params, best_score, best_all_scores, cv_results_
