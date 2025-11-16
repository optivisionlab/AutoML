---
inclusion: always
---

# Luồng Hoạt Động Hệ Thống

## Tổng Quan Kiến Trúc

HAutoML sử dụng kiến trúc microservices với các thành phần chính:
- **API Server** (app.py): Xử lý request từ client
- **Worker Nodes** (worker.py): Thực hiện huấn luyện mô hình
- **Kafka**: Message queue để xử lý bất đồng bộ
- **MongoDB**: Lưu trữ dữ liệu, job, người dùng
- **MinIO**: Lưu trữ object (dataset, model)

## Luồng 1: Huấn Luyện Đồng Bộ (Training Synchronous)

### Endpoint: `/training-file-local` hoặc `/train-from-requestbody-json/`

```
Client → API Server → Training Engine → Trả kết quả ngay
```

**Chi tiết:**

1. **Client gửi request** với:
   - Dữ liệu (CSV file hoặc JSON)
   - Cấu hình (YAML hoặc JSON config)

2. **API Server nhận request** (`app.py`):
   - Validate dữ liệu đầu vào
   - Parse config: `list_feature`, `target`, `metric_sort`, `search_algorithm`

3. **Gọi `train_process()`** (`automl/engine.py`):
   - **Tiền xử lý dữ liệu**: `preprocess_data()`
     - Encode categorical features (LabelEncoder)
     - Chuẩn hóa features (StandardScaler)
     - Tách X (features) và y (target)
   
   - **Lấy danh sách models**: `get_model()`
     - Đọc từ `assets/system_models/model.yml`
     - Load các model: DecisionTree, RandomForest, SVM, KNN, LogisticRegression, GaussianNB
   
   - **Chọn phiên bản model**: `choose_model_version()`
     - "new model": Train tất cả models
     - ID cụ thể: Train lại model đó

4. **Gọi `training()`** (`automl/engine.py`):
   - **Tạo Search Strategy**: `SearchStrategyFactory.create_strategy()`
     - Grid Search: Tìm kiếm toàn diện
     - Genetic Algorithm: Tìm kiếm nhanh với thuật toán di truyền
     - Bayesian Search: Tìm kiếm thông minh với Bayesian Optimization
   
   - **Duyệt qua từng model**:
     - Lấy model và param_grid
     - Gọi `strategy.search()` để tìm siêu tham số tốt nhất
     - Cross-validation với cv=5
     - Tính toán metrics: accuracy, precision, recall, f1
     - Chuyển đổi numpy types sang Python native types
   
   - **Chọn model tốt nhất**:
     - So sánh theo `metric_sort`
     - Lưu best_model, best_params, best_score

5. **Lưu kết quả vào MongoDB** (`tbl_Job`):
   - Serialize model bằng pickle
   - Lưu thông tin: job_id, best_model, best_params, best_score, model_scores
   - Lưu metadata: user, dataset, config, timestamp

6. **Trả kết quả về Client**:
   - best_model_id, best_model, best_params, best_score
   - orther_model_scores (điểm của các model khác)

## Luồng 2: Huấn Luyện Bất Đồng Bộ với Kafka (Training Asynchronous)

### Endpoint: `/v2/auto/jobs/training`

```
Client → API Server → Kafka → Consumer → Training → MongoDB
                         ↓
                    Trả job_id ngay
```

**Chi tiết:**

1. **Client gửi request** (`InputRequest`):
   - `id_data`: ID dataset trong MongoDB
   - `config`: Cấu hình huấn luyện

2. **API Server** (`experiment.py`):
   - Tạo job_id mới (UUID)
   - Lưu job vào MongoDB với `status=0` (pending)
   - Gửi message vào Kafka topic `train-job-topic`
   - **Trả về job_id ngay lập tức** (không chờ training)

3. **Kafka Consumer** (`kafka_consumer.py`):
   - Lắng nghe topic `train-job-topic`
   - Nhận message chứa job_id và config
   - Gọi `train_json_from_job()` để xử lý

4. **Training Process**:
   - Lấy job từ MongoDB theo job_id
   - Kiểm tra status (nếu đã train thì bỏ qua)
   - Thực hiện training tương tự Luồng 1
   - Cập nhật job với `status=1` (completed)

5. **Client kiểm tra kết quả**:
   - Gọi `/v2/auto/jobs/offset/{id_user}` để xem danh sách job
   - Gọi `/get-job-info` với job_id để xem chi tiết

## Luồng 3: Huấn Luyện Phân Tán (Distributed Training)

### Endpoint: `/v2/auto/distributed/mongodb`

```
Client → API Server → MapReduce Coordinator
                           ↓
                    ┌──────┼──────┐
                    ↓      ↓      ↓
                Worker1 Worker2 Worker3
                    ↓      ↓      ↓
                    └──────┼──────┘
                           ↓
                    Reduce Results → Client
```

**Chi tiết:**

1. **Client gửi request**:
   - `id_data`: ID dataset
   - `config`: Cấu hình huấn luyện

2. **API Server** (`experiment.py`):
   - Gọi `process_async()` từ `automl/v2/distributed.py`

