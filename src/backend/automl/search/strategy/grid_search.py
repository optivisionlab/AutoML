import copy
import hashlib
import itertools
import logging
import time
from typing import Dict, Any, List

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.base import BaseEstimator
from sklearn.model_selection import cross_validate

from automl.search.strategy.base import SearchStrategy, normalize_param_grid

# Cấu hình logger cho module này
logger = logging.getLogger(__name__)

class GridSearchStrategy(SearchStrategy):
    """Triển khai Grid Search"""

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """Trả về cấu hình mặc định cho strategy này, đọc từ file YAML."""
        config = SearchStrategy.get_default_config()

        # Tải config từ file YAML (sử dụng method từ base class)
        yaml_config = SearchStrategy._load_yaml_config('grid_search')

        # Config với giá trị từ YAML hoặc fallback
        grid_defaults = {
            'pre_dispatch': yaml_config.get('pre_dispatch', '2*n_jobs'),
            'return_train_score': yaml_config.get('return_train_score', False),
            'parallel_evaluation': yaml_config.get('parallel_evaluation', True),
            'cache_evaluations': yaml_config.get('cache_evaluations', True),
            'batch_size': yaml_config.get('batch_size', 10),
            'auto_select_backend': yaml_config.get('auto_select_backend', True),
            # Early stopping settings
            'early_stopping_enabled': yaml_config.get('early_stopping_enabled', False),
            'early_stopping_score': yaml_config.get('early_stopping_score', None),
            'early_stopping_n_best': yaml_config.get('early_stopping_n_best', None),
            'early_stopping_no_improve': yaml_config.get('early_stopping_no_improve', None),
            # Progress tracking
            'show_progress': yaml_config.get('show_progress', True),
            'show_time_estimate': yaml_config.get('show_time_estimate', True),
        }

        config.update(grid_defaults)
        return config

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._evaluation_cache = {}  # Cache cho các tổ hợp tham số đã đánh giá
        self._model_copies = []  # Các bản sao mô hình được tạo trước cho đánh giá song song
        self._start_time = None  # Thời điểm bắt đầu search
        self._best_scores_history = []  # Lịch sử các điểm số tốt nhất

    def _select_optimal_backend(self, n_combinations: int, data_size: int) -> str:
        """
        Chọn backend tối ưu dựa trên workload.
        
        Args:
            n_combinations: Số tổ hợp tham số cần đánh giá
            data_size: Kích thước dữ liệu (số samples * số features)
            
        Returns:
            str: 'threading' hoặc 'loky'
        """
        if not self.config.get('auto_select_backend', True):
            return 'loky'  # Mặc định nếu không auto select

        # Threading tốt cho:
        # - Số lượng combinations nhỏ (overhead nhỏ)
        # - Khi cross-validation đã sử dụng multiprocessing nội bộ
        if n_combinations <= 4:
            return 'threading'

        # Loky (multiprocessing) tốt cho workload lớn
        # Tính tổng workload = data_size * n_combinations
        total_workload = data_size * n_combinations
        if total_workload > 1_000_000:
            return 'loky'

        # Threading cho các trường hợp trung bình
        return 'threading'

    def _estimate_remaining_time(self, completed: int, total: int, elapsed: float) -> str:
        """
        Ước tính thời gian còn lại.
        
        Args:
            completed: Số tổ hợp đã hoàn thành
            total: Tổng số tổ hợp
            elapsed: Thời gian đã trôi qua (giây)
            
        Returns:
            str: Chuỗi định dạng thời gian còn lại
        """
        if completed == 0:
            return "calculating..."

        avg_time_per_combo = elapsed / completed
        remaining = avg_time_per_combo * (total - completed)

        if remaining < 60:
            return f"{remaining:.0f}s"
        elif remaining < 3600:
            return f"{remaining / 60:.1f}m"
        else:
            return f"{remaining / 3600:.1f}h"

    def _check_early_stopping(self, best_score: float, batch_idx: int) -> bool:
        """
        Kiểm tra điều kiện early stopping.
        
        Args:
            best_score: Điểm số tốt nhất hiện tại
            batch_idx: Chỉ số batch hiện tại
            
        Returns:
            bool: True nếu nên dừng sớm
        """
        if not self.config.get('early_stopping_enabled', False):
            return False

        # Kiểm tra ngưỡng score
        target_score = self.config.get('early_stopping_score')
        if target_score is not None and best_score >= target_score:
            n_best = self.config.get('early_stopping_n_best', 1) or 1
            good_scores = sum(1 for s in self._best_scores_history if s >= target_score)
            if good_scores >= n_best:
                logger.info(f"Early stopping: Đạt {good_scores} kết quả với score >= {target_score}")
                return True

        # Kiểm tra không cải thiện
        no_improve_limit = self.config.get('early_stopping_no_improve')
        if no_improve_limit is not None and len(self._best_scores_history) >= no_improve_limit:
            recent_scores = self._best_scores_history[-no_improve_limit:]
            if len(set(recent_scores)) == 1:  # Không thay đổi
                logger.info(f"Early stopping: Không cải thiện sau {no_improve_limit} batches")
                return True

        return False

    def _get_params_hash(self, params: Dict[str, Any], model: BaseEstimator) -> str:
        """
        Tạo cache_key từ Hash(M.class, θ).
        
        Args:
            params: Tổ hợp tham số θ cần đánh giá
            model: Mô hình M (bao gồm cả class và cấu hình ban đầu)
            
        Returns:
            str: Hash key duy nhất cho tổ hợp (model, params)
        """
        # Lấy thông tin đầy đủ của model class (bao gồm module và tên)
        model_class_info = f"{model.__class__.__module__}.{model.__class__.__name__}"

        # Lấy các tham số hiện tại của model (cấu hình ban đầu)
        model_base_params = str(sorted(model.get_params().items()))

        # Hash từ: model class + model base params + params cần đánh giá
        params_str = str(sorted(params.items()))
        hash_input = f"{model_class_info}_{model_base_params}_{params_str}"
        return hashlib.md5(hash_input.encode()).hexdigest()

    def _evaluate_single_params(self, params: Dict[str, Any], model: BaseEstimator,
                                X: np.ndarray, y: np.ndarray, cv, scoring_config) -> Dict[str, Any]:
        """Đánh giá một tổ hợp tham số đơn lẻ sử dụng cross-validation."""
        try:
            # cache_key ← Hash(M.class, θ)
            cache_key = self._get_params_hash(params, model)

            # if cache_key ∈ cache then return cache[cache_key]
            if self.config.get('cache_evaluations', True) and cache_key in self._evaluation_cache:
                return self._evaluation_cache[cache_key].copy()

            # Thiết lập tham số
            model.set_params(**params)

            # Sử dụng cross_validate để đánh giá hiệu quả
            scores = cross_validate(
                model, X, y,
                cv=cv,
                scoring=scoring_config,
                n_jobs=1,  # Sử dụng 1 job ở đây vì chúng ta đang song song hóa ở mức cao hơn
                return_train_score=self.config.get('return_train_score', False),
                error_score='raise'
            )

            result = {
                'test_scores': scores,
                'params': params,
                'fit_time': np.mean(scores.get('fit_time', [0])),
                'score_time': np.mean(scores.get('score_time', [0]))
            }

            # Cache kết quả
            if self.config.get('cache_evaluations', True):
                self._evaluation_cache[cache_key] = result

            return result

        except Exception as e:
            # Trả về kết quả lỗi
            return {
                'test_scores': None,
                'params': params,
                'fit_time': 0,
                'score_time': 0,
                'error': str(e)
            }

    def _evaluate_params_batch(self, param_combinations: List[Dict[str, Any]], model: BaseEstimator,
                               X: np.ndarray, y: np.ndarray, cv, scoring_config) -> List[Dict[str, Any]]:
        """Đánh giá một batch các tổ hợp tham số song song với cài đặt tối ưu."""
        # Luôn sử dụng song song cho nhiều hơn 1 tổ hợp
        if len(param_combinations) > 1:
            import multiprocessing
            n_jobs = self.config.get('n_jobs', -1)
            if n_jobs == -1:
                n_jobs = multiprocessing.cpu_count()

            # Luôn sử dụng đánh giá song song
            if n_jobs > 1:
                # Tạo trước các bản sao mô hình để quản lý bộ nhớ tốt hơn
                if not self._model_copies or len(self._model_copies) < n_jobs:
                    actual_n_jobs = min(n_jobs, len(param_combinations))
                    self._model_copies = [copy.deepcopy(model) for _ in range(actual_n_jobs)]

                # Sử dụng smart backend selection
                data_size = X.shape[0] * X.shape[1] if hasattr(X, 'shape') else len(X)
                backend = self._select_optimal_backend(len(param_combinations), data_size)

                # Đánh giá song song với cài đặt tối ưu
                results = Parallel(n_jobs=n_jobs, backend=backend, batch_size='auto', prefer='threads')(
                    delayed(self._evaluate_single_params)(
                        params, self._model_copies[i % len(self._model_copies)], X, y, cv, scoring_config
                    )
                    for i, params in enumerate(param_combinations)
                )
                return results

        # Đánh giá tuần tự chỉ cho một tham số duy nhất
        return [self._evaluate_single_params(params, model, X, y, cv, scoring_config)
                for params in param_combinations]

    def _grid_search_core(self, param_grid, model_func, data, targets, cv, scoring, metric_sort, return_train_score, log_file=None):
        """Triển khai cốt lõi grid search với đánh giá song song."""
        if metric_sort not in scoring:
            raise ValueError(f"metric_sort '{metric_sort}' không có trong các metric scoring")

        # Chuẩn hóa param_grid về list-of-dicts format
        param_grid_list = normalize_param_grid(param_grid)

        # Tạo tất cả các tổ hợp tham số từ mỗi dict trong list
        all_params = []
        for single_grid in param_grid_list:
            if not single_grid:
                continue
            keys = list(single_grid.keys())
            combinations = list(itertools.product(*(single_grid[key] for key in keys)))
            all_params.extend([dict(zip(keys, combo)) for combo in combinations])

        # Kiểm tra nếu không có tổ hợp tham số nào
        if not all_params:
            logger.warning("Grid Search: Không có tổ hợp tham số nào để đánh giá. Kiểm tra lại param_grid.")
            return {}, float('-inf'), {}, {}

        logger.info(f"Grid Search: Đang đánh giá {len(all_params)} tổ hợp tham số...")

        # Tạo instance mô hình để đánh giá
        if callable(model_func):
            model = model_func()
        else:
            model = model_func

        # Khởi tạo tracking cho early stopping và progress
        self._start_time = time.time()
        self._best_scores_history = []
        best_score_so_far = float('-inf')

        # Đánh giá theo batch
        batch_size = self.config.get('batch_size', 10)
        all_results = []
        early_stopped = False
        time_limit_stopped = False

        for batch_idx, i in enumerate(range(0, len(all_params), batch_size)):
            # Kiểm tra time limit
            _, is_exceeded = self._check_time_status()
            if is_exceeded:
                logger.info(f"Đã đạt giới hạn thời gian ({self.config.get('max_time')}s). Dừng search.")
                time_limit_stopped = True
                break

            batch_params = all_params[i:i + batch_size]
            batch_results = self._evaluate_params_batch(
                batch_params, model, data, targets, cv, scoring
            )
            all_results.extend(batch_results)

            # Cập nhật best score cho early stopping
            for result in batch_results:
                if result.get('test_scores') is not None:
                    test_scores = result['test_scores']
                    metric_key = f'test_{metric_sort}'
                    if metric_key in test_scores:
                        score = np.mean(test_scores[metric_key])
                        if score > best_score_so_far:
                            best_score_so_far = score

            self._best_scores_history.append(best_score_so_far)

            # Kiểm tra early stopping
            if self._check_early_stopping(best_score_so_far, batch_idx):
                early_stopped = True
                logger.info(f"Dừng sớm sau khi đánh giá {len(all_results)}/{len(all_params)} tổ hợp")
                break

            # Hiển thị tiến trình với ước tính thời gian
            if self.config.get('show_progress', True) and self.config.get('verbose', 1) > 0:
                completed = min(i + batch_size, len(all_params))
                elapsed = time.time() - self._start_time

                progress_msg = f"Tiến trình: {completed}/{len(all_params)} tổ hợp đã đánh giá"

                if self.config.get('show_time_estimate', True) and completed < len(all_params):
                    remaining = self._estimate_remaining_time(completed, len(all_params), elapsed)
                    progress_msg += f" | Còn lại: ~{remaining}"

                progress_msg += f" | Best: {best_score_so_far:.4f}"
                logger.info(progress_msg)

        # Log tổng thời gian
        total_time = time.time() - self._start_time
        if time_limit_stopped:
            logger.info(f"Grid Search hoàn thành (time limit) trong {total_time:.2f}s")
        elif early_stopped:
            logger.info(f"Grid Search hoàn thành (early stopped) trong {total_time:.2f}s")
        else:
            logger.info(f"Grid Search hoàn thành trong {total_time:.2f}s")

        # Xử lý kết quả và xây dựng cv_results_
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

        # Thêm các key cho từng metric
        for metric in scoring.keys():
            cv_results_[f'mean_test_{metric}'] = []
            cv_results_[f'std_test_{metric}'] = []
            if return_train_score:
                cv_results_[f'mean_train_{metric}'] = []
                cv_results_[f'std_train_{metric}'] = []

        best_score = float('-inf')
        best_params = None
        best_all_scores = None

        # Xử lý tất cả kết quả
        for result in all_results:
            params = result['params']
            cv_results_['params'].append(params)

            # Xử lý trường hợp lỗi
            if result.get('test_scores') is None:
                # Đánh giá thất bại - thêm 0.0 cho tất cả metrics
                for key in cv_results_.keys():
                    if key != 'params':
                        cv_results_[key].append(0.0)
                continue

            # Trích xuất điểm số từ kết quả
            test_scores = result['test_scores']

            # Tính mean và std cho mỗi metric
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

            # Xử lý điểm train nếu được yêu cầu
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

            # Điểm số tổng thể
            cv_results_['mean_test_score'].append(average_score.get(metric_sort, 0.0))
            cv_results_['std_test_score'].append(std_score.get(metric_sort, 0.0))

            # Thông tin thời gian
            cv_results_['mean_fit_time'].append(result.get('fit_time', 0.0))
            cv_results_['std_fit_time'].append(0.0)  # Chúng ta không có std cho timing trong triển khai này
            cv_results_['mean_score_time'].append(result.get('score_time', 0.0))
            cv_results_['std_score_time'].append(0.0)

            # Theo dõi điểm số tốt nhất
            current_score = average_score.get(metric_sort, 0.0)
            if current_score > best_score:
                best_score = current_score
                best_params = params
                best_all_scores = average_score

        # Tạo xếp hạng cho mỗi metric
        for metric in scoring.keys():
            test_scores = cv_results_[f'mean_test_{metric}']
            ranks = np.argsort(np.argsort(-np.array(test_scores))) + 1
            cv_results_[f'rank_test_{metric}'] = ranks.tolist()

        # Cũng tạo xếp hạng tổng thể dựa trên metric sắp xếp
        test_scores = cv_results_[f'mean_test_{metric_sort}']
        ranks = np.argsort(np.argsort(-np.array(test_scores))) + 1
        cv_results_['rank_test_score'] = ranks.tolist()

        # Lưu kết quả vào file log nếu logging được bật
        if log_file and self.config.get('save_log', False):
            # Tạo DataFrame với kết quả tìm kiếm
            log_data = []
            for i in range(len(cv_results_['params'])):
                row = {
                    'rank': cv_results_['rank_test_score'][i],
                    'mean_test_score': cv_results_['mean_test_score'][i],
                    'std_test_score': cv_results_['std_test_score'][i]
                }
                # Thêm giá trị tham số
                row.update(cv_results_['params'][i])
                # Thêm điểm số metric
                for metric in scoring.keys():
                    row[f'mean_test_{metric}'] = cv_results_[f'mean_test_{metric}'][i]
                    row[f'std_test_{metric}'] = cv_results_[f'std_test_{metric}'][i]
                log_data.append(row)

            # Lưu vào CSV
            df = pd.DataFrame(log_data)
            df = df.sort_values('rank')
            df.to_csv(log_file, index=False)

        # Xóa cache và chuyển đổi kiểu numpy trước khi trả về
        return self._finalize_results(best_params, best_score, best_all_scores, cv_results_)

    def search(self, model: BaseEstimator, param_grid: List[Dict[str, Any]], X: np.ndarray, y: np.ndarray, **kwargs):
        """
        Thực hiện tối ưu hóa siêu tham số bằng grid search.

        Args:
            model: Bộ ước lượng (estimator) cần tối ưu hóa
            param_grid: Dictionary với tên tham số làm khóa và danh sách các giá trị tham số cần thử
            X: Dữ liệu đặc trưng huấn luyện
            y: Dữ liệu nhãn mục tiêu huấn luyện
            **kwargs: Các tham số cấu hình bổ sung

        Returns:
            tuple: (best_params, best_score, best_all_scores, cv_results)
                - best_params: Từ điển các tham số tốt nhất
                - best_score: Điểm số tốt nhất đạt được
                - best_all_scores: Từ điển với tất cả điểm số metric cho tham số tốt nhất
                - cv_results: Từ điển với kết quả cross-validation chi tiết
        """
        self.set_config(**{k: v for k, v in kwargs.items() if k in self.config})
        self._start_timer()  # Bắt đầu đếm thời gian

        # Tạo đường dẫn file log sử dụng phương thức lớp cơ sở
        log_file = self.create_log_file_path(model, 'grid_search')

        best_params, best_score, best_all_scores, cv_results = self._grid_search_core(
            param_grid=param_grid,
            model_func=model,
            data=X,
            targets=y,
            cv=self.config['cv'],
            scoring=self.config['scoring'],
            metric_sort=self.config['metric_sort'],

            return_train_score=self.config.get('return_train_score', False),
            log_file=log_file
        )

        # Ghi log thông báo hoàn thành nếu logging được bật
        if self.config.get('save_log', False) and log_file:
            logger.info(f"Log grid search đã lưu vào: {log_file}")

        return best_params, best_score, best_all_scores, cv_results
