from typing import Dict, Any, List
import itertools
import copy
import hashlib

import logging
import pandas as pd

import numpy as np
from sklearn.base import BaseEstimator
from sklearn.model_selection import cross_validate
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from joblib import Parallel, delayed

from automl.search.strategy.base import SearchStrategy


# Cấu hình logger cho module này
logger = logging.getLogger(__name__)

class GridSearchStrategy(SearchStrategy):
    """Triển khai Grid Search"""

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """Trả về cấu hình mặc định cho strategy này"""
        config = SearchStrategy.get_default_config()
        config.update({
            'pre_dispatch': '2*n_jobs',
            'return_train_score': False,
            'parallel_evaluation': True,  # Bật đánh giá song song
            'cache_evaluations': True,  # Cache kết quả đánh giá
            'batch_size': 10,  # Kích thước batch cho xử lý song song
        })

        return config
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._evaluation_cache = {}  # Cache cho các tổ hợp tham số đã đánh giá
        self._model_copies = []  # Các bản sao mô hình được tạo trước cho đánh giá song song
    
    def _get_params_hash(self, params: Dict[str, Any], model_class: str) -> str:
        """Tạo hash để cache các tổ hợp tham số."""
        params_str = str(sorted(params.items()))
        hash_input = f"{model_class}_{params_str}"
        return hashlib.md5(hash_input.encode()).hexdigest()
    
    def _evaluate_single_params(self, params: Dict[str, Any], model: BaseEstimator, 
                               X: np.ndarray, y: np.ndarray, cv, scoring_config) -> Dict[str, Any]:
        """Đánh giá một tổ hợp tham số đơn lẻ sử dụng cross-validation."""
        try:
            # Kiểm tra cache trước
            cache_key = self._get_params_hash(params, model.__class__.__name__)
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
                
                # Chọn backend dựa trên kích thước dữ liệu và số lượng tổ hợp
                # Sử dụng threading cho khối lượng công việc nhỏ, loky cho khối lượng lớn hơn
                backend = 'threading' if len(param_combinations) <= 8 else 'loky'
                
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
        # Chuyển đổi scoring sang định dạng tương thích với cross_validate nếu cần
        if scoring is None:
            from sklearn.metrics import make_scorer
            scoring = {
                'accuracy': make_scorer(accuracy_score),
                'precision': make_scorer(precision_score, average='macro', zero_division=0),
                'recall': make_scorer(recall_score, average='macro', zero_division=0),
                'f1': make_scorer(f1_score, average='macro', zero_division=0)
            }
        
        # Đảm bảo scoring ở định dạng phù hợp cho cross_validate
        if not isinstance(scoring, dict):
            scoring = {'score': scoring}
            metric_sort = 'score'

        if metric_sort not in scoring:
            raise ValueError(f"metric_sort '{metric_sort}' không có trong các metric scoring")

        # Tạo tất cả các tổ hợp tham số
        keys = list(param_grid.keys())
        combinations = list(itertools.product(*(param_grid[key] for key in keys)))
        all_params = [dict(zip(keys, combo)) for combo in combinations]
        
        logger.info(f"Grid Search: Đang đánh giá {len(all_params)} tổ hợp tham số...")
        
        # Tạo instance mô hình để đánh giá
        if callable(model_func):
            model = model_func()
        else:
            model = model_func
        
        # Đánh giá theo batch
        batch_size = self.config.get('batch_size', 10)
        all_results = []
        
        for i in range(0, len(all_params), batch_size):
            batch_params = all_params[i:i+batch_size]
            batch_results = self._evaluate_params_batch(
                batch_params, model, data, targets, cv, scoring
            )
            all_results.extend(batch_results)
            
            # Hiển thị tiến trình
            if self.config.get('verbose', 1) > 0:
                logger.info(f"Tiến trình: {min(i+batch_size, len(all_params))}/{len(all_params)} tổ hợp đã đánh giá")
        
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

    def search(self, model: BaseEstimator, param_grid: Dict[str, Any], X: np.ndarray, y: np.ndarray, **kwargs):
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