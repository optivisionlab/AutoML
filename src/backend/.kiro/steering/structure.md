---
inclusion: always
---

# Cấu Trúc Dự Án

## Cấp Gốc

- `app.py`: Ứng dụng FastAPI chính với tất cả API endpoints
- `worker.py`: Worker node phân tán để huấn luyện mô hình
- `experiment.py`: API router v2 thử nghiệm với huấn luyện phân tán
- `kafka_consumer.py`: Kafka consumer để xử lý job bất đồng bộ
- `requirements.txt`: Các thư viện Python phụ thuộc

## Module Chính

### `automl/`
Engine AutoML và các chiến lược tìm kiếm

- `engine.py`: Logic huấn luyện cốt lõi, tiền xử lý dữ liệu, lựa chọn mô hình
- `model.py`: Pydantic models cho API requests
- `demo_gradio.py`: Giao diện Gradio UI
- `search/`: Triển khai các chiến lược tìm kiếm
  - `factory/`: Factory pattern để tạo strategy
  - `strategy/`: Base class và các strategy cụ thể (grid, genetic, bayesian)
- `v2/`: Hệ thống huấn luyện phân tán thử nghiệm
  - `distributed.py`: Triển khai MapReduce cho huấn luyện song song
  - `schemas.py`: Request/response models
  - `service.py`: Business logic cho v2 APIs
  - `minio.py`: Tích hợp MinIO storage

### `data/`
Quản lý dataset

- `engine.py`: Các thao tác CRUD dataset
- `uci.py`: Tích hợp UCI ML Repository
- `get_dataset.py`: Tiện ích lấy dataset

### `database/`
Lớp cơ sở dữ liệu

- `database.py`: Thiết lập kết nối MongoDB
- `get_dataset.py`: Truy vấn dataset

### `users/`
Quản lý người dùng và xác thực

- `engine.py`: CRUD người dùng, xác thực, OAuth, quản lý mật khẩu

### `assets/`
Cấu hình và dữ liệu mẫu

- `system_models/model.yml`: Cấu hình mô hình ML
- `config-data-iris.yaml`: Cấu hình huấn luyện mẫu
- `iris.data.csv`: Dataset mẫu
- `desc.md`: Mô tả dự án (tiếng Việt)
- `end_users/`: Tài liệu người dùng cuối
- `online_shoppers/`: Dataset mẫu

## Docker Files

- `hautoml.toolkit.dockerfile`: Image API server chính
- `hautoml.nano.dockerfile`: Image Gradio demo
- `worker.dockerfile`: Image worker node
- `docker-compose.yaml`: Điều phối multi-container
- `worker.docker-compose.yaml`: Compose riêng cho worker

## Quy Ước Quan Trọng

### API Endpoints

- `/training-file-local`: Huấn luyện với file upload
- `/training-file-mongodb`: Huấn luyện với dữ liệu MongoDB
- `/train-from-requestbody-json/`: Huấn luyện với JSON payload
- `/v2/auto/*`: APIs huấn luyện phân tán thử nghiệm

### Database Collections

- `tbl_Job`: Các job huấn luyện và kết quả
- `tbl_Data`: Dataset của người dùng
- `tbl_User`: Tài khoản người dùng
- `file_csv`, `file_yaml`: Lưu trữ file cũ (legacy)

### Định Dạng Cấu Hình

YAML configs phải bao gồm:
- `choose`: "new model" hoặc ID mô hình để train lại
- `list_feature`: Tên các cột đặc trưng
- `target`: Tên cột mục tiêu
- `metric_sort`: Metric chính để chọn mô hình
- `search_algorithm`: "grid", "genetic", hoặc "bayesian" (tùy chọn, mặc định "grid")

### Phong Cách Code

- Async/await cho các thao tác I/O
- Chuyển đổi kiểu numpy sang Python native trước khi JSON serialization
- Factory pattern cho các component có thể mở rộng
- Xử lý lỗi với FastAPI HTTPException
- Comment và message tiếng Việt cho nội dung người dùng
