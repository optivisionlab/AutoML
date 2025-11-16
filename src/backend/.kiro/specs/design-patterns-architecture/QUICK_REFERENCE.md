# Quick Reference - Design Patterns trong HAutoML

## 🎯 Cheat Sheet

### Cấu Trúc File

```
automl/
├── search/
│   ├── factory/
│   │   └── search_strategy_factory.py    # Factory tạo strategies
│   └── strategy/
│       ├── search_strategy.py            # Interface chung
│       ├── grid_search_strategy.py       # Grid Search
│       ├── genetic_algorithm.py          # Genetic Algorithm
│       └── bayesian_search_strategy.py   # Bayesian Search
└── engine.py                             # Training engine sử dụng Factory
```

### Luồng Hoạt Động (1 Phút)

```
1. User gửi config với search_algorithm: 'genetic'
2. Factory.create_strategy('genetic') → GeneticAlgorithm instance
3. Engine gọi strategy.search(model, params, X, y)
4. Strategy tìm best_params và trả về
5. Engine lưu kết quả vào MongoDB
```

### Code Snippets Quan Trọng

#### Tạo Strategy

```python
from automl.search.factory import SearchStrategyFactory

# Tạo strategy từ config
strategy = SearchStrategyFactory.create_strategy('genetic')

# Sử dụng strategy
result = strategy.search(
    model=DecisionTreeClassifier(),
    param_grid={'max_depth': [3, 5, 7]},
    X=X_train,
    y=y_train,
    cv=5,
    scoring='accuracy'
)

print(result['best_params'])  # {'max_depth': 5}
print(result['best_score'])   # 0.95
```

#### Thêm Strategy Mới (3 Bước)

```python
# 1. Tạo class
class RandomSearchStrategy(SearchStrategy):
    def search(self, model, param_grid, X, y, cv=5, scoring='accuracy'):
        # Implementation
        pass

# 2. Đăng ký
SearchStrategyFactory._strategies['random'] = RandomSearchStrategy
SearchStrategyFactory._aliases['rs'] = 'random'

# 3. Sử dụng
strategy = SearchStrategyFactory.create_strategy('random')
```

## 📋 Aliases Được Hỗ Trợ

| Canonical Name | Aliases | Class |
|----------------|---------|-------|
| `grid` | `gridsearch`, `Grid`, `GridSearch` | GridSearchStrategy |
| `genetic` | `ga`, `GA`, `GeneticAlgorithm` | GeneticAlgorithm |
| `bayesian` | `bayes`, `skopt`, `BayesianOptimization` | BayesianSearchStrategy |

## 🔧 Config Examples

### Grid Search (Toàn Diện)

```yaml
choose: "new model"
list_feature: ["sepal_length", "sepal_width", "petal_length", "petal_width"]
target: "species"
metric_sort: "accuracy"
search_algorithm: grid  # Mặc định
```

### Genetic Algorithm (Nhanh)

```yaml
choose: "new model"
list_feature: ["sepal_length", "sepal_width", "petal_length", "petal_width"]
target: "species"
metric_sort: "accuracy"
search_algorithm: genetic  # hoặc 'ga'
```

### Bayesian Search (Cân Bằng)

```yaml
choose: "new model"
list_feature: ["sepal_length", "sepal_width", "petal_length", "petal_width"]
target: "species"
metric_sort: "accuracy"
search_algorithm: bayesian  # hoặc 'skopt'
```

## 🎨 Sơ Đồ Nhanh

### Factory Pattern

```
┌──────────────────────┐
│  Client Code         │
│  (Training Engine)   │
└──────────┬───────────┘
           │ create_strategy('genetic')
           ▼
┌──────────────────────┐
│ SearchStrategyFactory│
│  - _strategies dict  │
│  - _aliases dict     │
└──────────┬───────────┘
           │ returns
           ▼
┌──────────────────────┐
│ GeneticAlgorithm     │
│ (SearchStrategy)     │
└──────────────────────┘
```

### Strategy Pattern

```
┌─────────────────────────────────────┐
│      SearchStrategy (Interface)     │
│  + search(model, params, X, y)      │
└─────────────────────────────────────┘
           ▲
           │ implements
    ┌──────┼──────┐
    │      │      │
┌───┴──┐ ┌─┴───┐ ┌┴─────┐
│ Grid │ │ GA  │ │Bayes │
└──────┘ └─────┘ └──────┘
```

## 🚨 Common Pitfalls

### ❌ Sai

```python
# Tạo strategy trực tiếp
strategy = GeneticAlgorithm()  # Tight coupling!
```

### ✅ Đúng

```python
# Sử dụng Factory
strategy = SearchStrategyFactory.create_strategy('genetic')
```

### ❌ Sai

```python
# Kiểm tra type cụ thể
if isinstance(strategy, GeneticAlgorithm):
    # Do something
```

### ✅ Đúng

```python
# Sử dụng interface chung
result = strategy.search(model, params, X, y)
```

## 🔍 Debugging Tips

### Kiểm Tra Strategy Được Tạo

```python
strategy = SearchStrategyFactory.create_strategy('ga')
print(type(strategy).__name__)  # GeneticAlgorithm
```

### Xem Aliases Được Hỗ Trợ

```python
print(SearchStrategyFactory._aliases)
# {'gridsearch': 'grid', 'ga': 'genetic', ...}
```

### Test Strategy

```python
from sklearn.datasets import load_iris
from sklearn.tree import DecisionTreeClassifier

X, y = load_iris(return_X_y=True)
model = DecisionTreeClassifier()
param_grid = {'max_depth': [3, 5, 7]}

strategy = SearchStrategyFactory.create_strategy('grid')
result = strategy.search(model, param_grid, X, y)

assert 'best_params' in result
assert 'best_score' in result
```

## 📊 Performance Tips

### Chọn Thuật Toán

```python
# Không gian nhỏ (<100 combinations)
strategy = SearchStrategyFactory.create_strategy('grid')

# Không gian lớn (>1000 combinations)
strategy = SearchStrategyFactory.create_strategy('genetic')

# Cân bằng tốc độ/chất lượng
strategy = SearchStrategyFactory.create_strategy('bayesian')
```

### Tối Ưu Hóa

```python
# Parallel execution (tất cả strategies hỗ trợ)
# Được set trong implementation: n_jobs=-1

# Custom GA parameters
class FastGA(GeneticAlgorithm):
    def __init__(self):
        super().__init__(population_size=10, generations=5)

SearchStrategyFactory._strategies['fast_ga'] = FastGA
```

## 🔗 Liên Kết Nhanh

- [Design Document Đầy Đủ](design.md)
- [Requirements](requirements.md)
- [README](README.md)

## 💡 Tips

1. **Luôn sử dụng Factory** thay vì tạo Strategy trực tiếp
2. **Sử dụng aliases** để code dễ đọc hơn ('ga' thay vì 'GeneticAlgorithm')
3. **Test với Grid Search trước** để có baseline
4. **Chuyển sang GA hoặc Bayesian** khi không gian tham số lớn
5. **Thêm logging** để debug quá trình tìm kiếm

---

**Cập nhật lần cuối**: 2025-11-15
