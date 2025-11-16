---
inclusion: always
---

# Công Nghệ Sử Dụng

## Công Nghệ Cốt Lõi

- **Python**: 3.10.12
- **Web Framework**: FastAPI 0.115.12 với Uvicorn
- **Thư Viện ML**: scikit-learn 1.5.1, scikit-optimize 0.10.2
- **Xử Lý Dữ Liệu**: pandas 2.2.2, numpy 1.26.2
- **Giao Diện**: Gradio 5.25.2

## Hạ Tầng

- **Cơ Sở Dữ Liệu**: MongoDB 4.10.1 (pymongo)
- **Message Queue**: Apache Kafka (kafka-python 2.2.10, aiokafka 0.12.0)
- **Object Storage**: MinIO 7.2.18
- **Containerization**: Docker & Docker Compose
- **Xác Thực**: Authlib 1.5.2, PyJWT 2.10.1

## Mẫu Kiến Trúc

- **Factory Pattern**: Tạo chiến lược tìm kiếm (`SearchStrategyFactory`)
- **Strategy Pattern**: Thuật toán tìm kiếm có thể thay thế (Grid, Genetic, Bayesian)
- **MapReduce**: Huấn luyện mô hình phân tán trên các worker
- **Async/Await**: I/O không chặn với asyncio và httpx

## Cấu Trúc Dự Án

```
automl/          # Engine AutoML và các chiến lược tìm kiếm
data/            # Xử lý dataset và tích hợp UCI
database/        # Kết nối MongoDB và truy vấn
users/           # Quản lý người dùng và xác thực
assets/          # File cấu hình và dữ liệu mẫu
```

## Lệnh Thường Dùng

### Phát Triển

```bash
# Khởi động API server chính
python app.py

# Khởi động worker node
python worker.py

# Khởi động Gradio demo
python automl/demo_gradio.py
```

### Docker

```bash
# Build và chạy với Docker Compose
docker-compose up -d

# Build từng image riêng lẻ
docker build -f hautoml.toolkit.dockerfile -t hautoml-toolkit .
docker build -f hautoml.nano.dockerfile -t hautoml-nano .
docker build -f worker.dockerfile -t workers .
```

### Kiểm Thử

```bash
# Chạy experiment API
python experiment.py

# Test tái tạo kết quả
python test_reproduction.py
```

## Cấu Hình

- `.config.yml`: Cấu hình chính (ports, hosts, OAuth, Kafka, MongoDB)
- `assets/system_models/model.yml`: Định nghĩa mô hình ML và siêu tham số
- `assets/config-data-iris.yaml`: Cấu hình huấn luyện mẫu

## Thư Viện Quan Trọng

- **Thuật Toán Tìm Kiếm**: Grid Search (toàn diện), Genetic Algorithm (nhanh), Bayesian Search (hiệu quả)
- **Serialization**: pickle cho models, PyYAML cho configs
- **Định Dạng Dữ Liệu**: CSV, Parquet (fastparquet, pyarrow)
