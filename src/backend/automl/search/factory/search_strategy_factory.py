"""
Triển khai Factory Pattern cho Search Strategy
Module này cung cấp factory để tạo các instance của search strategy khác nhau.
"""

from typing import Dict, Any, Optional
from automl.search.strategy.base import SearchStrategy
from automl.search.strategy.grid_search import GridSearchStrategy
from automl.search.strategy.genetic_algorithm import GeneticAlgorithm
from automl.search.strategy.bayesian_search import BayesianSearchStrategy


class SearchStrategyFactory:
    """Lớp Factory để tạo các instance của search strategy."""
    
    # Registry của các search strategy có sẵn
    _strategies = {
        'grid_search': GridSearchStrategy,
        'genetic_algorithm': GeneticAlgorithm,
        'bayesian_search': BayesianSearchStrategy
    }
    
    @classmethod
    def create_strategy(cls, strategy_name: str, config: Optional[Dict[str, Any]] = None) -> SearchStrategy:
        """
        Tạo một instance search strategy dựa trên tên strategy.
        
        Args:
            strategy_name: Tên của search strategy (ví dụ: 'grid', 'genetic', 'bayesian')
            config: Từ điển cấu hình tùy chọn cho strategy
            
        Returns:
            SearchStrategy: Một instance của search strategy được yêu cầu
            
        Raises:
            ValueError: Nếu tên strategy không được nhận diện
        """
        # Chuẩn hóa tên strategy thành chữ thường
        strategy_name = strategy_name.lower().strip()
        
        # Xác định lớp strategy sử dụng pattern matching startswith
        strategy_class = None
        
        if strategy_name.startswith('grid'):
            strategy_class = GridSearchStrategy
        elif strategy_name.startswith('genetic') or strategy_name.startswith('ga'):
            strategy_class = GeneticAlgorithm
        elif strategy_name.startswith('bayesian') or strategy_name.startswith('bayes') or strategy_name.startswith('skopt'):
            strategy_class = BayesianSearchStrategy
        else:
            raise ValueError(
                f"Search strategy không xác định: '{strategy_name}'. "
                f"Các strategy có sẵn: grid*, genetic*/ga*, bayesian*/bayes*/skopt*"
            )
        
        # Tạo và trả về instance strategy
        if config:
            return strategy_class(**config)
        else:
            return strategy_class()
    
    @classmethod
    def get_available_strategies(cls) -> list:
        """
        Lấy danh sách tất cả các pattern strategy có sẵn.
        
        Returns:
            Danh sách các pattern tên strategy
        """
        return ['grid*', 'genetic*/ga*', 'bayesian*/bayes*/skopt*']
    
    @classmethod
    def is_strategy_available(cls, strategy_name: str) -> bool:
        """
        Kiểm tra xem một strategy có sẵn trong factory hay không.
        
        Args:
            strategy_name: Tên của strategy cần kiểm tra
            
        Returns:
            bool: True nếu strategy có sẵn, False nếu ngược lại
        """
        strategy_name = strategy_name.lower().strip()
        return (
            strategy_name.startswith('grid') or
            strategy_name.startswith('genetic') or
            strategy_name.startswith('ga') or
            strategy_name.startswith('bayesian') or
            strategy_name.startswith('bayes') or
            strategy_name.startswith('skopt')
        )
