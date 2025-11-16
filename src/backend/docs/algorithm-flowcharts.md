# Lưu Đồ Thuật Toán Tìm Kiếm Siêu Tham Số

## Mục Lục

- [Giới Thiệu](#giới-thiệu)
- [Grid Search](#grid-search)
  - [Lưu Đồ Thuật Toán](#lưu-đồ-thuật-toán-grid-search)
  - [Giải Thích Chi Tiết](#giải-thích-chi-tiết-grid-search)
  - [Tối Ưu Hóa](#tối-ưu-hóa-grid-search)
- [Genetic Algorithm](#genetic-algorithm)
  - [Lưu Đồ Thuật Toán](#lưu-đồ-thuật-toán-genetic-algorithm)
  - [Encoding/Decoding](#encodingdecoding)
  - [Các Operators](#các-operators)
  - [Elitism và Diversity](#elitism-và-diversity)
  - [Early Stopping](#early-stopping-genetic-algorithm)
- [Bayesian Search](#bayesian-search)
  - [Lưu Đồ Thuật Toán](#lưu-đồ-thuật-toán-bayesian-search)
  - [Gaussian Process](#gaussian-process)
  - [Acquisition Functions](#acquisition-functions)
  - [Class Imbalance Detection](#class-imbalance-detection)
  - [Early Stopping](#early-stopping-bayesian-search)
- [So Sánh Các Thuật Toán](#so-sánh-các-thuật-toán)
  - [Bảng So Sánh](#bảng-so-sánh)
  - [Hướng Dẫn Lựa Chọn](#hướng-dẫn-lựa-chọn)
  - [Ví Dụ Use Cases](#ví-dụ-use-cases)
- [Phụ Lục](#phụ-lục)
  - [Glossary](#glossary)
  - [References](#references)
  - [FAQ](#faq)

---

## Giới Thiệu

Tài liệu này mô tả chi tiết ba thuật toán tìm kiếm siêu tham số (hyperparameter search) được sử dụng trong hệ thống HAutoML:

1. **Grid Search** - Tìm kiếm toàn diện trên lưới tham số
2. **Genetic Algorithm** - Tìm kiếm dựa trên thuật toán di truyền
3. **Bayesian Search** - Tìm kiếm thông minh sử dụng Bayesian Optimization

Mỗi thuật toán có ưu và nhược điểm riêng, phù hợp với các tình huống khác nhau. Tài liệu này sẽ giúp bạn hiểu rõ cách hoạt động của từng thuật toán và lựa chọn phương pháp phù hợp nhất cho bài toán của mình.

### Tại Sao Cần Tìm Kiếm Siêu Tham Số?

Siêu tham số (hyperparameters) là các tham số không được học từ dữ liệu mà phải được thiết lập trước khi huấn luyện mô hình. Ví dụ:
- Số lượng cây trong Random Forest (`n_estimators`)
- Độ sâu tối đa của cây (`max_depth`)
- Learning rate trong Gradient Boosting
- Tham số regularization `C` trong SVM

Việc chọn đúng siêu tham số có thể cải thiện đáng kể hiệu suất mô hình. Tuy nhiên, việc thử thủ công từng tổ hợp tham số rất tốn thời gian và không hiệu quả. Đó là lý do chúng ta cần các thuật toán tự động tìm kiếm siêu tham số tối ưu.

### Cách Sử Dụng Tài Liệu Này

- **Nếu bạn là developer**: Đọc phần lưu đồ và giải thích chi tiết để hiểu implementation
- **Nếu bạn là data scientist**: Tập trung vào phần so sánh và hướng dẫn lựa chọn
- **Nếu bạn mới bắt đầu**: Đọc từ đầu đến cuối, bắt đầu với Grid Search (đơn giản nhất)

[⬆️ Về đầu trang](#mục-lục)

---

## Grid Search

Grid Search là phương pháp tìm kiếm đơn giản và toàn diện nhất. Thuật toán này thử tất cả các tổ hợp có thể của siêu tham số trong một "lưới" (grid) được định nghĩa trước.

### Lưu Đồ Thuật Toán Grid Search

```mermaid
flowchart TD
    Start([Bắt Đầu Grid Search]) --> Init[Khởi tạo cấu hình<br/>cv, scoring, n_jobs]
    Init --> Encode[Chuyển đổi param_grid<br/>thành danh sách tham số]
    Encode --> Generate[Tạo tất cả tổ hợp tham số<br/>itertools.product]
    
    Generate --> CheckCache{Cache<br/>enabled?}
    CheckCache -->|Yes| InitCache[Khởi tạo evaluation cache]
    CheckCache -->|No| Batch
    InitCache --> Batch
    
    Batch[Chia thành batches<br/>batch_size=10]
    Batch --> ParallelCheck{Parallel<br/>enabled?}
    
    ParallelCheck -->|Yes| ParallelEval[Đánh giá song song<br/>Parallel/Joblib]
    ParallelCheck -->|No| SeqEval[Đánh giá tuần tự]
    
    ParallelEval --> EvalBatch[Đánh giá từng batch]
    SeqEval --> EvalBatch
    
    EvalBatch --> CVCheck{Kiểm tra<br/>cache?}
    CVCheck -->|Hit| UseCache[Sử dụng kết quả cache]
    CVCheck -->|Miss| CrossVal[Cross-validation<br/>cross_validate]
    
    UseCache --> CalcMetrics
    CrossVal --> CalcMetrics[Tính toán metrics<br/>accuracy, precision, recall, f1]
    
    CalcMetrics --> StoreCache{Cache<br/>enabled?}
    StoreCache -->|Yes| SaveCache[Lưu vào cache]
    StoreCache -->|No| UpdateBest
    SaveCache --> UpdateBest
    
    UpdateBest[Cập nhật best_score<br/>và best_params]
    UpdateBest --> MoreBatch{Còn batch?}
    
    MoreBatch -->|Yes| Batch
    MoreBatch -->|No| BuildResults[Xây dựng cv_results_<br/>với tất cả metrics]
    
    BuildResults --> Rank[Tính toán rankings<br/>cho mỗi metric]
    Rank --> Convert[Convert numpy types<br/>sang Python native]
    
    Convert --> SaveLog{save_log<br/>enabled?}
    SaveLog -->|Yes| WriteLog[Ghi log ra CSV]
    SaveLog -->|No| Return
    WriteLog --> Return
    
    Return([Trả về best_params,<br/>best_score, best_all_scores,<br/>cv_results_])
    
    style Start fill:#e1f5e1
    style Return fill:#e1f5e1
    style ParallelEval fill:#fff4e1
    style CrossVal fill:#e1f0ff
    style UseCache fill:#ffe1f0
```

[⬆️ Về đầu trang](#mục-lục)

---

### Giải Thích Chi Tiết Grid Search

#### Bước 1: Khởi Tạo Cấu Hình

Grid Search bắt đầu bằng việc đọc các tham số cấu hình:

```python
config = {
    'cv': 5,                    # Số folds cho cross-validation
    'scoring': {                # Các metrics để đánh giá
        'accuracy': make_scorer(accuracy_score),
        'precision': make_scorer(precision_score, average='macro'),
        'recall': make_scorer(recall_score, average='macro'),
        'f1': make_scorer(f1_score, average='macro')
    },
    'metric_sort': 'f1',        # Metric chính để chọn model tốt nhất
    'n_jobs': -1,               # Số CPU cores (-1 = tất cả)
    'cache_evaluations': True,  # Bật caching
    'batch_size': 10            # Kích thước batch
}
```

#### Bước 2: Tạo Tổ Hợp Tham Số

Grid Search sử dụng `itertools.product()` để tạo tất cả các tổ hợp có thể:

```python
param_grid = {
    'C': [0.1, 1, 10],
    'kernel': ['rbf', 'linear'],
    'gamma': ['scale', 'auto']
}

# Tạo tổ hợp: 3 × 2 × 2 = 12 tổ hợp
combinations = list(itertools.product(
    param_grid['C'],
    param_grid['kernel'],
    param_grid['gamma']
))

# Kết quả:
# [
#   (0.1, 'rbf', 'scale'),
#   (0.1, 'rbf', 'auto'),
#   (0.1, 'linear', 'scale'),
#   ...
# ]
```

**Lưu ý**: Số lượng tổ hợp tăng theo cấp số nhân với số tham số. Ví dụ:
- 3 tham số, mỗi tham số 5 giá trị → 5³ = 125 tổ hợp
- 5 tham số, mỗi tham số 10 giá trị → 10⁵ = 100,000 tổ hợp

#### Bước 3: Cơ Chế Caching

Grid Search sử dụng caching để tránh đánh giá lại các tổ hợp tham số đã thử:

```python
def _get_params_hash(self, params, model_class):
    """Tạo hash key cho cache"""
    params_str = str(sorted(params.items()))
    hash_input = f"{model_class}_{params_str}"
    return hashlib.md5(hash_input.encode()).hexdigest()

# Kiểm tra cache trước khi đánh giá
cache_key = self._get_params_hash(params, model.__class__.__name__)
if cache_key in self._evaluation_cache:
    return self._evaluation_cache[cache_key].copy()
```

**Lợi ích của caching**:
- Tránh đánh giá lại khi chạy nhiều lần với cùng tham số
- Hữu ích khi so sánh nhiều models với cùng param_grid
- Tiết kiệm thời gian đáng kể cho datasets lớn

#### Bước 4: Đánh Giá Song Song

Grid Search chia công việc thành batches và đánh giá song song:

```python
def _evaluate_params_batch(self, param_combinations, model, X, y, cv, scoring):
    """Đánh giá một batch tham số song song"""
    
    # Xác định số jobs
    n_jobs = self.config.get('n_jobs', -1)
    if n_jobs == -1:
        n_jobs = multiprocessing.cpu_count()
    
    # Chọn backend dựa trên kích thước batch
    backend = 'threading' if len(param_combinations) <= 8 else 'loky'
    
    # Đánh giá song song
    results = Parallel(n_jobs=n_jobs, backend=backend, batch_size='auto')(
        delayed(self._evaluate_single_params)(
            params, model_copy, X, y, cv, scoring
        )
        for params, model_copy in zip(param_combinations, model_copies)
    )
    
    return results
```

**Lựa chọn backend**:
- **threading**: Nhanh cho batch nhỏ (≤8), overhead thấp
- **loky**: Tốt cho batch lớn (>8), process-based parallelism

#### Bước 5: Cross-Validation

Mỗi tổ hợp tham số được đánh giá bằng cross-validation:

```python
scores = cross_validate(
    model, X, y,
    cv=5,                    # 5-fold CV
    scoring=scoring_config,  # Multiple metrics
    n_jobs=1,               # 1 job vì đã parallel ở level cao hơn
    return_train_score=False,
    error_score='raise'
)

# scores chứa:
# {
#     'test_accuracy': [0.95, 0.93, 0.94, 0.96, 0.95],
#     'test_precision': [0.94, 0.92, 0.93, 0.95, 0.94],
#     'test_recall': [0.93, 0.91, 0.92, 0.94, 0.93],
#     'test_f1': [0.93, 0.91, 0.92, 0.94, 0.93],
#     'fit_time': [0.1, 0.11, 0.1, 0.12, 0.11],
#     'score_time': [0.01, 0.01, 0.01, 0.01, 0.01]
# }
```

**Tính toán metrics**:
```python
# Tính mean và std cho mỗi metric
for metric in scoring.keys():
    metric_scores = scores[f'test_{metric}']
    mean_score = np.mean(metric_scores)
    std_score = np.std(metric_scores)
```

#### Bước 6: Xây Dựng Kết Quả

Grid Search tạo dictionary `cv_results_` chứa tất cả thông tin:

```python
cv_results_ = {
    'params': [
        {'C': 0.1, 'kernel': 'rbf'},
        {'C': 0.1, 'kernel': 'linear'},
        {'C': 1, 'kernel': 'rbf'},
        ...
    ],
    'mean_test_accuracy': [0.85, 0.87, 0.92, ...],
    'std_test_accuracy': [0.02, 0.03, 0.01, ...],
    'mean_test_f1': [0.84, 0.86, 0.91, ...],
    'std_test_f1': [0.02, 0.03, 0.02, ...],
    'rank_test_accuracy': [3, 2, 1, ...],
    'rank_test_f1': [3, 2, 1, ...],
    'mean_fit_time': [0.1, 0.15, 0.2, ...],
    'mean_score_time': [0.01, 0.01, 0.02, ...]
}
```

#### Bước 7: Chọn Tham Số Tốt Nhất

```python
# Tìm tổ hợp có score cao nhất theo metric_sort
best_idx = np.argmax(cv_results_['mean_test_f1'])
best_params = cv_results_['params'][best_idx]
best_score = cv_results_['mean_test_f1'][best_idx]

# Lấy tất cả metrics của tổ hợp tốt nhất
best_all_scores = {
    'accuracy': cv_results_['mean_test_accuracy'][best_idx],
    'precision': cv_results_['mean_test_precision'][best_idx],
    'recall': cv_results_['mean_test_recall'][best_idx],
    'f1': cv_results_['mean_test_f1'][best_idx]
}
```

#### Ví Dụ Sử Dụng

```python
from automl.search.strategy.grid_search import GridSearchStrategy
from sklearn.svm import SVC

# Khởi tạo strategy
strategy = GridSearchStrategy(
    cv=5,
    n_jobs=-1,
    cache_evaluations=True,
    batch_size=10
)

# Định nghĩa param grid
param_grid = {
    'C': [0.1, 1, 10, 100],
    'kernel': ['rbf', 'linear', 'poly'],
    'gamma': ['scale', 'auto']
}

# Thực hiện tìm kiếm
model = SVC()
best_params, best_score, best_all_scores, cv_results = strategy.search(
    model=model,
    param_grid=param_grid,
    X=X_train,
    y=y_train
)

print(f"Best parameters: {best_params}")
print(f"Best F1 score: {best_score:.4f}")
print(f"All metrics: {best_all_scores}")
```

[⬆️ Về đầu trang](#mục-lục)

---

### Tối Ưu Hóa Grid Search

#### Batch Processing

Grid Search chia công việc thành các batches để tối ưu hóa hiệu suất:

```python
batch_size = 10  # Mặc định
all_results = []

for i in range(0, len(all_params), batch_size):
    batch_params = all_params[i:i+batch_size]
    batch_results = self._evaluate_params_batch(
        batch_params, model, X, y, cv, scoring
    )
    all_results.extend(batch_results)
    
    # Progress logging
    logger.info(f"Progress: {min(i+batch_size, len(all_params))}/{len(all_params)}")
```

**Lợi ích của batching**:
- Giảm memory overhead
- Cho phép progress tracking
- Dễ dàng resume nếu bị gián đoạn
- Tối ưu hóa cache locality

**Chọn batch_size phù hợp**:
- **Nhỏ (5-10)**: Cho datasets lớn, models phức tạp
- **Trung bình (10-20)**: Mặc định, phù hợp hầu hết trường hợp
- **Lớn (20-50)**: Cho datasets nhỏ, models đơn giản

#### Backend Selection

Grid Search tự động chọn backend tối ưu dựa trên workload:

```python
def _evaluate_params_batch(self, param_combinations, ...):
    # Chọn backend dựa trên số lượng combinations
    if len(param_combinations) <= 8:
        backend = 'threading'  # Overhead thấp, nhanh cho batch nhỏ
    else:
        backend = 'loky'       # Process-based, tốt cho batch lớn
    
    results = Parallel(
        n_jobs=n_jobs,
        backend=backend,
        batch_size='auto',
        prefer='threads'
    )(...)
```

**So sánh backends**:

| Backend | Overhead | Memory | GIL | Use Case |
|---------|----------|--------|-----|----------|
| threading | Thấp | Shared | Bị ảnh hưởng | Batch nhỏ, I/O bound |
| loky | Cao | Isolated | Không ảnh hưởng | Batch lớn, CPU bound |
| multiprocessing | Trung bình | Isolated | Không ảnh hưởng | Legacy, cross-platform |

#### Model Copies Pre-creation

Để tối ưu hóa parallel execution, Grid Search pre-create model copies:

```python
# Pre-create model copies cho parallel evaluation
if not self._model_copies or len(self._model_copies) < n_jobs:
    actual_n_jobs = min(n_jobs, len(param_combinations))
    self._model_copies = [
        copy.deepcopy(model) for _ in range(actual_n_jobs)
    ]

# Sử dụng model copies trong parallel loop
results = Parallel(...)(
    delayed(self._evaluate_single_params)(
        params,
        self._model_copies[i % len(self._model_copies)],  # Reuse copies
        X, y, cv, scoring
    )
    for i, params in enumerate(param_combinations)
)
```

**Lợi ích**:
- Giảm overhead của deepcopy trong mỗi iteration
- Tránh race conditions
- Memory efficient (reuse copies)

#### Cache Management

Grid Search quản lý cache hiệu quả để tránh memory overflow:

```python
def _evaluate_single_params(self, params, model, X, y, cv, scoring):
    # Kiểm tra cache
    cache_key = self._get_params_hash(params, model.__class__.__name__)
    if cache_key in self._evaluation_cache:
        return self._evaluation_cache[cache_key].copy()
    
    # Đánh giá và lưu cache
    result = self._perform_cv(...)
    
    # Quản lý kích thước cache (FIFO)
    max_cache_size = 1000
    if len(self._evaluation_cache) >= max_cache_size:
        # Xóa 25% entries cũ nhất
        keys_to_remove = list(self._evaluation_cache.keys())[:max_cache_size // 4]
        for key in keys_to_remove:
            del self._evaluation_cache[key]
    
    self._evaluation_cache[cache_key] = result
    return result
```

#### Performance Tips

**1. Giảm số tổ hợp tham số**:
```python
# Thay vì:
param_grid = {
    'C': [0.001, 0.01, 0.1, 1, 10, 100, 1000],  # 7 values
    'gamma': [0.001, 0.01, 0.1, 1, 10, 100]     # 6 values
}
# Total: 7 × 6 = 42 combinations

# Sử dụng:
param_grid = {
    'C': [0.1, 1, 10],           # 3 values
    'gamma': ['scale', 'auto']   # 2 values
}
# Total: 3 × 2 = 6 combinations
```

**2. Sử dụng stratified CV cho imbalanced data**:
```python
from sklearn.model_selection import StratifiedKFold

strategy = GridSearchStrategy(
    cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
)
```

**3. Giảm số folds cho datasets lớn**:
```python
# Thay vì cv=10, sử dụng cv=3 hoặc cv=5
strategy = GridSearchStrategy(cv=3)  # Nhanh hơn 3.3x so với cv=10
```

**4. Sử dụng subset của data cho initial search**:
```python
# Quick search trên 20% data
from sklearn.model_selection import train_test_split
X_subset, _, y_subset, _ = train_test_split(
    X, y, train_size=0.2, stratify=y, random_state=42
)

# Tìm kiếm nhanh
best_params, _, _, _ = strategy.search(model, param_grid, X_subset, y_subset)

# Refine trên full data với param grid nhỏ hơn
refined_grid = {
    'C': [best_params['C'] * 0.1, best_params['C'], best_params['C'] * 10]
}
final_best, _, _, _ = strategy.search(model, refined_grid, X, y)
```

**5. Enable logging để track progress**:
```python
strategy = GridSearchStrategy(
    save_log=True,
    verbose=1
)

# Log file sẽ được tạo tại: logs/grid_search_{model}_{timestamp}.csv
```

#### Benchmark Results

Dưới đây là kết quả benchmark trên dataset Iris (150 samples, 4 features):

| Configuration | Time (seconds) | Speedup |
|---------------|----------------|---------|
| Sequential (n_jobs=1) | 12.5 | 1.0x |
| Parallel (n_jobs=2) | 6.8 | 1.8x |
| Parallel (n_jobs=4) | 3.9 | 3.2x |
| Parallel + Cache | 2.1 | 6.0x |
| Parallel + Cache + Batch | 1.8 | 6.9x |

**Lưu ý**: Kết quả có thể khác nhau tùy thuộc vào:
- Kích thước dataset
- Độ phức tạp của model
- Số lượng CPU cores
- Overhead của parallel framework

[⬆️ Về đầu trang](#mục-lục)

---

## Genetic Algorithm

Genetic Algorithm (GA) là thuật toán tìm kiếm lấy cảm hứng từ quá trình tiến hóa tự nhiên. Thuật toán duy trì một "quần thể" các giải pháp và cải thiện chúng qua nhiều "thế hệ" bằng cách áp dụng các operators: selection, crossover, và mutation.

### Lưu Đồ Thuật Toán Genetic Algorithm

```mermaid
flowchart TD
    Start([Bắt Đầu Genetic Algorithm]) --> LoadConfig[Load cấu hình từ YAML<br/>population_size, generation,<br/>mutation_rate, crossover_rate]
    
    LoadConfig --> Encode[Encode param_grid<br/>categorical → indices<br/>continuous → ranges]
    
    Encode --> AdaptPop{Adaptive<br/>population?}
    AdaptPop -->|Yes| CalcSize[Tính toán kích thước<br/>dựa trên param space]
    AdaptPop -->|No| UseConfig[Sử dụng config size]
    
    CalcSize --> InitPop
    UseConfig --> InitPop[Khởi tạo quần thể]
    
    InitPop --> SmartInit{Init strategy<br/>= smart?}
    SmartInit -->|Yes| GridInit[Tạo mini-grid + random]
    SmartInit -->|No| RandomInit[Tạo random individuals]
    
    GridInit --> GenLoop
    RandomInit --> GenLoop[Vòng lặp Generation]
    
    GenLoop --> CalcDiv[Tính toán diversity<br/>pairwise distance]
    
    CalcDiv --> EvalPop{Parallel<br/>evaluation?}
    EvalPop -->|Yes| ParallelEval[Đánh giá song song<br/>Parallel/Joblib]
    EvalPop -->|No| SeqEval[Đánh giá tuần tự]
    
    ParallelEval --> CheckCache
    SeqEval --> CheckCache{Kiểm tra<br/>global cache?}
    
    CheckCache -->|Hit| UseCache[Sử dụng cached fitness]
    CheckCache -->|Miss| Evaluate[Cross-validation<br/>tính fitness scores]
    
    UseCache --> UpdateBest
    Evaluate --> SaveCache[Lưu vào global cache]
    SaveCache --> UpdateBest[Cập nhật best individual<br/>và best_score]
    
    UpdateBest --> CheckImprove{Có cải thiện?}
    CheckImprove -->|Yes| ResetCounter[Reset patience counter]
    CheckImprove -->|No| IncCounter[Tăng patience counter]
    
    ResetCounter --> CheckStagnation
    IncCounter --> CheckEarly{Early stopping<br/>triggered?}
    
    CheckEarly -->|Yes| Finalize
    CheckEarly -->|No| CheckStagnation
    
    CheckStagnation{Diversity < 0.05<br/>& no improve ≥ 3?}
    CheckStagnation -->|Yes| InjectDiv[Inject diversity<br/>20% random individuals]
    CheckStagnation -->|No| Selection
    
    InjectDiv --> Selection[Tournament Selection<br/>chọn parents]
    
    Selection --> Crossover[Crossover<br/>BLX-α cho continuous<br/>Uniform cho categorical]
    
    Crossover --> Mutation[Adaptive Mutation<br/>Gaussian noise<br/>giảm dần theo generation]
    
    Mutation --> Elitism[Elitism<br/>giữ lại top individuals]
    
    Elitism --> NewPop[Tạo quần thể mới]
    
    NewPop --> SaveLog{save_log?}
    SaveLog -->|Yes| WriteLog[Ghi generation log]
    SaveLog -->|No| CheckGen
    WriteLog --> CheckGen
    
    CheckGen{Còn generation?}
    CheckGen -->|Yes| GenLoop
    CheckGen -->|No| Finalize
    
    Finalize[Decode best individual<br/>Build cv_results_]
    Finalize --> Convert[Convert numpy types]
    Convert --> Return([Trả về best_params,<br/>best_score, best_all_scores,<br/>cv_results_])
    
    style Start fill:#e1f5e1
    style Return fill:#e1f5e1
    style InjectDiv fill:#ffe1e1
    style Crossover fill:#fff4e1
    style Mutation fill:#e1f0ff
    style Elitism fill:#f0e1ff
```

[⬆️ Về đầu trang](#mục-lục)

---

### Encoding/Decoding

Genetic Algorithm cần chuyển đổi tham số giữa dạng "gene" (số thực) và dạng thực tế để sử dụng với model.

#### Encoding - Chuyển Tham Số Thành Genes

```python
def _encode_parameters(self, param_grid):
    """Encode parameter grid cho genetic algorithm"""
    self.param_bounds = {}
    self.param_types = {}
    
    for param_name, param_values in param_grid.items():
        if isinstance(param_values, list):
            # Categorical parameter
            self.param_bounds[param_name] = (0, len(param_values) - 1)
            self.param_types[param_name] = ('categorical', param_values)
            
        elif isinstance(param_values, tuple) and len(param_values) == 2:
            # Continuous or Integer parameter
            min_val, max_val = param_values
            self.param_bounds[param_name] = (min_val, max_val)
            
            if isinstance(min_val, int) and isinstance(max_val, int):
                self.param_types[param_name] = ('integer', None)
            else:
                self.param_types[param_name] = ('continuous', None)
```

**Ví dụ Encoding**:

```python
# Input param_grid
param_grid = {
    'kernel': ['rbf', 'linear', 'poly'],      # Categorical
    'C': (0.1, 100.0),                        # Continuous
    'max_iter': (100, 1000)                   # Integer
}

# Sau khi encode:
param_bounds = {
    'kernel': (0, 2),        # Indices: 0='rbf', 1='linear', 2='poly'
    'C': (0.1, 100.0),       # Giữ nguyên range
    'max_iter': (100, 1000)  # Giữ nguyên range
}

param_types = {
    'kernel': ('categorical', ['rbf', 'linear', 'poly']),
    'C': ('continuous', None),
    'max_iter': ('integer', None)
}

# Individual (gene representation)
individual = {
    'kernel': 1.7,      # Sẽ được round thành 2 → 'poly'
    'C': 45.3,          # Giá trị continuous
    'max_iter': 567.8   # Sẽ được round thành 568
}
```

#### Decoding - Chuyển Genes Thành Tham Số

```python
def _decode_individual(self, individual):
    """Decode individual từ gene representation sang actual parameters"""
    # Check cache first
    cache_key = self._make_hashable(individual)
    if cache_key in self._decode_cache:
        return self._decode_cache[cache_key].copy()
    
    decoded = {}
    
    for param_name, value in individual.items():
        param_type, param_values = self.param_types[param_name]
        
        if param_type == 'categorical':
            # Round và clamp vào valid range
            index = int(round(value))
            index = max(0, min(index, len(param_values) - 1))
            decoded[param_name] = param_values[index]
            
        elif param_type == 'integer':
            # Round thành integer
            decoded[param_name] = int(round(value))
            
        else:  # continuous
            # Giữ nguyên float
            decoded[param_name] = float(value)
    
    # Cache kết quả
    self._decode_cache[cache_key] = decoded
    return decoded
```

**Ví dụ Decoding**:

```python
# Individual (genes)
individual = {
    'kernel': 1.7,
    'C': 45.3,
    'max_iter': 567.8
}

# Sau khi decode:
decoded_params = {
    'kernel': 'poly',    # round(1.7) = 2 → param_values[2] = 'poly'
    'C': 45.3,           # Giữ nguyên
    'max_iter': 568      # round(567.8) = 568
}

# Sử dụng với model
model.set_params(**decoded_params)
```

#### Tại Sao Cần Encoding?

**1. Uniform Representation**:
- Tất cả tham số đều là số thực
- Dễ dàng áp dụng crossover và mutation
- Không cần xử lý đặc biệt cho từng loại

**2. Continuous Search Space**:
- Genetic operators hoạt động tốt với continuous values
- Crossover có thể tạo ra giá trị trung gian
- Mutation có thể điều chỉnh nhỏ

**3. Caching Efficiency**:
- Decode cache giảm overhead
- Hash individual nhanh chóng
- Tránh decode lặp lại

#### Xử Lý Edge Cases

```python
def _decode_individual(self, individual):
    decoded = {}
    
    for param_name, value in individual.items():
        param_type, param_values = self.param_types[param_name]
        
        if param_type == 'categorical':
            index = int(round(value))
            # Clamp vào valid range để tránh index out of bounds
            index = max(0, min(index, len(param_values) - 1))
            param_value = param_values[index]
            
            # Convert numpy types sang Python native
            if isinstance(param_value, np.integer):
                decoded[param_name] = int(param_value)
            elif isinstance(param_value, np.floating):
                decoded[param_name] = float(param_value)
            else:
                decoded[param_name] = param_value
                
        elif param_type == 'integer':
            # Ensure integer type
            decoded[param_name] = int(round(value))
            
        else:  # continuous
            # Ensure float type
            decoded[param_name] = float(value)
    
    return decoded
```

#### Performance Optimization

**Decode Caching**:
```python
# Cache để tránh decode lặp lại
self._decode_cache = {}

def _make_hashable(self, individual):
    """Convert individual thành hashable tuple"""
    return tuple(sorted(individual.items()))

# Trong _decode_individual:
cache_key = self._make_hashable(individual)
if cache_key in self._decode_cache:
    return self._decode_cache[cache_key].copy()

# ... decode logic ...

self._decode_cache[cache_key] = decoded
return decoded
```

**Cache Statistics**:
```python
# Track cache efficiency
cache_hits = 0
total_decodes = 0

# Trong mỗi decode:
total_decodes += 1
if cache_key in self._decode_cache:
    cache_hits += 1

# Report
cache_efficiency = (cache_hits / total_decodes) * 100
print(f"Decode cache efficiency: {cache_efficiency:.1f}%")
```

[⬆️ Về đầu trang](#mục-lục)

---

### Các Operators

Genetic Algorithm sử dụng ba operators chính để tạo ra thế hệ mới: Selection, Crossover, và Mutation.

#### 1. Selection - Tournament Selection

Tournament selection chọn parents bằng cách tổ chức "giải đấu" giữa một số individuals ngẫu nhiên:

```python
def _tournament_selection(self, population, fitness_scores):
    """Chọn individual bằng tournament selection"""
    tournament_size = self.config['tournament_size']  # Mặc định: 3
    
    # Chọn ngẫu nhiên tournament_size individuals
    tournament_indices = np.random.choice(
        len(population),
        size=tournament_size,
        replace=False
    )
    
    # Chọn individual có fitness cao nhất
    winner_index = tournament_indices[
        np.argmax(fitness_scores[tournament_indices])
    ]
    
    return population[winner_index].copy()
```

**Ví dụ**:
```python
population = [ind1, ind2, ind3, ind4, ind5]
fitness_scores = [0.85, 0.92, 0.78, 0.95, 0.88]

# Tournament với size=3
# Giả sử chọn indices [1, 3, 4]
# Fitness: [0.92, 0.95, 0.88]
# Winner: index 3 (fitness=0.95) → ind4
```

**Ưu điểm**:
- Đơn giản và nhanh
- Có thể điều chỉnh selection pressure bằng tournament_size
- Không cần sort toàn bộ population

**Tournament Size**:
- **Nhỏ (2-3)**: Selection pressure thấp, exploration nhiều
- **Trung bình (3-5)**: Cân bằng exploration/exploitation
- **Lớn (5-7)**: Selection pressure cao, exploitation nhiều

#### 2. Crossover

Crossover kết hợp genes từ hai parents để tạo offspring.

##### Uniform Crossover (Categorical Parameters)

```python
def _crossover_categorical(self, parent1, parent2, param_name):
    """Uniform crossover cho categorical parameters"""
    child1 = parent1.copy()
    child2 = parent2.copy()
    
    # Swap với xác suất 50%
    if random.random() < 0.5:
        child1[param_name], child2[param_name] = \
            child2[param_name], child1[param_name]
    
    return child1, child2
```

**Ví dụ**:
```python
parent1 = {'kernel': 1.0}  # 'linear'
parent2 = {'kernel': 2.0}  # 'poly'

# 50% chance swap
# Kết quả có thể:
# child1 = {'kernel': 2.0}, child2 = {'kernel': 1.0}  # Swapped
# hoặc
# child1 = {'kernel': 1.0}, child2 = {'kernel': 2.0}  # Not swapped
```

##### BLX-α Crossover (Continuous/Integer Parameters)

Blend Crossover (BLX-α) tạo offspring trong range mở rộng của parents:

```python
def _crossover_continuous(self, parent1, parent2, param_name):
    """BLX-α crossover cho continuous/integer parameters"""
    alpha = 0.5  # Blending factor
    
    # Tìm min và max
    min_val = min(parent1[param_name], parent2[param_name])
    max_val = max(parent1[param_name], parent2[param_name])
    range_val = max_val - min_val
    
    # Mở rộng range bằng alpha
    lower = min_val - alpha * range_val
    upper = max_val + alpha * range_val
    
    # Clamp vào param bounds
    param_min, param_max = self.param_bounds[param_name]
    lower = max(lower, param_min)
    upper = min(upper, param_max)
    
    # Sample random trong extended range
    child1[param_name] = random.uniform(lower, upper)
    child2[param_name] = random.uniform(lower, upper)
    
    return child1, child2
```

**Ví dụ**:
```python
parent1 = {'C': 10.0}
parent2 = {'C': 20.0}
alpha = 0.5

# Range: 20 - 10 = 10
# Extended range: [10 - 0.5*10, 20 + 0.5*10] = [5, 25]

# Children có thể có C trong [5, 25]
# Ví dụ: child1 = {'C': 7.3}, child2 = {'C': 18.9}
```

**Tại sao BLX-α?**:
- Cho phép exploration ngoài range của parents
- α = 0.5 cân bằng exploration/exploitation
- Tạo diversity trong population

##### Adaptive Crossover Rate

```python
# Tăng crossover rate khi diversity thấp
adaptive_crossover_rate = self.config['crossover_rate']
if diversity < 0.1:
    adaptive_crossover_rate = min(1.0, adaptive_crossover_rate * 1.2)

# Áp dụng crossover
if random.random() < adaptive_crossover_rate:
    child1, child2 = self._crossover(parent1, parent2)
else:
    child1, child2 = parent1.copy(), parent2.copy()
```

#### 3. Mutation

Mutation thêm random changes vào genes để duy trì diversity.

##### Adaptive Mutation Rate

```python
def _mutate(self, individual, generation, max_generation):
    """Mutate với adaptive rate"""
    # Mutation rate giảm dần theo generation
    if max_generation and max_generation > 0:
        adaptive_rate = self.config['mutation_rate'] * \
                       (1 - generation / max_generation)
    else:
        adaptive_rate = self.config['mutation_rate']
    
    mutated = individual.copy()
    
    for param_name in mutated.keys():
        if random.random() < adaptive_rate:
            # Mutate this parameter
            mutated[param_name] = self._mutate_param(
                param_name, mutated[param_name], generation, max_generation
            )
    
    return mutated
```

**Adaptive Rate Example**:
```python
base_rate = 0.2
max_gen = 50

# Generation 0: rate = 0.2 * (1 - 0/50) = 0.20
# Generation 25: rate = 0.2 * (1 - 25/50) = 0.10
# Generation 49: rate = 0.2 * (1 - 49/50) = 0.004
```

##### Categorical Mutation

```python
def _mutate_categorical(self, param_name, current_value):
    """Mutate categorical parameter"""
    min_val, max_val = self.param_bounds[param_name]
    possible_values = list(range(int(min_val), int(max_val) + 1))
    
    # Loại bỏ giá trị hiện tại
    if len(possible_values) > 1:
        possible_values.remove(int(round(current_value)))
        # Chọn giá trị khác ngẫu nhiên
        return float(random.choice(possible_values))
    
    return current_value
```

**Ví dụ**:
```python
# kernel có 3 giá trị: [0, 1, 2] → ['rbf', 'linear', 'poly']
current_value = 1.0  # 'linear'

# Possible values: [0, 2] (loại bỏ 1)
# Random choice: 0 hoặc 2
# Kết quả: 0.0 ('rbf') hoặc 2.0 ('poly')
```

##### Gaussian Mutation (Continuous/Integer)

```python
def _mutate_continuous(self, param_name, current_value, generation, max_gen):
    """Mutate continuous/integer parameter với Gaussian noise"""
    min_val, max_val = self.param_bounds[param_name]
    
    # Mutation strength giảm dần theo generation
    mutation_strength = (max_val - min_val) * \
                       (0.2 * (1 - generation / (max_gen + 1)))
    
    # Thêm Gaussian noise
    new_val = current_value + random.gauss(0, mutation_strength)
    
    # Clamp vào bounds
    new_val = max(min_val, min(new_val, max_val))
    
    return new_val
```

**Ví dụ**:
```python
param_bounds = {'C': (0.1, 100)}
current_value = 10.0
generation = 10
max_gen = 50

# Range: 100 - 0.1 = 99.9
# Strength: 99.9 * 0.2 * (1 - 10/51) = 99.9 * 0.2 * 0.804 = 16.06
# Gaussian noise: N(0, 16.06)
# Ví dụ noise = -5.3
# new_val = 10.0 + (-5.3) = 4.7
```

**Tại sao Gaussian?**:
- Mutation nhỏ thường xuyên hơn mutation lớn
- Phù hợp với fine-tuning
- Strength giảm dần → convergence

#### Code Example: Full Crossover & Mutation

```python
# Selection
parent1 = self._tournament_selection(population, fitness_scores)
parent2 = self._tournament_selection(population, fitness_scores)

# Crossover
if random.random() < self.config['crossover_rate']:
    child1, child2 = self._crossover(parent1, parent2)
else:
    child1, child2 = parent1.copy(), parent2.copy()

# Mutation
child1 = self._mutate(child1, generation, max_generation)
child2 = self._mutate(child2, generation, max_generation)

# Thêm vào population mới
new_population.append(child1)
new_population.append(child2)
```

[⬆️ Về đầu trang](#mục-lục)

---

### Elitism và Diversity

#### Elitism - Giữ Lại Cá Thể Tốt Nhất

Elitism đảm bảo rằng các individuals tốt nhất không bị mất qua các generations:

```python
def _apply_elitism(self, population, fitness_scores, elite_size):
    """Giữ lại elite_size individuals tốt nhất"""
    new_population = []
    
    # Tìm indices của elite individuals
    elite_indices = np.argpartition(
        fitness_scores,
        -elite_size
    )[-elite_size:]
    
    # Copy elite individuals sang generation mới
    for idx in elite_indices:
        new_population.append(population[idx].copy())
    
    return new_population
```

**Ví dụ**:
```python
population_size = 20
elite_size = 4  # Giữ lại 20% tốt nhất

fitness_scores = [0.85, 0.92, 0.78, 0.95, 0.88, ...]

# Elite indices: [3, 1, 4, ...] (4 individuals có fitness cao nhất)
# Các individuals này được copy trực tiếp sang generation mới
```

**Lợi ích**:
- Đảm bảo best solution không bị mất
- Tăng tốc độ convergence
- Giảm risk của random operators

**Elite Size**:
- **Nhỏ (1-2)**: Ít ảnh hưởng, nhiều exploration
- **Trung bình (10-20% population)**: Cân bằng tốt
- **Lớn (>30% population)**: Convergence nhanh nhưng có thể premature

#### Diversity Calculation

Diversity đo lường sự khác biệt giữa các individuals trong population:

```python
def _calculate_population_diversity(self, population):
    """Tính diversity bằng average pairwise distance"""
    if len(population) < 2:
        return 0.0
    
    total_distance = 0
    count = 0
    
    # Tính distance giữa mọi cặp individuals
    for i in range(len(population)):
        for j in range(i + 1, len(population)):
            distance = 0
            
            for param_name in population[i].keys():
                param_type, _ = self.param_types[param_name]
                
                if param_type == 'categorical':
                    # Distance 0/1 cho categorical
                    if population[i][param_name] != population[j][param_name]:
                        distance += 1
                else:
                    # Normalized distance cho continuous/integer
                    min_val, max_val = self.param_bounds[param_name]
                    if max_val != min_val:
                        diff = abs(population[i][param_name] - 
                                 population[j][param_name])
                        normalized_diff = diff / (max_val - min_val)
                        distance += normalized_diff
            
            # Average over parameters
            total_distance += distance / len(population[i])
            count += 1
    
    return total_distance / count if count > 0 else 0.0
```

**Ví dụ**:
```python
population = [
    {'C': 1.0, 'kernel': 0.0},   # ind1
    {'C': 10.0, 'kernel': 0.0},  # ind2
    {'C': 1.0, 'kernel': 2.0}    # ind3
]

# Distance(ind1, ind2):
#   C: |1-10|/(100-0.1) = 0.09
#   kernel: 0 (same)
#   Average: 0.045

# Distance(ind1, ind3):
#   C: 0 (same)
#   kernel: 1 (different)
#   Average: 0.5

# Distance(ind2, ind3):
#   C: |10-1|/(100-0.1) = 0.09
#   kernel: 1 (different)
#   Average: 0.545

# Total diversity: (0.045 + 0.5 + 0.545) / 3 = 0.363
```

**Interpretation**:
- **High diversity (>0.5)**: Population rất đa dạng, exploration tốt
- **Medium diversity (0.2-0.5)**: Cân bằng exploration/exploitation
- **Low diversity (<0.2)**: Population hội tụ, risk of premature convergence

#### Diversity Injection

Khi diversity quá thấp, inject random individuals để tăng exploration:

```python
def _inject_diversity(self, population, injection_rate=0.3):
    """Inject random individuals khi population stagnates"""
    num_to_inject = int(len(population) * injection_rate)
    
    if num_to_inject == 0:
        return population
    
    new_population = population.copy()
    
    # Thay thế random individuals (không phải elite)
    injection_indices = random.sample(
        range(self.config['elite_size'], len(population)),
        num_to_inject
    )
    
    for idx in injection_indices:
        new_population[idx] = self._create_individual()
    
    return new_population
```

**Khi nào inject?**:
```python
stagnation_threshold = 0.05
if diversity < stagnation_threshold and generations_without_improvement >= 3:
    logger.warning(f"Stagnation detected (diversity={diversity:.4f})")
    population = self._inject_diversity(population, injection_rate=0.2)
    logger.info("Diversity injection complete!")
```

**Ví dụ**:
```python
population_size = 20
elite_size = 4
injection_rate = 0.2

# Inject 20% = 4 individuals
# Chọn 4 indices từ [4, 5, ..., 19] (không touch elite [0-3])
# Ví dụ: indices [7, 12, 15, 18]
# Thay thế bằng random individuals mới
```

**Lợi ích**:
- Thoát khỏi local optima
- Tăng exploration khi stuck
- Maintain genetic diversity

#### Monitoring Diversity

```python
diversity_history = []

for generation in range(max_generations):
    # Calculate diversity
    diversity = self._calculate_population_diversity(population)
    diversity_history.append(diversity)
    
    # Log
    logger.info(f"Generation {generation}: Diversity = {diversity:.4f}")
    
    # Check stagnation
    if diversity < 0.05:
        logger.warning("Low diversity detected!")
```

**Visualization** (conceptual):
```
Generation | Diversity | Action
-----------|-----------|--------
0          | 0.85      | Initial high diversity
10         | 0.45      | Normal convergence
20         | 0.25      | Continuing convergence
30         | 0.08      | Low diversity warning
31         | 0.35      | Diversity injection applied
40         | 0.15      | Converging to optimum
50         | 0.05      | Final convergence
```

[⬆️ Về đầu trang](#mục-lục)

---

### Early Stopping Genetic Algorithm

Early stopping giúp dừng thuật toán sớm khi không còn cải thiện, tiết kiệm thời gian tính toán.

#### Patience-Based Stopping

Dừng sau N generations không có cải thiện:

```python
# Tracking
best_score = float('-inf')
best_generation = 0
generations_without_improvement = 0
early_stopping_patience = 5

for generation in range(max_generations):
    # Evaluate population
    current_best = max(fitness_scores)
    
    if current_best > best_score:
        best_score = current_best
        best_generation = generation
        generations_without_improvement = 0
    else:
        generations_without_improvement += 1
    
    # Check early stopping
    if generations_without_improvement >= early_stopping_patience:
        logger.info(f"Early stopping at generation {generation}")
        logger.info(f"Best score {best_score:.4f} at generation {best_generation}")
        break
```

**Ví dụ**:
```
Gen | Best Score | Improvement | Counter | Action
----|------------|-------------|---------|--------
0   | 0.85       | -           | 0       | Continue
5   | 0.92       | Yes         | 0       | Reset counter
10  | 0.92       | No          | 1       | Increment
11  | 0.92       | No          | 2       | Increment
12  | 0.92       | No          | 3       | Increment
13  | 0.92       | No          | 4       | Increment
14  | 0.92       | No          | 5       | STOP (patience=5)
```

#### Convergence-Based Stopping

Dừng khi improvement quá nhỏ:

```python
convergence_threshold = 0.001
convergence_history = []

for generation in range(max_generations):
    current_best = max(fitness_scores)
    convergence_history.append(current_best)
    
    # Check convergence
    if generation > 0:
        improvement = convergence_history[-1] - convergence_history[-2]
        
        if abs(improvement) < convergence_threshold:
            logger.info(f"Convergence detected at generation {generation}")
            logger.info(f"Improvement {improvement:.6f} < threshold {convergence_threshold}")
            break
```

**Ví dụ**:
```
Gen | Best Score | Improvement | Action
----|------------|-------------|--------
45  | 0.9234     | -           | Continue
46  | 0.9241     | 0.0007      | Continue (> 0.001)
47  | 0.9243     | 0.0002      | STOP (< 0.001)
```

#### Combined Stopping Strategy

Kết hợp cả hai phương pháp:

```python
def check_early_stopping(self, generation, current_best, best_score, 
                        generations_without_improvement, convergence_history):
    """Check early stopping conditions"""
    
    # Patience-based
    if generations_without_improvement >= self.config['early_stopping_patience']:
        logger.info(f"Early stopping: No improvement for {generations_without_improvement} generations")
        return True
    
    # Convergence-based
    if len(convergence_history) > 1:
        improvement = convergence_history[-1] - convergence_history[-2]
        threshold = self.config['convergence_threshold']
        
        if abs(improvement) < threshold and generations_without_improvement >= 2:
            logger.info(f"Convergence: Improvement {improvement:.6f} < {threshold}")
            return True
    
    return False
```

#### Configuration

```python
config = {
    'early_stopping_enabled': True,
    'early_stopping_patience': 5,      # Số generations không cải thiện
    'convergence_threshold': 0.001,    # Threshold cho improvement
}

# Sử dụng
ga = GeneticAlgorithm(**config)
```

**Tuning Parameters**:

| Parameter | Small Value | Large Value | Effect |
|-----------|-------------|-------------|--------|
| patience | 3-5 | 10-15 | Dừng sớm hơn vs chạy lâu hơn |
| threshold | 0.0001 | 0.01 | Strict vs lenient convergence |

#### Logging và Reporting

```python
# Trong main loop
if early_stopping_triggered:
    logger.info("=" * 60)
    logger.info("EARLY STOPPING TRIGGERED")
    logger.info("=" * 60)
    logger.info(f"Stopped at generation: {generation + 1}/{max_generations}")
    logger.info(f"Best score: {best_score:.4f}")
    logger.info(f"Best generation: {best_generation + 1}")
    logger.info(f"Generations without improvement: {generations_without_improvement}")
    logger.info(f"Time saved: {(max_generations - generation) * avg_gen_time:.1f}s")
```

**Example Output**:
```
============================================================
EARLY STOPPING TRIGGERED
============================================================
Stopped at generation: 23/50
Best score: 0.9456
Best generation: 18
Generations without improvement: 5
Time saved: 135.2s
```

#### Benefits

**1. Time Savings**:
```python
# Không có early stopping
total_time = 50 generations × 5s = 250s

# Với early stopping (dừng ở gen 23)
actual_time = 23 generations × 5s = 115s
time_saved = 250s - 115s = 135s (54% faster)
```

**2. Prevent Overfitting**:
- Dừng trước khi model overfit trên CV folds
- Giữ lại generalization tốt hơn

**3. Resource Efficiency**:
- Giảm CPU usage
- Giảm memory usage
- Cho phép chạy nhiều experiments hơn

#### Best Practices

**1. Không dùng early stopping quá aggressive**:
```python
# TOO AGGRESSIVE (có thể dừng quá sớm)
config = {
    'early_stopping_patience': 2,
    'convergence_threshold': 0.01
}

# RECOMMENDED
config = {
    'early_stopping_patience': 5,
    'convergence_threshold': 0.001
}
```

**2. Monitor convergence history**:
```python
# Save convergence history
convergence_df = pd.DataFrame({
    'generation': range(len(convergence_history)),
    'best_score': convergence_history,
    'diversity': diversity_history
})
convergence_df.to_csv('convergence_history.csv')
```

**3. Combine với diversity injection**:
```python
# Nếu diversity thấp VÀ không cải thiện → inject trước khi early stop
if diversity < 0.05 and generations_without_improvement >= 3:
    population = self._inject_diversity(population)
    generations_without_improvement = 0  # Reset counter
```

[⬆️ Về đầu trang](#mục-lục)

---

## Bayesian Search

Bayesian Search sử dụng Bayesian Optimization để tìm kiếm siêu tham số một cách thông minh. Thay vì thử ngẫu nhiên, thuật toán xây dựng một mô hình xác suất (surrogate model) về hàm mục tiêu và sử dụng nó để quyết định điểm tiếp theo cần thử.

### Lưu Đồ Thuật Toán Bayesian Search

```mermaid
flowchart TD
    Start([Bắt Đầu Bayesian Search]) --> LoadConfig[Load cấu hình<br/>n_calls, n_initial_points,<br/>acq_func, acq_optimizer]
    
    LoadConfig --> DetectImbalance{optimize_for<br/>= auto?}
    DetectImbalance -->|Yes| CheckBalance[Phát hiện class imbalance<br/>Counter + threshold]
    DetectImbalance -->|No| UseConfig[Sử dụng config]
    
    CheckBalance --> DecideAvg{Imbalanced?}
    DecideAvg -->|Yes| UseWeighted[averaging = weighted]
    DecideAvg -->|No| UseMacro[averaging = macro]
    
    UseWeighted --> ConvertSpace
    UseMacro --> ConvertSpace
    UseConfig --> ConvertSpace
    
    ConvertSpace[Chuyển đổi param_grid<br/>thành search space<br/>Real, Integer, Categorical]
    
    ConvertSpace --> InitGP[Khởi tạo Gaussian Process<br/>surrogate model]
    
    InitGP --> RandomPhase[Phase 1: Random Exploration<br/>n_initial_points iterations]
    
    RandomPhase --> EvalRandom[Đánh giá ngẫu nhiên<br/>cross_validate với scoring]
    
    EvalRandom --> UpdateGP1[Cập nhật GP model<br/>với observations]
    
    UpdateGP1 --> CheckInitial{Đủ initial<br/>points?}
    CheckInitial -->|No| RandomPhase
    CheckInitial -->|Yes| BayesPhase
    
    BayesPhase[Phase 2: Bayesian Optimization<br/>n_calls - n_initial_points iterations]
    
    BayesPhase --> BuildGP[Xây dựng GP surrogate<br/>từ observations]
    
    BuildGP --> AcqFunc[Tính Acquisition Function<br/>EI, PI, hoặc UCB]
    
    AcqFunc --> OptimizeAcq[Tối ưu acquisition<br/>sampling hoặc lbfgs]
    
    OptimizeAcq --> NextPoint[Chọn điểm tiếp theo<br/>maximize acquisition]
    
    NextPoint --> Evaluate[Đánh giá điểm mới<br/>cross_validate]
    
    Evaluate --> CalcMetrics[Tính toán metrics<br/>accuracy, precision, recall, f1]
    
    CalcMetrics --> UpdateGP2[Cập nhật GP model<br/>thêm observation mới]
    
    UpdateGP2 --> UpdateBest[Cập nhật best_params<br/>và best_score]
    
    UpdateBest --> Callback[Callback function<br/>log iteration results]
    
    Callback --> CheckEarly{Early stopping<br/>check}
    
    CheckEarly --> NoImprove{No improve<br/>≥ patience?}
    NoImprove -->|Yes| StopEarly[Early stop triggered]
    NoImprove -->|No| CheckConv
    
    CheckConv{Improvement<br/>< threshold?}
    CheckConv -->|Yes| StopConv[Convergence detected]
    CheckConv -->|No| SaveIter
    
    SaveIter{save_log?}
    SaveIter -->|Yes| WriteIter[Ghi iteration log]
    SaveIter -->|No| CheckCalls
    WriteIter --> CheckCalls
    
    CheckCalls{Còn calls?}
    CheckCalls -->|Yes| BayesPhase
    CheckCalls -->|No| Finalize
    
    StopEarly --> Finalize
    StopConv --> Finalize
    
    Finalize[Lấy kết quả tốt nhất<br/>từ gp_minimize result]
    
    Finalize --> BuildCV[Xây dựng cv_results_<br/>từ search history]
    
    BuildCV --> Rank[Tính toán rankings<br/>cho mỗi metric]
    
    Rank --> Convert[Convert numpy types<br/>sang Python native]
    
    Convert --> Return([Trả về best_params,<br/>best_score, best_all_scores,<br/>cv_results_])
    
    style Start fill:#e1f5e1
    style Return fill:#e1f5e1
    style RandomPhase fill:#fff4e1
    style BayesPhase fill:#e1f0ff
    style AcqFunc fill:#ffe1f0
    style BuildGP fill:#f0e1ff
```

[⬆️ Về đầu trang](#mục-lục)

---

### Gaussian Process

Gaussian Process (GP) là surrogate model dự đoán performance của tham số chưa thử dựa trên observations đã có.

**Công thức cơ bản**:
```
f(x) ~ GP(μ(x), k(x, x'))
```
Trong đó:
- `μ(x)`: Mean function (thường = 0)
- `k(x, x')`: Kernel function đo similarity giữa hai điểm

**Ví dụ đơn giản**:
```python
# Đã thử 3 điểm
observations = [
    ({'C': 1}, 0.85),
    ({'C': 10}, 0.92),
    ({'C': 100}, 0.88)
]

# GP dự đoán cho điểm mới
x_new = {'C': 5}
μ, σ = gp.predict(x_new)
# μ = 0.90 (predicted mean)
# σ = 0.03 (uncertainty)
```

### Acquisition Functions

Acquisition function quyết định điểm tiếp theo cần thử bằng cách cân bằng exploration và exploitation.

**Expected Improvement (EI)**:
```python
EI(x) = E[max(f(x) - f(x_best), 0)]
```
- Chọn điểm có khả năng cải thiện cao nhất
- Cân bằng tốt exploration/exploitation

**Upper Confidence Bound (UCB)**:
```python
UCB(x) = μ(x) + κ*σ(x)
```
- κ điều chỉnh exploration (κ lớn → explore nhiều)
- Đơn giản và hiệu quả

### Class Imbalance Detection

```python
def _detect_class_imbalance(self, y):
    class_counts = Counter(y)
    ratios = {cls: count/len(y) for cls, count in class_counts.items()}
    return (max(ratios.values()) - min(ratios.values())) > 0.3
```

Nếu imbalanced → sử dụng `weighted` averaging, ngược lại → `macro`.

### Early Stopping Bayesian Search

Tương tự GA, Bayesian Search có patience-based và convergence-based stopping.

```python
# Trong callback
if no_improvement >= patience:
    return True  # Stop gp_minimize

if abs(improvement) < threshold:
    return True  # Convergence
```

[⬆️ Về đầu trang](#mục-lục)

---

## So Sánh Các Thuật Toán

### Bảng So Sánh

| Tiêu Chí | Grid Search | Genetic Algorithm | Bayesian Search |
|----------|-------------|-------------------|-----------------|
| **Độ phức tạp thời gian** | O(n^d × cv) | O(pop × gen × cv) | O(n × cv + n³) |
| **Độ phức tạp không gian** | O(n^d) | O(pop) | O(n²) |
| **Tính toàn diện** | 100% | ~70-90% | ~80-95% |
| **Tốc độ** | Chậm | Trung bình | Nhanh |
| **Parallel** | Tốt | Tốt | Trung bình |
| **Tối ưu cho** | Không gian nhỏ | Không gian lớn | Không gian phức tạp |
| **Số lần đánh giá** | Tất cả tổ hợp | Có thể điều chỉnh | Có thể điều chỉnh |
| **Reproducibility** | 100% | Phụ thuộc seed | Phụ thuộc seed |
| **Categorical params** | Tốt | Tốt | Trung bình |
| **Continuous params** | Trung bình | Tốt | Rất tốt |
| **Dễ hiểu** | Rất dễ | Trung bình | Khó |
| **Tuning effort** | Thấp | Trung bình | Cao |

**Chú thích**:
- `n`: số tổ hợp tham số
- `d`: số chiều (số tham số)
- `cv`: số folds cross-validation
- `pop`: kích thước quần thể (GA)
- `gen`: số generations (GA)

### Hướng Dẫn Lựa Chọn

#### Sử dụng Grid Search khi:

✅ **Phù hợp**:
- Không gian tham số nhỏ (< 100 tổ hợp)
- Cần kết quả chính xác 100%
- Có nhiều CPU cores để parallel
- Thời gian không phải vấn đề
- Muốn reproducible results

❌ **Không phù hợp**:
- Không gian tham số lớn (> 1000 tổ hợp)
- Thời gian tính toán hạn chế
- Nhiều tham số continuous

**Ví dụ**:
```python
# Small parameter space
param_grid = {
    'C': [0.1, 1, 10],
    'kernel': ['rbf', 'linear']
}
# Total: 3 × 2 = 6 combinations ✓
```

#### Sử dụng Genetic Algorithm khi:

✅ **Phù hợp**:
- Không gian tham số lớn (> 1000 tổ hợp)
- Có nhiều tham số categorical
- Cần cân bằng tốc độ và chất lượng
- Muốn tùy chỉnh evolution process
- Budget evaluations linh hoạt

❌ **Không phù hợp**:
- Cần reproducibility tuyệt đối
- Không gian tham số rất nhỏ
- Không có thời gian tuning GA parameters

**Ví dụ**:
```python
# Large parameter space
param_grid = {
    'n_estimators': list(range(10, 200, 10)),      # 19 values
    'max_depth': list(range(3, 20)),               # 17 values
    'min_samples_split': list(range(2, 20)),       # 18 values
    'min_samples_leaf': list(range(1, 10))         # 9 values
}
# Total: 19 × 17 × 18 × 9 = 52,326 combinations
# GA với 20 pop × 30 gen = 600 evaluations ✓
```

#### Sử dụng Bayesian Search khi:

✅ **Phù hợp**:
- Không gian tham số phức tạp
- Mỗi evaluation tốn thời gian (> 1 phút)
- Cần tối ưu nhanh với ít iterations
- Có nhiều tham số continuous
- Budget evaluations hạn chế (< 100)

❌ **Không phù hợp**:
- Nhiều tham số categorical
- Cần parallel evaluation tối đa
- Không gian tham số đơn giản

**Ví dụ**:
```python
from skopt.space import Real, Integer

# Continuous parameter space
param_grid = {
    'learning_rate': Real(0.001, 0.1, prior='log-uniform'),
    'n_estimators': Integer(50, 500),
    'max_depth': Integer(3, 15),
    'subsample': Real(0.5, 1.0)
}
# Infinite continuous space
# Bayesian với 25 calls tìm được gần optimal ✓
```

### Ví Dụ Use Cases

#### Use Case 1: SVM Classification (Small Space)

**Scenario**: Tìm tham số cho SVM trên dataset nhỏ (1000 samples)

```python
param_grid = {
    'C': [0.1, 1, 10, 100],
    'kernel': ['rbf', 'linear', 'poly'],
    'gamma': ['scale', 'auto']
}
# Total: 4 × 3 × 2 = 24 combinations
```

**Recommendation**: **Grid Search**
- Chỉ 24 combinations, chạy nhanh
- Đảm bảo tìm được best combination
- Parallel tốt với 24 jobs

#### Use Case 2: Random Forest (Large Space)

**Scenario**: Tối ưu Random Forest với nhiều tham số

```python
param_grid = {
    'n_estimators': list(range(50, 500, 50)),      # 9 values
    'max_depth': list(range(5, 30, 5)),            # 5 values
    'min_samples_split': [2, 5, 10, 20],           # 4 values
    'min_samples_leaf': [1, 2, 4, 8],              # 4 values
    'max_features': ['sqrt', 'log2', None]         # 3 values
}
# Total: 9 × 5 × 4 × 4 × 3 = 2,160 combinations
```

**Recommendation**: **Genetic Algorithm**
- Quá nhiều combinations cho Grid Search
- GA với 30 pop × 20 gen = 600 evaluations
- Tìm được ~85-90% optimal solution
- Tiết kiệm 72% thời gian

#### Use Case 3: XGBoost (Continuous Space)

**Scenario**: Fine-tune XGBoost với continuous parameters

```python
from skopt.space import Real, Integer

param_grid = {
    'learning_rate': Real(0.001, 0.3, prior='log-uniform'),
    'max_depth': Integer(3, 12),
    'min_child_weight': Real(0.5, 10.0),
    'subsample': Real(0.5, 1.0),
    'colsample_bytree': Real(0.5, 1.0),
    'gamma': Real(0.0, 5.0)
}
```

**Recommendation**: **Bayesian Search**
- Continuous parameters → GP hoạt động tốt
- Mỗi evaluation tốn thời gian (XGBoost phức tạp)
- 30-50 calls đủ để tìm gần optimal
- Thông minh hơn random search

### Decision Tree

```
Bắt đầu
   |
   v
Không gian < 100 combinations?
   |
   ├─ Yes → Grid Search
   |
   └─ No → Có nhiều continuous params?
            |
            ├─ Yes → Bayesian Search
            |
            └─ No → Genetic Algorithm
```

[⬆️ Về đầu trang](#mục-lục)

---

## Phụ Lục

### Glossary

**Acquisition Function**: Hàm quyết định điểm tiếp theo cần thử trong Bayesian Optimization, cân bằng exploration và exploitation.

**BLX-α (Blend Crossover)**: Phương pháp crossover cho continuous parameters, tạo offspring trong range mở rộng của parents.

**Categorical Parameter**: Tham số có giá trị rời rạc không có thứ tự (ví dụ: kernel=['rbf', 'linear', 'poly']).

**Continuous Parameter**: Tham số có giá trị liên tục trong một khoảng (ví dụ: C=(0.1, 100.0)).

**Convergence**: Trạng thái khi thuật toán không còn cải thiện đáng kể, gần đạt optimal solution.

**Cross-Validation (CV)**: Kỹ thuật đánh giá model bằng cách chia data thành k folds và train/test trên các folds khác nhau.

**Crossover**: Operator trong GA kết hợp genes từ hai parents để tạo offspring.

**Diversity**: Độ đo sự khác biệt giữa các individuals trong population (GA).

**Early Stopping**: Kỹ thuật dừng thuật toán sớm khi không còn cải thiện để tiết kiệm thời gian.

**Elitism**: Chiến lược giữ lại các individuals tốt nhất qua các generations (GA).

**Encoding**: Quá trình chuyển đổi tham số thành dạng gene representation (GA).

**Expected Improvement (EI)**: Acquisition function đo expected improvement so với best observation hiện tại.

**Exploration**: Tìm kiếm ở các vùng chưa được khám phá của search space.

**Exploitation**: Tập trung tìm kiếm ở vùng đã biết có performance tốt.

**Fitness Score**: Điểm đánh giá chất lượng của một individual (GA).

**Gaussian Process (GP)**: Mô hình xác suất dùng làm surrogate model trong Bayesian Optimization.

**Generation**: Một iteration trong Genetic Algorithm, tạo ra population mới từ population cũ.

**Hyperparameter**: Tham số của model không được học từ data mà phải thiết lập trước training.

**Individual**: Một giải pháp (tổ hợp tham số) trong population (GA).

**Mutation**: Operator trong GA thêm random changes vào genes để duy trì diversity.

**Population**: Tập hợp các individuals trong một generation (GA).

**Selection**: Operator trong GA chọn parents để tạo offspring.

**Surrogate Model**: Mô hình xấp xỉ hàm mục tiêu thực, dùng trong Bayesian Optimization.

**Tournament Selection**: Phương pháp selection chọn winner từ một nhóm individuals ngẫu nhiên (GA).

**Upper Confidence Bound (UCB)**: Acquisition function cộng mean prediction với uncertainty.

### References

#### Papers

1. **Grid Search**:
   - Bergstra, J., & Bengio, Y. (2012). "Random Search for Hyper-Parameter Optimization". Journal of Machine Learning Research.

2. **Genetic Algorithm**:
   - Holland, J. H. (1992). "Adaptation in Natural and Artificial Systems". MIT Press.
   - Goldberg, D. E. (1989). "Genetic Algorithms in Search, Optimization, and Machine Learning". Addison-Wesley.

3. **Bayesian Optimization**:
   - Snoek, J., Larochelle, H., & Adams, R. P. (2012). "Practical Bayesian Optimization of Machine Learning Algorithms". NIPS.
   - Shahriari, B., et al. (2016). "Taking the Human Out of the Loop: A Review of Bayesian Optimization". Proceedings of the IEEE.

#### Documentation

- **scikit-learn GridSearchCV**: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GridSearchCV.html
- **scikit-optimize**: https://scikit-optimize.github.io/stable/
- **DEAP (Genetic Algorithms)**: https://deap.readthedocs.io/

#### Books

- "Hands-On Machine Learning with Scikit-Learn, Keras, and TensorFlow" by Aurélien Géron
- "Python Machine Learning" by Sebastian Raschka
- "Bayesian Optimization" by Roman Garnett

### FAQ

#### Q1: Thuật toán nào nhanh nhất?

**A**: Phụ thuộc vào context:
- **Bayesian Search** nhanh nhất với ít evaluations (< 50)
- **Genetic Algorithm** tốt cho medium evaluations (100-1000)
- **Grid Search** có thể nhanh nếu parallel tốt và space nhỏ

#### Q2: Làm sao biết khi nào dừng GA?

**A**: Sử dụng early stopping với:
- `patience=5`: Dừng sau 5 generations không cải thiện
- `convergence_threshold=0.001`: Dừng khi improvement < 0.001
- Monitor diversity: Nếu < 0.05, inject diversity hoặc dừng

#### Q3: Grid Search có thể parallel không?

**A**: Có, Grid Search parallel rất tốt:
```python
strategy = GridSearchStrategy(n_jobs=-1)  # Sử dụng tất cả cores
```

#### Q4: Bayesian Search có reproducible không?

**A**: Có, nếu set `random_state`:
```python
strategy = BayesianSearchStrategy(random_state=42)
```

#### Q5: GA cần bao nhiêu generations?

**A**: Phụ thuộc vào problem:
- Simple: 10-20 generations
- Medium: 30-50 generations
- Complex: 50-100 generations
- Sử dụng early stopping để tự động dừng

#### Q6: Làm sao chọn acquisition function?

**A**:
- **EI (Expected Improvement)**: Mặc định, cân bằng tốt
- **UCB**: Khi muốn explore nhiều hơn
- **PI (Probability of Improvement)**: Khi muốn exploit nhiều hơn

#### Q7: Cache có ảnh hưởng gì?

**A**: Cache giúp:
- Tránh re-evaluate cùng params
- Tiết kiệm 20-50% thời gian khi chạy nhiều lần
- Hữu ích cho GA và Grid Search

#### Q8: Nên dùng bao nhiêu CV folds?

**A**:
- **Small dataset (< 1000)**: cv=5 hoặc cv=10
- **Medium dataset (1000-10000)**: cv=5
- **Large dataset (> 10000)**: cv=3
- Trade-off: Nhiều folds → chính xác hơn nhưng chậm hơn

#### Q9: Làm sao tối ưu thời gian chạy?

**A**:
1. Giảm CV folds (cv=3 thay vì cv=5)
2. Sử dụng subset data cho initial search
3. Enable caching
4. Parallel execution (n_jobs=-1)
5. Early stopping
6. Giảm search space

#### Q10: Có thể kết hợp các thuật toán không?

**A**: Có, ví dụ:
```python
# Stage 1: GA để tìm vùng promising
ga_best = ga_strategy.search(model, large_param_grid, X, y)

# Stage 2: Grid Search chi tiết quanh GA best
refined_grid = create_refined_grid(ga_best)
final_best = grid_strategy.search(model, refined_grid, X, y)
```

---

## Kết Luận

Tài liệu này đã trình bày chi tiết ba thuật toán tìm kiếm siêu tham số trong HAutoML:

1. **Grid Search**: Toàn diện, đơn giản, phù hợp không gian nhỏ
2. **Genetic Algorithm**: Linh hoạt, hiệu quả, phù hợp không gian lớn
3. **Bayesian Search**: Thông minh, nhanh, phù hợp không gian phức tạp

Mỗi thuật toán có ưu nhược điểm riêng. Việc lựa chọn phụ thuộc vào:
- Kích thước search space
- Loại parameters (categorical vs continuous)
- Budget evaluations
- Thời gian có sẵn
- Yêu cầu reproducibility

Hy vọng tài liệu này giúp bạn hiểu rõ và sử dụng hiệu quả các thuật toán trong HAutoML!

[⬆️ Về đầu trang](#mục-lục)

---

**Tài liệu được tạo bởi**: HAutoML Team  
**Phiên bản**: 1.0  
**Ngày cập nhật**: 2024  
**License**: MIT
