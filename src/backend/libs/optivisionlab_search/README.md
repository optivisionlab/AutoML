# optivisionlab-search

Thư viện tối ưu hóa siêu tham số (Hyperparameter Optimization) cho AutoML.

## Các thuật toán hỗ trợ

- **Grid Search** — Tìm kiếm toàn diện trên lưới tham số
- **Bayesian Optimization** — Tối ưu hóa Bayesian sử dụng Gaussian Process
- **Genetic Algorithm** — Thuật toán di truyền với adaptive operators

## Cài đặt

```bash
# Cài đặt từ source (editable mode)
pip install -e ./libs/optivisionlab_search

# Cài đặt với dev dependencies
pip install -e "./libs/optivisionlab_search[dev]"
```

## Sử dụng nhanh

```python
from optivisionlab_search import SearchStrategyFactory

# Tạo strategy qua factory
strategy = SearchStrategyFactory.create_strategy('grid_search', {
    'cv': 5,
    'scoring': scoring_dict,
    'metric_sort': 'accuracy',
})

# Chạy tối ưu hóa
best_params, best_score, best_all_scores, cv_results, time_limit_reached = strategy.search(
    model=model,
    param_grid=param_grid,
    X=X_train,
    y=y_train,
)
```

## Import trực tiếp

```python
from optivisionlab_search import (
    SearchStrategy,           # Base class (ABC)
    GridSearchStrategy,       # Grid Search
    BayesianSearchStrategy,   # Bayesian Optimization
    GeneticAlgorithm,         # Genetic Algorithm
    SearchStrategyFactory,    # Factory Pattern
    normalize_param_grid,     # Utility function
)
```

## Cấu hình

Mỗi strategy có file config YAML mặc định đi kèm. Có thể override bằng cách:

1. Truyền kwargs khi tạo strategy:
   ```python
   strategy = SearchStrategyFactory.create_strategy('grid_search', {
       'batch_size': 20,
       'parallel_evaluation': True,
   })
   ```

2. Gọi `set_config()` sau khi tạo:
   ```python
   strategy.set_config(batch_size=20)
   ```
