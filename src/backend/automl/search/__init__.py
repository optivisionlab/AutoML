from .base import SearchStrategy
from .factory import SearchStrategyFactory
from .strategies.grid_search import GridSearchStrategy
# from .strategies

# Đăng ký strategy mặc định
SearchStrategyFactory.register_strategy('grid', GridSearchStrategy)
# SearchStrategyFactory.register_strategy('random', RandomSearchStrategy)

# Auto-discover thêm các strategy trong thư mục strategies/future
SearchStrategyFactory.auto_discover(__name__ + ".strategies.future")

# Export các thành phần chính
__all__ = ['SearchStrategy', 'SearchStrategyFactory']