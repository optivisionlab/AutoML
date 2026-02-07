# HAutoML Documentation

Chào mừng đến với tài liệu HAutoML - Hệ thống AutoML tự động tối ưu hóa siêu tham số.

## Giới thiệu

HAutoML (Hierarchical Automated Machine Learning) là một nền tảng AutoML mã nguồn mở được phát triển bởi OptiVisionLab tại Trường Công nghệ Thông tin và Truyền thông, Đại học Công nghiệp Hà Nội.

Hệ thống hỗ trợ:

- **Classification** và **Regression**: Tự động tiền xử lý, huấn luyện và đánh giá mô hình
- **Bayesian Optimization**: Tối ưu hóa siêu tham số bằng Gaussian Process
- **Genetic Algorithm**: Thuật toán di truyền cho tìm kiếm siêu tham số
- **Grid Search**: Tìm kiếm toàn diện trong không gian tham số
- **Distributed Training**: Huấn luyện phân tán qua Kafka và hệ thống Worker

## Tài liệu

| Tài liệu | Mô tả |
|----------|-------|
| [Design Patterns](design-patterns.md) | Các design pattern được sử dụng trong hệ thống |
| [Search Algorithms](search-algorithms.md) | Chi tiết về các thuật toán tìm kiếm |
| [API Reference](api-reference.md) | Tài liệu REST API endpoints |

## Bắt đầu nhanh

### Cài đặt

```bash
pip install -r requirements.txt
```

### Chạy server

```bash
python app.py
# hoặc
uvicorn app:app --host 0.0.0.0 --port 9999 --reload
```

### Sử dụng Search Strategy

```python
from automl.search.factory import SearchStrategyFactory
from sklearn.ensemble import RandomForestClassifier

# Tạo strategy
strategy = SearchStrategyFactory.create_strategy('bayesian', {
    'n_calls': 25,
    'cv': 5
})

# Định nghĩa không gian tham số
param_grid = {
    'n_estimators': [50, 100, 200],
    'max_depth': [5, 10, 15]
}

# Thực thi tìm kiếm
best_params, best_score, all_scores, cv_results = strategy.search(
    model=RandomForestClassifier(),
    param_grid=param_grid,
    X=X_train,
    y=y_train
)
```

### Huấn luyện qua API (V1 - Đồng bộ)

```bash
curl -X POST http://localhost:9999/training-file-local \
  -F "file_data=@data.csv" \
  -F "file_config=@config.yml"
```

### Huấn luyện qua API (V2 - Phân tán qua Kafka)

```bash
curl -X POST http://localhost:9999/v2/auto/jobs/training \
  -H "Content-Type: application/json" \
  -d '{
    "id_data": "...",
    "id_user": "...",
    "config": {
      "choose": "new_model",
      "metric_sort": "accuracy",
      "list_feature": ["feature1", "feature2"],
      "problem_type": "classification",
      "search_algorithm": "bayesian_search",
      "target": "label"
    }
  }'
```

## Cấu trúc dự án

```
├── app.py                         # FastAPI entry point + lifespan management
├── experiment.py                  # V2 API router (/v2/auto/*)
├── kafka_consumer.py              # Kafka consumer + producer cho async jobs
│
├── automl/                        # Core AutoML engine
│   ├── engine.py                  # Training orchestration (classification + regression)
│   ├── model.py                   # Pydantic models (Item)
│   ├── process_classification.py  # Classification preprocessing pipeline
│   ├── process_regression.py      # Regression preprocessing pipeline
│   ├── search/                    # Hyperparameter search strategies
│   │   ├── factory/
│   │   │   └── search_strategy_factory.py  # Factory Pattern
│   │   └── strategy/
│   │       ├── base.py                          # Abstract base class + normalize_param_grid
│   │       ├── base_config.yml                  # Cấu hình cơ sở
│   │       ├── grid_search.py                   # Grid Search
│   │       ├── grid_search_config.yml           # Cấu hình Grid Search
│   │       ├── bayesian_search.py               # Bayesian Optimization
│   │       ├── bayesian_search_config.yml       # Cấu hình Bayesian
│   │       ├── genetic_algorithm.py             # Genetic Algorithm
│   │       ├── genetic_algorithm_config.yml     # Cấu hình GA
│   │       └── *_default_config.yml             # Fallback configs
│   └── v2/                        # V2 distributed training
│       ├── master.py              # Job orchestration, task queuing, heartbeat monitor
│       ├── service.py             # Job persistence + Kafka messaging
│       ├── minio.py               # MinIO storage wrapper
│       └── schemas.py             # V2 request/response schemas
│
├── data/                          # Data handling
│   ├── engine.py                  # Dataset CRUD + MinIO upload
│   └── uci.py                     # UCI dataset integration
│
├── database/                      # Database layer
│   ├── database.py                # MongoDB async connection
│   └── get_dataset.py             # Dataset retrieval + preprocessing
│
├── users/                         # User management
│   └── engine.py                  # Auth, JWT, OAuth, user CRUD
│
├── cluster/                       # Distributed worker
│   └── worker.py                  # Worker node (polling, LRU cache, task execution)
│
└── assets/
    ├── system_models/             # Model definitions (classification.yml, regression.yml)
    └── end_users/                 # Sample configs
```

## Kiến trúc tổng quan

```
┌─────────────┐     ┌──────────────────────┐     ┌──────────────┐
│   Client    │────▶│  FastAPI + OAuth 2.0  │────▶│ Apache Kafka │
└─────────────┘     └──────────────────────┘     └──────┬───────┘
                                                        │
                    ┌───────────────────────────────────┘
                    ▼
            ┌───────────────┐     ┌─────────────────┐
            │  Master Node  │────▶│  Priority Queue  │
            │  (Coordinator)│     │  (Global/Local)  │
            └───────┬───────┘     └────────┬────────┘
                    │                      │
        ┌───────────┼──────────────────────┘
        │           │           │
        ▼           ▼           ▼
   ┌─────────┐ ┌─────────┐ ┌─────────┐
   │Worker 1 │ │Worker 2 │ │Worker N │
   │(LRU     │ │         │ │         │
   │ Cache)  │ │         │ │         │
   └────┬────┘ └────┬────┘ └────┬────┘
        │           │           │
        └───────────┼───────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
  ┌───────────┐          ┌───────────┐
  │  MongoDB  │          │   MinIO   │
  │ (Jobs,    │          │ (Models,  │
  │  Users)   │          │  Datasets,│
  └───────────┘          │  Cache)   │
                         └───────────┘
```

## Tech Stack

| Thành phần | Công nghệ |
|-----------|-----------|
| API Framework | FastAPI + Uvicorn |
| ML | scikit-learn 1.5.1, scikit-optimize 0.10.2, XGBoost 3.1.2 |
| Data | pandas 2.2.2, numpy 1.26.2 |
| Database | MongoDB (pymongo 4.10.1) |
| Object Storage | MinIO (minio 7.2.18) |
| Message Queue | Apache Kafka (aiokafka 0.12.0) |
| Auth | Authlib 1.5.2, PyJWT 2.10.1 |
| Config | PyYAML 6.0.2, python-dotenv 1.1.1 |
| Demo UI | Gradio |