3. **MapReduce Coordinator** (`distributed.py`):
   
   **Phase 1 - MAP:**
   - Lấy danh sách models từ `assets/system_models/model.yml`
   - **Chia models** thành N phần (N = số worker):
     - `split_models()`: Chia đều models cho các worker
     - Đánh số lại ID từ 0 cho mỗi phần
   
   - **Gửi song song** đến các worker:
     - Sử dụng `asyncio.gather()` để gửi đồng thời
     - Mỗi worker nhận: models_part, metrics, id_data, config
     - Worker URL: `http://HOST:PORT+i` (ví dụ: 4000, 4001, 4002)

4. **Worker Node** (`worker.py`):
   - Nhận request tại endpoint `/train`
   - Lấy dataset từ MongoDB theo `id_data`
   - Ánh xạ model name sang class (MODEL_MAPPING)
   - Gọi `train_process()` để train models_part
   - Serialize best_model thành base64
   - Trả về: best_model (base64), best_score, model_scores

5. **MapReduce Coordinator** (`distributed.py`):
   
   **Phase 2 - REDUCE:**
   - Nhận kết quả từ tất cả workers
   - `reduce_async()`:
     - Gộp tất cả model_scores từ các worker
     - So sánh best_score từ các worker
     - Chọn model có score cao nhất
     - Decode best_model từ base64
     - Đánh số lại model_id cho toàn bộ danh sách

6. **Lưu kết quả**:
   - Lưu vào MongoDB (`tbl_Job`)
   - Lưu model binary vào MinIO
   - Trả kết quả về client

## Luồng 4: Dự Đoán với Model (Inference)

### Endpoint: `/inference-model/`

```
Client → API Server → Load Model → Predict → Client
```

**Chi tiết:**

1. **Client gửi request**:
   - `job_id`: ID của job đã train
   - `file_data`: CSV file chứa dữ liệu cần dự đoán

2. **API Server** (`automl/engine.py`):
   - Lấy job từ MongoDB theo `job_id`
   - Kiểm tra `activate=1` (model đã được kích hoạt)
   - Deserialize model từ binary (pickle.loads)

3. **Tiền xử lý dữ liệu**:
   - Đọc CSV file
   - Encode categorical features (LabelEncoder)
   - Lấy các features theo `list_feature` từ config

4. **Dự đoán**:
   - Gọi `model.predict(X)`
   - Thêm cột "predict" vào dataframe

5. **Trả kết quả**:
   - Convert dataframe sang JSON
   - Trả về dữ liệu với cột dự đoán

## Luồng 5: Quản Lý Dataset

### Upload Dataset: `/upload-dataset`

```
Client → API Server → MinIO → MongoDB (metadata)
```

1. Client upload file CSV
2. API Server lưu file vào MinIO bucket
3. Lưu metadata vào MongoDB (`tbl_Data`):
   - dataName, dataType, user_id
   - MinIO path: bucket_name, object_name
   - Timestamp

### Get Dataset: `/get-data-from-mongodb-to-train`

```
Client → API Server → MinIO (file) → Parse → Format → Client
```

1. Client gửi `id_data`
2. Lấy metadata từ MongoDB
3. Lấy file từ MinIO
4. Parse CSV thành DataFrame
5. Format theo chuẩn AutoML
6. Trả về: data (JSON), list_feature

## Luồng 6: Xác Thực Người Dùng

### Login Local: `/login`

```
Client → API Server → MongoDB → JWT Token → Client
```

1. Client gửi username, password
2. Kiểm tra trong MongoDB (`tbl_User`)
3. Hash password và so sánh
4. Tạo JWT token
5. Trả về token và thông tin user

### Login Google OAuth: `/login_google`

```
Client → Google OAuth → Callback → API Server → MongoDB → Client
```

1. Client click "Login with Google"
2. Redirect đến Google OAuth
3. Google xác thực và callback về `/auth`
4. Lưu user info vào session
5. Lưu/cập nhật user trong MongoDB

## Các Thành Phần Quan Trọng

### SearchStrategyFactory
- Tạo strategy dựa trên tên: "grid", "genetic", "bayesian"
- Hỗ trợ nhiều alias: "ga", "GA", "skopt"
- Trả về instance của strategy tương ứng

### Search Strategies
- **GridSearchStrategy**: Tìm kiếm toàn bộ không gian tham số
- **GeneticAlgorithm**: Sử dụng thuật toán di truyền (population, generations)
- **BayesianSearchStrategy**: Sử dụng Bayesian Optimization (skopt)

### Type Conversion
- Tất cả numpy types phải convert sang Python native trước khi JSON serialization
- Sử dụng `SearchStrategy.convert_numpy_types()` để đảm bảo

### Error Handling
- Sử dụng FastAPI HTTPException
- Status codes: 400 (Bad Request), 404 (Not Found), 500 (Internal Error)
- Message tiếng Việt cho người dùng

## Monitoring và Logging

- Kafka consumer log các message nhận được
- Training process log từng bước
- Worker health check: `/health` endpoint
- Job status tracking trong MongoDB
