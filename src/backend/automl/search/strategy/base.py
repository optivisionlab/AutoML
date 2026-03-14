import logging
import os
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any, Tuple, Optional, List, Union

import numpy as np
import yaml
from sklearn.base import BaseEstimator
from sklearn.model_selection import StratifiedKFold

# Cấu hình logger cho module này
logger = logging.getLogger(__name__)


def normalize_param_grid(param_grid: Union[Dict, List[Dict], None]) -> List[Dict]:
    """
    Chuẩn hóa param_grid về định dạng list-of-dicts.
    
    Args:
        param_grid: dict đơn lẻ, list of dicts, hoặc None
        
    Returns:
        List of parameter dictionaries
        
    Raises:
        ValueError: Nếu định dạng không hợp lệ
    """
    if param_grid is None:
        return [{}]

    if isinstance(param_grid, dict):
        return [param_grid]

    if isinstance(param_grid, list):
        if len(param_grid) == 0:
            return [{}]
        if all(isinstance(d, dict) for d in param_grid):
            return param_grid
        raise ValueError(f"param_grid list chứa phần tử không phải dict")

    raise ValueError(f"param_grid phải là dict hoặc list of dicts, nhận được {type(param_grid)}")

class SearchStrategy(ABC):
    """Base class for all search strategies."""

    def __init__(self, **kwargs):
        self.config = self.get_default_config()
        self.config.update(kwargs)
        self._search_start_time = None
        self._time_limit_reached = False

    # ==========================================================================
    # Timer Utilities cho Time Limit
    # ==========================================================================

    def _start_timer(self):
        """
        Bắt đầu đếm thời gian cho search.
        Gọi method này ở đầu hàm search.
        """
        self._search_start_time = time.time()
        self._time_limit_reached = False
        self._iteration_time_ema = None  # Reset EMA cho mỗi lần search mới

        max_time = self.config.get('max_time')
        if max_time is not None and self.config.get('verbose', 0) > 0:
            logger.info(f"Time limit: {max_time} giây")

    def _check_time_status(self) -> Tuple[Optional[float], bool]:
        """
        Kiểm tra trạng thái thời gian của quá trình search.
        
        Returns:
            Tuple[Optional[float], bool]: 
                - remaining_time: Thời gian còn lại (giây), None nếu không có time limit
                - is_exceeded: True nếu đã vượt quá time limit, False nếu chưa
        """
        max_time = self.config.get('max_time')
        
        # Nếu không có time limit
        if max_time is None:
            return None, False
            
        # Tính thời gian đã trôi qua
        elapsed = 0.0 if self._search_start_time is None else time.time() - self._search_start_time
        remaining = max(0.0, max_time - elapsed)
        
        # Kiểm tra đã vượt quá chưa
        is_exceeded = elapsed >= max_time
        if is_exceeded:
            self._time_limit_reached = True
            
        return remaining, is_exceeded

    def _should_start_next_iteration(self, iteration_duration: float = None) -> bool:
        """
        Kiểm tra xem có nên bắt đầu iteration tiếp theo không, dựa trên 
        thời gian còn lại và ước tính thời gian mỗi iteration.
        
        Phương thức này sử dụng EMA (exponential moving average) để ước tính
        thời gian cho iteration tiếp theo. Nếu thời gian ước tính vượt quá 
        thời gian còn lại, trả về False để dừng sớm (proactive stop).
        
        Args:
            iteration_duration: Thời gian iteration vừa hoàn thành (giây).
                              Nếu None, chỉ kiểm tra time exceeded.
        
        Returns:
            bool: True nếu nên tiếp tục, False nếu nên dừng.
        """
        remaining_time, is_exceeded = self._check_time_status()
        
        # Đã vượt quá time limit
        if is_exceeded:
            return False
        
        # Không có time limit
        if remaining_time is None:
            return True
        
        # Cập nhật EMA nếu có iteration_duration
        if iteration_duration is not None:
            if not hasattr(self, '_iteration_time_ema') or self._iteration_time_ema is None:
                self._iteration_time_ema = iteration_duration
            else:
                # EMA: 70% giá trị mới, 30% giá trị cũ
                self._iteration_time_ema = 0.7 * iteration_duration + 0.3 * self._iteration_time_ema
        
        # Kiểm tra proactive: ước tính iteration tiếp theo có vượt quá không
        if hasattr(self, '_iteration_time_ema') and self._iteration_time_ema is not None:
            # Nhân 1.2x safety factor (iteration tiếp có thể chậm hơn)
            estimated_next = self._iteration_time_ema * 1.2
            if estimated_next > remaining_time:
                logger.info(
                    f"Dừng proactive: ước tính iteration tiếp ~{estimated_next:.1f}s "
                    f"nhưng chỉ còn {remaining_time:.1f}s"
                )
                self._time_limit_reached = True
                return False
        
        return True

    def _should_apply_early_stopping(self) -> bool:
        """
        Xác định có nên áp dụng early stopping hay không.
        
        Logic:
        - Nếu max_time được set: KHÔNG áp dụng early stopping (ưu tiên time)  
        - Nếu không có max_time: Áp dụng early stopping theo cấu hình
        
        Returns:
            bool: True nếu nên áp dụng early stopping, False nếu không
        """
        max_time = self.config.get('max_time')
        
        # Nếu có time limit, không áp dụng early stopping
        if max_time is not None:
            return False
        
        # Không có time limit, áp dụng early stopping theo config    
        return True

    @staticmethod
    def _load_yaml_config(config_name: str) -> Dict[str, Any]:
        """
        Tải cấu hình từ file YAML. Nếu không tìm thấy file config chính,
        sẽ load file default config.
        
        Args:
            config_name: Tên config (vd: 'base', 'grid_search', 'bayesian_search')
            
        Returns:
            Dict chứa cấu hình từ file YAML
        """
        current_dir = os.path.dirname(os.path.abspath(__file__))
        config_file = os.path.join(current_dir, f'{config_name}_config.yml')
        default_config_file = os.path.join(current_dir, f'{config_name}_default_config.yml')

        loaded_config = {}

        # Thử load file config chính trước
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    loaded_config = yaml.safe_load(f) or {}
                    if loaded_config:
                        return loaded_config
            except Exception as e:
                logger.warning(f"Không thể tải cấu hình từ {config_file}: {e}")

        # Nếu không có file config chính hoặc file trống, load file default
        if os.path.exists(default_config_file):
            try:
                with open(default_config_file, 'r', encoding='utf-8') as f:
                    loaded_config = yaml.safe_load(f) or {}
                    if loaded_config:
                        logger.info(f"Đã tải cấu hình mặc định từ {default_config_file}")
                        return loaded_config
            except Exception as e:
                logger.warning(f"Không thể tải cấu hình mặc định từ {default_config_file}: {e}")

        return loaded_config

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """Trả về cấu hình mặc định cho strategy này, đọc từ file YAML."""
        # Tải config từ file YAML
        yaml_config = SearchStrategy._load_yaml_config('base')

        # Tạo StratifiedKFold từ config
        cv_n_splits = yaml_config.get('cv_n_splits', 5)
        cv_shuffle = yaml_config.get('cv_shuffle', True)
        cv_random_state = yaml_config.get('cv_random_state', 42)
        cv = StratifiedKFold(n_splits=cv_n_splits, shuffle=cv_shuffle, random_state=cv_random_state)

        # Config mặc định (fallback nếu YAML không có)
        config = {
            'cv': cv,
            'scoring': None,
            'metric_sort': yaml_config.get('metric_sort', 'accuracy'),
            'n_jobs': yaml_config.get('n_jobs', -1),
            'verbose': yaml_config.get('verbose', 0),
            'random_state': yaml_config.get('random_state'),
            'error_score': yaml_config.get('error_score', 'raise'),
            'log_dir': yaml_config.get('log_dir', 'logs'),
            'save_log': yaml_config.get('save_log', False),
            'max_time': yaml_config.get('max_time', None)
        }

        return config

    @abstractmethod
    def search(self, model: BaseEstimator, param_grid: List[Dict[str, Any]], X: np.ndarray, y: np.ndarray, **kwargs):
        """Thực thi thuật toán tìm kiếm.
        
        Args:
            model: Mô hình scikit-learn cần tối ưu hóa
            param_grid: List of dicts, mỗi dict chứa các tham số cần tìm kiếm.
                        Ví dụ: [{'kernel': ['rbf'], 'C': [1, 10]}, {'kernel': ['linear'], 'C': [1, 10]}]
            X: Dữ liệu features
            y: Dữ liệu target
            **kwargs: Các tham số bổ sung

        Returns:
            tuple: (best_params, best_score, best_all_scores, cv_results)
        """
        pass

    def set_config(self, **kwargs):
        """Cập nhật cấu hình"""
        self.config.update(kwargs)
        return self

    def create_log_file_path(self, model: BaseEstimator, strategy_name: str = None) -> Optional[str]:
        """Tạo đường dẫn file log để lưu kết quả tìm kiếm.
        
        Phương thức này tạo đường dẫn file log chuẩn hóa dựa trên cấu hình.
        Nó đảm bảo thư mục log tồn tại và tạo tên file có timestamp.
        
        Args:
            model: Mô hình đang được sử dụng cho tìm kiếm
            strategy_name: Tên tùy chọn cho strategy (mặc định là tên class)
            
        Returns:
            str: Đường dẫn đến file log nếu save_log là True, None nếu ngược lại
        """
        if not self.config.get('save_log', False):
            return None

        log_dir = self.config.get('log_dir', 'logs')
        os.makedirs(log_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_name = model.__class__.__name__

        # Sử dụng tên strategy được cung cấp hoặc tạo từ tên class
        if strategy_name is None:
            # Chuyển đổi tên class từ CamelCase sang snake_case
            class_name = self.__class__.__name__
            # Loại bỏ hậu tố 'Strategy' nếu có
            if class_name.endswith('Strategy'):
                class_name = class_name[:-8]
            if class_name.endswith('SearchStrategy'):
                class_name = class_name[:-14]
            # Chuyển đổi sang snake_case
            import re
            strategy_name = re.sub(r'(?<!^)(?=[A-Z])', '_', class_name).lower()

        log_file = os.path.join(log_dir, f'{strategy_name}_{model_name}_{timestamp}.csv')
        return log_file

    @staticmethod
    def convert_numpy_types(obj: Any) -> Any:
        """Chuyển đổi kiểu numpy sang kiểu Python gốc một cách đệ quy.
        
        Điều này quan trọng cho JSON serialization và tránh 
        lỗi kiểu không thể hash.
        
        Args:
            obj: Đối tượng cần chuyển đổi (có thể là dict, list, scalar, v.v.)
            
        Returns:
            Đối tượng với tất cả kiểu numpy đã được chuyển đổi sang kiểu Python gốc
        """
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif hasattr(obj, 'item'):
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
        """Xóa cache và chuyển đổi kiểu numpy trước khi trả về kết quả.
        
        Phương thức này nên được gọi ở cuối phương thức search để:
        1. Xóa tất cả cache để giải phóng bộ nhớ
        2. Chuyển đổi kiểu numpy sang kiểu Python gốc để serialization
        
        Args:
            best_params: Tham số tốt nhất tìm được
            best_score: Điểm số tốt nhất đạt được
            best_all_scores: Tất cả điểm số metric cho tham số tốt nhất
            cv_results: Kết quả cross-validation chi tiết
            
        Returns:
            tuple: (best_params, best_score, best_all_scores, cv_results) với tất cả kiểu numpy đã chuyển đổi
        """
        # Xóa cache sau khi tìm kiếm hoàn thành
        if hasattr(self, '_decode_cache'):
            self._decode_cache.clear()
        if hasattr(self, '_evaluation_cache'):
            self._evaluation_cache.clear()
        if hasattr(self, '_model_copies'):
            self._model_copies.clear()

        # Chuyển đổi tất cả kiểu numpy sang kiểu Python gốc
        best_params = self.convert_numpy_types(best_params)
        best_score = self.convert_numpy_types(best_score)
        best_all_scores = self.convert_numpy_types(best_all_scores)
        cv_results = self.convert_numpy_types(cv_results)

        return best_params, best_score, best_all_scores, cv_results

    def _init_search_log(self):
        """Khởi tạo danh sách log cho quá trình tìm kiếm."""
        self._search_log = []

    def _log_evaluation(self, model_name: str, strategy_name: str,
                        params: Dict[str, Any], scores: Dict[str, float],
                        iteration: int = None, total: int = None):
        """Ghi log kết quả đánh giá một tổ hợp tham số ra console và lưu vào danh sách."""
        if not hasattr(self, '_search_log'):
            self._search_log = []

        record = {
            'model': model_name,
            'run_type': strategy_name,
            'best_params': str(params),
        }
        record.update(scores)
        self._search_log.append(record)

        if self.config.get('verbose', 0) > 0:
            progress = f"[{iteration}/{total}] " if iteration is not None and total is not None else ""
            scores_str = ", ".join([f"{k}={v:.4f}" for k, v in scores.items()])
            logger.info(f"{progress}{model_name} | {strategy_name} | {params} | {scores_str}")

    def _save_search_log(self, log_file: Optional[str], silent: bool = False):
        """Lưu log tìm kiếm vào file CSV theo format chuẩn."""
        if not log_file or not hasattr(self, '_search_log') or not self._search_log:
            return

        import pandas as pd
        df = pd.DataFrame(self._search_log)
        df.to_csv(log_file, index=False)
        if not silent:
            logger.info(f"Log tìm kiếm đã lưu vào: {log_file}")
