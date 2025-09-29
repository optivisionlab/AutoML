from typing import Any, Dict,Tuple, List
import numpy as np
import pandas as pd
from datetime import datetime
import os
from sklearn.base import BaseEstimator
from sklearn.model_selection import cross_val_score
from skopt import gp_minimize
from skopt.space import Real, Integer, Categorical
from skopt.utils import use_named_args

from ..base import SearchStrategy

class BayesianSearchStrategy(SearchStrategy):
    """
        Thực thi tìm kiếm siêu tham số bằng Tối ưu hóa Bayesian (Bayesian Optimization)
        sử dụng thư viện scikit-optimize.
    """

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """Ghi đè cấu hình mặc định để thêm các tham số cho tối ưu hóa Bayesian"""
        base_config = SearchStrategy.get_default_config()
        bayesian_config = {
            'n_calls': 50, # Số lần gọi hàm mục tiêu để tối ưu hóa
            'scoring': 'accuracy', # Hàm đánh giá mô hình
            'log_dir': 'logs',  # Thư mục lưu log
            'save_log': True,  # Có lưu log không
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
            log_file = os.path.join(log_dir, f'bayesian_search_{timestamp}.csv')

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
        
        # Định nghĩa hàm mục tiêu
        @use_named_args(search_space)
        def objective(**params):
            model.set_params(**params)

            scoring = self.config['scoring']

            """
            Vì skopt tối thiểu hóa, chúng ta cần trả về giá trị âm của accuracy
            hoặc giá trị dương của lỗi (ví dụ: mean_squared_error)
            """
            score = np.mean(
                cross_val_score(
                    estimator=model,
                    X=X,
                    y=y,
                    cv=self.config['cv'],
                    n_jobs=self.config['n_jobs'],
                    scoring=scoring,
                    error_score=self.config['error_score']
                )
            )

            """
            Scikit-learn scorers cho các metric lớn hơn là tốt hơn (như accuracy)
            thường trả về giá trị dương. Các metric lỗi (như MSE) có scorer
            trả về giá trị âm (neg_mean_squared_error).
            gp_minimize luôn tối thiểu hóa, vì vậy ta chỉ cần trả về -score.
            """
            return -score  # Trả về âm của score để tối thiểu hóa

        # Callback function để lưu lịch sử
        def on_step(res):
            """Callback được gọi sau mỗi iteration để lưu kết quả"""
            iteration = len(res.x_iters)
            current_params = {param_names[i]: val for i, val in enumerate(res.x_iters[-1])}
            current_score = -res.func_vals[-1]
            best_score_so_far = -res.fun
            
            # Tạo dict để lưu vào history
            record = {
                'iteration': iteration,
                'score': current_score,
                'best_score': best_score_so_far,
                **current_params
            }
            search_history.append(record)
            
            # In thông tin ra console
            print(f"Iteration {iteration}/{self.config['n_calls']}: Score = {current_score:.6f}, Best = {best_score_so_far:.6f}")
            
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