from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional
from sklearn.base import BaseEstimator
import numpy as np
import logging

import os
from datetime import datetime
from sklearn.model_selection import StratifiedKFold

# Cấu hình logger cho module này
logger = logging.getLogger(__name__)


class SearchStrategy(ABC):
    """Base class for all search strategies."""

    def __init__(self, **kwargs):
        self.config = self.get_default_config()
        self.config.update(kwargs)

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        """Trả về cấu hình mặc định cho strategy này"""
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
        """Thực thi thuật toán tìm kiếm.

        Returns:
            tuple: (best_params, best_score, cv_results)
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
