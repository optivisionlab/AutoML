from typing import Any, Dict, Tuple, List
import numpy as np
import pandas as pd
from typing import Any, Dict, Tuple, List
import numpy as np
import pandas as pd
from datetime import datetime
import os
from sklearn.base import BaseEstimator
from sklearn.model_selection import cross_val_score, cross_validate
from skopt import gp_minimize
from skopt.space import Real, Integer, Categorical
from skopt.utils import use_named_args
from collections import Counter

from automl.search.base import SearchStrategy

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
                print("Phát hiện mất cân bằng lớp. Sử dụng trung bình có trọng số (weighted).")
                return 'weighted'
            else:
                print("Phát hiện các lớp cân bằng. Sử dụng trung bình macro.")
                return 'macro'
        elif averaging in ['macro', 'weighted']:
            print(f"Sử dụng trung bình {averaging} theo cấu hình.")
            return averaging
        else:
            print(f"Phương pháp tính trung bình '{averaging}' không hợp lệ. Mặc định dùng macro.")
            return 'macro'

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """Ghi đè cấu hình mặc định để thêm các tham số cho tối ưu hóa Bayesian"""
        base_config = SearchStrategy.get_default_config()
        bayesian_config = {
            'n_calls': 50,  # Số lần gọi hàm mục tiêu để tối ưu hóa
            'scoring': 'accuracy',  # Hàm đánh giá mô hình
            'metrics': ['accuracy', 'precision', 'recall', 'f1'],
            'log_dir': 'logs',  # Thư mục lưu log
            'save_log': True,  # Có lưu log không
            'averaging': 'both',  # 'both', 'macro', 'weighted' - 'both' computes both types
            'optimize_for': 'auto',  # 'auto', 'macro', 'weighted' - which metric to optimize when averaging='both'
            'imbalance_threshold': 0.3,  # Threshold for detecting class imbalance (auto mode)
        }
        base_config.update(bayesian_config)
        return base_config

    def search(self, model: BaseEstimator, param_grid: Dict[str, Any],
               X: np.ndarray, y: np.ndarray, **kwargs) -> Tuple[Dict[str, Any], float, Any]:
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
            Tuple[Dict, float, Any]: (best_params, best_score, optimizer_result)
        """
        self.set_config(**kwargs)

        # Tạo thư mục log nếu cần
        if self.config['save_log']:
            log_dir = self.config['log_dir']
            os.makedirs(log_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            model_name = model.__class__.__name__
            log_file = os.path.join(log_dir, f'bayesian_search_{model_name}_{timestamp}.csv')

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
        
        # Determine which metrics to compute
        averaging = self.config.get('averaging', 'both')
        optimize_for = self.config.get('optimize_for', 'auto')
        
        # If optimize_for is 'auto', detect based on class balance
        if optimize_for == 'auto':
            optimize_for = 'weighted' if self._detect_class_imbalance(y) else 'macro'
            print(f"Auto-detected optimization target: {optimize_for}")

        # Định nghĩa hàm mục tiêu
        @use_named_args(search_space)
        def objective(**params):
            model.set_params(**params)

            scoring = self.config['scoring']
            metrics = self.config.get('metrics', ['accuracy', 'precision', 'recall', 'f1'])

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
                if scoring != 'accuracy' and scoring in metrics:
                    if f'{scoring}_macro' not in scoring_metrics:
                        scoring_metrics[f'{scoring}_macro'] = f'{scoring}_macro'
                    if f'{scoring}_weighted' not in scoring_metrics:
                        scoring_metrics[f'{scoring}_weighted'] = f'{scoring}_weighted'
                        
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

            # Store all metrics
            objective.last_metrics = {}
            
            if averaging == 'both':
                # Store both macro and weighted metrics
                objective.last_metrics['accuracy'] = np.mean(cv_results['test_accuracy'])
                
                for metric in ['precision', 'recall', 'f1']:
                    if f'{metric}_macro' in scoring_metrics:
                        objective.last_metrics[f'{metric}_macro'] = np.mean(cv_results[f'test_{metric}_macro'])
                    if f'{metric}_weighted' in scoring_metrics:
                        objective.last_metrics[f'{metric}_weighted'] = np.mean(cv_results[f'test_{metric}_weighted'])
                
                # Choose which score to optimize based on configuration
                if scoring == 'accuracy':
                    score = objective.last_metrics['accuracy']
                else:
                    score = objective.last_metrics.get(f'{scoring}_{optimize_for}', 
                                                      objective.last_metrics.get('accuracy', 0.0))
            else:
                # Single averaging method
                for key in scoring_metrics:
                    objective.last_metrics[key] = np.mean(cv_results[f'test_{key}'])
                score = objective.last_metrics.get(scoring, objective.last_metrics.get('accuracy', 0.0))

            # gp_minimize luôn tối thiểu hóa, vì vậy trả về -score
            return -score

        # Hàm callback để lưu lịch sử
        def on_step(res):
            """Callback được gọi sau mỗi iteration để lưu kết quả"""
            iteration = len(res.x_iters)
            current_params = {param_names[i]: val for i, val in enumerate(res.x_iters[-1])}
            current_score = -res.func_vals[-1]
            best_score_so_far = -res.fun

            # Lấy tên model
            model_name = model.__class__.__name__

            # Lấy metrics từ iteration hiện tại
            metrics = getattr(objective, 'last_metrics', {})
            
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
                print(f"Lần lặp {iteration}/{self.config['n_calls']}: ")
                print(f"  Độ chính xác={metrics.get('accuracy', 0.0):.4f}")
                print(f"  Macro   - P={metrics.get('precision_macro', 0.0):.4f}, "
                      f"R={metrics.get('recall_macro', 0.0):.4f}, "
                      f"F1={metrics.get('f1_macro', 0.0):.4f}")
                print(f"  Weighted- P={metrics.get('precision_weighted', 0.0):.4f}, "
                      f"R={metrics.get('recall_weighted', 0.0):.4f}, "
                      f"F1={metrics.get('f1_weighted', 0.0):.4f}")
                print(f"  Đang tối ưu cho: {optimize_for}")
                
            else:
                # Phương pháp averaging đơn
                avg_suffix = '' if averaging not in ['macro', 'weighted'] else f'_{averaging}'
                for metric_type in ['precision', 'recall', 'f1']:
                    key = f'{metric_type}{avg_suffix}' if avg_suffix else metric_type
                    record[metric_type] = metrics.get(key, 0.0)
                
                # In thông tin ra console
                print(f"Lần lặp {iteration}/{self.config['n_calls']}: "
                      f"Độ chính xác={metrics.get('accuracy', 0.0):.4f}, "
                      f"Precision={record.get('precision', 0.0):.4f}, "
                      f"Recall={record.get('recall', 0.0):.4f}, "
                      f"F1={record.get('f1', 0.0):.4f}")
            
            search_history.append(record)

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

        # Thêm callback vào gp_kwargs
        if 'callback' in gp_kwargs:
            if isinstance(gp_kwargs['callback'], list):
                gp_kwargs['callback'].append(on_step)
            else:
                gp_kwargs['callback'] = [gp_kwargs['callback'], on_step]
        else:
            gp_kwargs['callback'] = [on_step]

        # Thực thi tối ưu hóa Bayesian
        result = gp_minimize(
            func=objective,
            dimensions=search_space,
            n_calls=self.config['n_calls'],
            random_state=self.config['random_state'],
            **gp_kwargs
        )

        # Lấy tham số tốt nhất và điểm số tốt nhất
        best_params = {param_names[i]: val for i, val in enumerate(result.x)}
        best_score = -result.fun  # Đổi dấu để lấy giá trị dương

        # In thông báo về vị trí file log
        if self.config['save_log']:
            print(f"\nĐã lưu log tìm kiếm vào: {log_file}")

        return best_params, best_score, result
