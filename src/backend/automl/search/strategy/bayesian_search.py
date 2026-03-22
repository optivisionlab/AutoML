import hashlib
import logging
import time
from collections import Counter
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.model_selection import cross_validate
from skopt import gp_minimize
from skopt.space import Categorical
from skopt.utils import use_named_args

from automl.search.strategy.base import SearchStrategy, normalize_param_grid

# Cấu hình logger cho module này
logger = logging.getLogger(__name__)

class BayesianSearchStrategy(SearchStrategy):
    """
        Thực thi tìm kiếm siêu tham số bằng Tối ưu hóa Bayesian (Bayesian Optimization)
        sử dụng thư viện scikit-optimize.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._optimizer_state = {}  # Lưu trạng thái optimizer cho warm start
        self._cache_dir = kwargs.get('cache_dir', '.bayesian_cache')

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
        class_ratios = {cls: count / total_samples for cls, count in class_counts.items()}

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
        """Lấy cấu hình mặc định bằng cách tải từ file YAML."""
        base_config = SearchStrategy.get_default_config()

        # Tải cấu hình Bayesian từ file YAML (sử dụng method từ base class)
        bayesian_config = SearchStrategy._load_yaml_config('bayesian_search')

        if bayesian_config:
            base_config.update(bayesian_config)

        return base_config

    def _get_search_space_hash(self, search_space: List) -> str:
        """
        Tạo hash của search space để nhận dạng cấu hình.
        
        Args:
            search_space: Danh sách các dimensions
            
        Returns:
            str: Hash của search space
        """
        space_str = str([(d.name, str(d)) for d in search_space])
        return hashlib.md5(space_str.encode()).hexdigest()[:8]

    def _save_optimizer_state(self, result, search_space_hash: str, model_name: str):
        """
        Lưu trạng thái optimizer để sử dụng cho warm start.
        
        Args:
            result: Kết quả gp_minimize
            search_space_hash: Hash của search space
            model_name: Tên model
        """
        if not self.config.get('save_optimizer_state', True):
            return

        state = {
            'x_iters': result.x_iters,
            'func_vals': result.func_vals,
            'search_space_hash': search_space_hash,
        }

        key = f"{model_name}_{search_space_hash}"
        self._optimizer_state[key] = state

        if self.config.get('verbose', 1) > 1:
            logger.debug(f"Đã lưu trạng thái optimizer với {len(result.x_iters)} điểm")

    def _load_optimizer_state(self, search_space_hash: str, model_name: str) -> Tuple[List, List]:
        """
        Tải trạng thái optimizer để warm start.
        
        Args:
            search_space_hash: Hash của search space
            model_name: Tên model
            
        Returns:
            Tuple[List, List]: (x0, y0) cho warm start, hoặc (None, None) nếu không có
        """
        if not self.config.get('warm_start_enabled', False):
            return None, None

        key = f"{model_name}_{search_space_hash}"

        if key in self._optimizer_state:
            state = self._optimizer_state[key]
            if state.get('search_space_hash') == search_space_hash:
                x0 = state.get('x_iters', [])
                y0 = state.get('func_vals', [])
                if x0 and y0:
                    logger.info(f"Warm start: sử dụng {len(x0)} điểm từ lần chạy trước")
                    return x0, y0

        return None, None

    def _evaluate_default_params(self, model: BaseEstimator, X: np.ndarray, y: np.ndarray) -> Tuple[Dict, float, Dict, Dict]:
        """Đánh giá model với default params khi không có hyperparameters để tối ưu.

        Args:
            model: Mô hình scikit-learn
            X: Dữ liệu features
            y: Dữ liệu target

        Returns:
            Tuple: (best_params, best_score, best_all_scores, cv_results_)
        """
        scoring_config = self.config.get('scoring', {})
        metric_names = list(scoring_config.keys()) if scoring_config else ['accuracy']
        primary_metric = self.config.get('metric_sort', 'accuracy')

        scores = cross_validate(
            estimator=model,
            X=X,
            y=y,
            cv=self.config['cv'],
            n_jobs=self.config['n_jobs'],
            scoring=scoring_config,
            error_score=self.config['error_score'],
            return_train_score=False
        )

        # Tính mean score cho mỗi metric
        all_scores = {}
        for metric in metric_names:
            test_key = f'test_{metric}'
            if test_key in scores:
                all_scores[metric] = float(np.mean(scores[test_key]))

        best_score = all_scores.get(primary_metric, 0.0)

        # Xây dựng cv_results_ format
        cv_results_ = {
            'params': [{}],
            'mean_test_score': [best_score],
            'std_test_score': [0.0],
            'rank_test_score': [1],
        }
        for metric in metric_names:
            cv_results_[f'mean_test_{metric}'] = [all_scores.get(metric, 0.0)]
            cv_results_[f'std_test_{metric}'] = [0.0]
            cv_results_[f'rank_test_{metric}'] = [1]

        logger.info(f"Đánh giá {model.__class__.__name__} với default params: {primary_metric}={best_score:.4f}")

        return {}, best_score, all_scores, cv_results_

    def search(self, model: BaseEstimator, param_grid: List[Dict[str, Any]],
               X: np.ndarray, y: np.ndarray, **kwargs) -> tuple[dict[Any, Any], float, dict[Any, Any], dict[
        Any, Any]] | tuple:
        """
        Thực thi thuật toán tìm kiếm.

        Args:
            model (BaseEstimator): Mô hình scikit-learn.
            param_grid (List[Dict[str, Any]]): Một list-of-dicts hoặc một dict đơn lẻ, trong đó mỗi dict 
                                         chứa key là tên tham số và value có thể là:
                                         - Một dimension của skopt (Real, Integer, Categorical)
                                         - Một list các giá trị (sẽ được chuyển thành Categorical)
                                         - Một tuple các giá trị (sẽ được chuyển thành Categorical)
            X (np.ndarray): Dữ liệu features.
            y (np.ndarray): Dữ liệu target.
            **kwargs: Các tham số bổ sung cho gp_minimize.

        Returns:
            Tuple[Dict, float, Dict, Dict]: (best_params, best_score, best_all_scores, cv_results_)
                - best_params: Từ điển các tham số tốt nhất
                - best_score: Điểm số tốt nhất đạt được
                - best_all_scores: Từ điển với tất cả điểm số metric cho tham số tốt nhất  
                - cv_results_: Từ điển với kết quả cross-validation chi tiết
        """
        self.set_config(**kwargs)
        self._start_timer()  # Bắt đầu đếm thời gian

        # Chuẩn hóa param_grid về list-of-dicts format
        param_grid_list = normalize_param_grid(param_grid)

        # Chạy tối ưu hóa trên từng grid và trả về kết quả tốt nhất
        all_results = []
        all_cv_results = []

        for grid_idx, single_grid in enumerate(param_grid_list):
            if not single_grid:
                # Model không có hyperparameters → đánh giá với default params
                result = self._evaluate_default_params(model, X, y)
                all_results.append(result)
                all_cv_results.append(result[3])
                continue

            if self.config.get('verbose', 1) > 0:
                logger.info(f"Đang tối ưu hóa grid {grid_idx + 1}/{len(param_grid_list)}")

            result = self._search_single_grid(model, single_grid, X, y, **kwargs)
            all_results.append(result)
            all_cv_results.append(result[3])  # cv_results_

        # Nếu không có grid nào, trả về kết quả mặc định
        if not all_results:
            return {}, 0.0, {}, {}, False

        # Chọn kết quả tốt nhất dựa trên best_score
        best_idx = max(range(len(all_results)), key=lambda i: all_results[i][1])
        best_params, best_score, best_all_scores, _, _ = all_results[best_idx]

        # Gộp tất cả cv_results
        combined_cv_results = self._combine_cv_results(all_cv_results)

        return self._finalize_results(best_params, best_score, best_all_scores, combined_cv_results)

    def _combine_cv_results(self, cv_results_list: list) -> Dict[str, Any]:
        """Gộp cv_results từ nhiều grid thành một."""
        if not cv_results_list:
            return {}

        # Filter out empty dictionaries
        non_empty_results = [cv for cv in cv_results_list if cv]
        if not non_empty_results:
            return {}

        # Collect all unique keys from all cv_results dictionaries
        all_keys = set()
        for cv_results in non_empty_results:
            all_keys.update(cv_results.keys())

        combined = {}
        for key in all_keys:
            combined[key] = []
            for cv_results in non_empty_results:
                if key in cv_results:
                    combined[key].extend(cv_results[key])

        # Tính lại rank
        if 'mean_test_score' in combined and combined['mean_test_score']:
            test_scores = combined['mean_test_score']
            ranks = np.argsort(np.argsort(-np.array(test_scores))) + 1
            combined['rank_test_score'] = ranks.tolist()

        return combined

    def _search_single_grid(self, model: BaseEstimator, param_grid: Dict[str, Any],
               X: np.ndarray, y: np.ndarray, **kwargs) -> tuple:
        """
        Thực thi thuật toán tìm kiếm trên một grid đơn lẻ.
        """

        # Tạo đường dẫn file log sử dụng phương thức lớp cơ sở
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

        # Khởi tạo từ điển cv_results_ tương tự grid_search
        cv_results_ = {
            'params': [],
            'mean_test_score': [],
            'std_test_score': [],
            'rank_test_score': []
        }

        # Lấy danh sách metrics từ scoring config
        scoring_config = self.config.get('scoring', {})
        metric_names = list(scoring_config.keys()) if scoring_config else ['accuracy']

        # Thêm các trường cụ thể cho metric
        for metric in metric_names:
            cv_results_[f'mean_test_{metric}'] = []
            cv_results_[f'std_test_{metric}'] = []
            cv_results_[f'rank_test_{metric}'] = []

        # Theo dõi metrics tốt nhất cho tất cả điểm số
        best_all_scores = None

        # Xác định metrics nào cần tính toán
        averaging = self.config.get('averaging', 'both')
        optimize_for = self.config.get('optimize_for', 'auto')

        # Nếu optimize_for là 'auto', phát hiện dựa trên cân bằng lớp
        if optimize_for == 'auto':
            optimize_for = 'weighted' if self._detect_class_imbalance(y) else 'macro'
            if self.config.get('verbose', 1) > 0:
                logger.info(f"Tự động phát hiện mục tiêu tối ưu hóa: {optimize_for}")

        # Định nghĩa hàm mục tiêu
        @use_named_args(search_space)
        def objective(**params):
            model.set_params(**params)

            # Lấy cấu hình scoring
            scoring_config = self.config.get('scoring')

            # Xác định metric chính để tối ưu hóa
            primary_metric = self.config.get('metric_sort', 'accuracy')
            scoring_metrics = scoring_config

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

            # Lưu trữ tất cả metrics - sẽ được chuyển đổi sau
            objective.last_metrics = {}

            # Lưu trữ tất cả metrics từ scoring_config (dict từ engine.py)
            # scoring_metrics có dạng: {'accuracy': scorer, 'precision_macro': scorer, 'precision_weighted': scorer, 
            #                          'recall_macro': scorer, 'recall_weighted': scorer, 'f1_macro': scorer, 'f1_weighted': scorer}
            for key in scoring_metrics:
                test_key = f'test_{key}'
                if test_key in cv_results:
                    objective.last_metrics[key] = float(np.mean(cv_results[test_key]))

            # Chọn điểm số để tối ưu hóa
            score = objective.last_metrics.get(primary_metric, objective.last_metrics.get('accuracy', 0.0))

            # gp_minimize luôn tối thiểu hóa, vì vậy trả về -score
            return -score

        # Theo dõi để dừng sớm
        best_score_history = []
        early_stopping_patience = self.config.get('early_stopping_patience', 5)
        early_stopping_enabled = self.config.get('early_stopping_enabled', True)
        convergence_threshold = self.config.get('convergence_threshold', 0.001)

        # Hàm callback để lưu lịch sử
        self._last_callback_time = time.time()  # Theo dõi thời gian giữa các iteration
        def on_step(res):
            """Callback được gọi sau mỗi iteration để lưu kết quả"""
            nonlocal best_all_scores, best_score_history

            # Tính thời gian iteration vừa hoàn thành
            now = time.time()
            iteration_duration = now - self._last_callback_time
            self._last_callback_time = now

            iteration = len(res.x_iters)
            # Chuyển đổi kiểu numpy sang kiểu Python gốc sử dụng phương thức lớp cơ sở
            raw_params = {}
            for i, val in enumerate(res.x_iters[-1]):
                raw_params[param_names[i]] = val
            # Sử dụng bộ chuyển đổi lớp cơ sở để chuyển đổi toàn diện
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
            }
            # Thêm tất cả metrics vào record
            for metric_key in metric_names:
                record[metric_key] = metrics.get(metric_key, 0.0)

            # In thông tin ra console
            if self.config.get('verbose', 1) > 0:
                metrics_str = ", ".join([f"{k}={metrics.get(k, 0.0):.4f}" for k in metric_names])
                logger.info(f"Lần lặp {iteration}/{self.config['n_calls']}: {metrics_str}")

            search_history.append(record)

            # Điền dữ liệu vào cv_results_
            cv_results_['params'].append(current_params)
            cv_results_['mean_test_score'].append(current_score)
            cv_results_['std_test_score'].append(0.0)  # Bayesian opt không tính std cho mỗi iteration

            # Thêm tất cả metrics vào cv_results_
            for metric_key in metric_names:
                cv_results_[f'mean_test_{metric_key}'].append(metrics.get(metric_key, 0.0))
                cv_results_[f'std_test_{metric_key}'].append(0.0)

            # Cập nhật best_all_scores nếu đây là kết quả tốt nhất cho đến nay
            if current_score >= best_score_so_far:
                best_all_scores = SearchStrategy.convert_numpy_types(metrics.copy())

            # Theo dõi lịch sử điểm số để dừng sớm
            best_score_history.append(best_score_so_far)

            # Kiểm tra time limit (sử dụng base.py)
            if not self._should_start_next_iteration(iteration_duration=iteration_duration):
                logger.info(f"Dừng search tại iteration {iteration}.")
                return True  # Dừng gp_minimize

            # Kiểm tra điều kiện dừng sớm (chỉ khi không có time limit)
            if early_stopping_enabled and self._should_apply_early_stopping() and iteration >= early_stopping_patience:
                # Kiểm tra nếu không có cải thiện trong số lần lặp patience
                recent_scores = best_score_history[-early_stopping_patience:]
                if len(set(recent_scores)) == 1:  # Không có cải thiện
                    logger.info(f"Dừng sớm tại iteration {iteration} (không có cải thiện trong {early_stopping_patience} lần lặp)")
                    return True  # Điều này sẽ dừng gp_minimize

                # Kiểm tra ngưỡng hội tụ (chỉ khi không có time limit)
                if self._should_apply_early_stopping() and len(best_score_history) > 1:
                    recent_improvement = best_score_history[-1] - best_score_history[-2]
                    if abs(recent_improvement) < convergence_threshold:
                        logger.info(f"Phát hiện hội tụ tại iteration {iteration} (cải thiện < {convergence_threshold:.4f})")
                        return True

            # Lưu log sau mỗi iteration nếu được yêu cầu
            if self.config['save_log']:
                df = pd.DataFrame(search_history)
                df.to_csv(log_file, index=False)

            # Trả về False để tiếp tục tối ưu hóa (True sẽ dừng)
            return False

        # Lọc kwargs để chỉ giữ các tham số hợp lệ cho gp_minimize
        # Loại bỏ các tham số của SearchStrategy như 'scoring', 'cv', 'n_jobs', 'error_score'
        valid_gp_minimize_params = ['n_initial_points', 'acq_func', 'acq_optimizer',
                                    'x0', 'y0', 'noise', 'n_points', 'n_restarts_optimizer',
                                    'xi', 'kappa', 'verbose', 'callback', 'n_jobs']
        gp_kwargs = {k: v for k, v in kwargs.items() if k in valid_gp_minimize_params}

        # Thêm các tham số tối ưu từ config nếu chưa được chỉ định
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

        # Warm start: tải trạng thái từ lần chạy trước
        search_space_hash = self._get_search_space_hash(search_space)
        model_name = model.__class__.__name__

        x0, y0 = self._load_optimizer_state(search_space_hash, model_name)

        # Thêm x0, y0 vào gp_kwargs nếu có
        if x0 is not None and y0 is not None:
            # Giảm số điểm initial khi warm start
            gp_kwargs['n_initial_points'] = max(1, gp_kwargs.get('n_initial_points', 5) // 2)
            gp_kwargs['x0'] = x0
            gp_kwargs['y0'] = y0

        # Thực thi tối ưu hóa Bayesian với hỗ trợ song song
        # Đảm bảo n_jobs được thiết lập để tối ưu hóa hàm acquisition song song
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

        # Lưu trạng thái optimizer cho warm start tương lai
        self._save_optimizer_state(result, search_space_hash, model_name)

        # Lấy tham số tốt nhất và điểm số tốt nhất
        # Chuyển đổi kiểu numpy sang kiểu Python gốc sử dụng phương thức lớp cơ sở
        raw_best_params = {}
        for i, val in enumerate(result.x):
            raw_best_params[param_names[i]] = val
        best_params = SearchStrategy.convert_numpy_types(raw_best_params)

        best_score = float(-result.fun) if hasattr(result.fun, 'item') else -result.fun  # Đổi dấu để lấy giá trị dương

        # Tính toán xếp hạng cho cv_results_
        for metric in metric_names:
            test_scores = cv_results_.get(f'mean_test_{metric}', [])
            if test_scores:
                ranks = np.argsort(np.argsort(-np.array(test_scores))) + 1
                cv_results_[f'rank_test_{metric}'] = ranks.tolist()

        # Xếp hạng tổng thể dựa trên metric tối ưu hóa
        test_scores = cv_results_['mean_test_score']
        if test_scores:
            ranks = np.argsort(np.argsort(-np.array(test_scores))) + 1
            cv_results_['rank_test_score'] = ranks.tolist()

        # Nếu best_all_scores chưa được thiết lập (không nên xảy ra), tạo từ lần chạy cuối
        if best_all_scores is None:
            raw_metrics = getattr(objective, 'last_metrics', {})
            best_all_scores = SearchStrategy.convert_numpy_types(raw_metrics)

        # In thông báo về vị trí file log
        if self.config['save_log']:
            logger.info(f"Đã lưu log tìm kiếm vào: {log_file}")

        # Xóa cache và chuyển đổi kiểu numpy trước khi trả về
        return self._finalize_results(best_params, best_score, best_all_scores, cv_results_)
