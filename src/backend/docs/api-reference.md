# API Reference

HAutoML cung cấp REST API qua FastAPI với hai phiên bản: V1 (đồng bộ) và V2 (phân tán qua Kafka).

## Thông tin chung

- **Base URL**: `http://{HOST_BACK_END}:{PORT_BACK_END}` (mặc định `http://0.0.0.0:9999`)
- **Auth**: JWT token qua `Authorization: Bearer <token>` hoặc Google OAuth 2.0
- **Content-Type**: `application/json` (trừ endpoints upload file)

---

## Authentication

### POST /login

Đăng nhập bằng username/email và password. Trả về JWT token.

```json
{
  "username": "user_or_email",
  "password": "password"
}
```

### POST /signup

Đăng ký tài khoản mới.

```json
{
  "username": "string",
  "email": "string",
  "password": "string",
  "gender": "string",
  "date": "string",
  "number": "string",
  "fullName": "string"
}
```

### GET /login/google

Redirect đến Google OAuth 2.0 login.

### GET /auth

Callback URL cho Google OAuth.

### POST /forgot_password/{email}

Gửi email reset password.

### POST /send_email/{username}

Gửi OTP xác thực email.

### POST /verification_email/{username}?otp={otp}

Xác thực email bằng OTP.

---

## User Management

### GET /users

Lấy danh sách tất cả users (role = "user").

### GET /users/?username={username}

Lấy thông tin 1 user theo username.

### PUT /update/{username}

Cập nhật thông tin user.

### DELETE /delete/{username}

Xóa user.

---

## Dataset Management

### POST /get-list-data-by-userid

Lấy danh sách datasets của user.

**Body**: `id` (string) - User ID

### GET /get-data-info?id={dataset_id}

Lấy thông tin chi tiết 1 dataset.

### POST /upload-dataset

Upload dataset mới lên MinIO.

**Form Data**:
- `user_id` (string)
- `data_name` (string)
- `data_type` (string)
- `file_data` (file) - CSV hoặc Excel

### PUT /update-dataset/{dataset_id}

Cập nhật dataset.

### DELETE /delete-dataset/{dataset_id}

Xóa dataset khỏi MinIO và MongoDB.

### GET /get-list-data-user

Lấy tất cả datasets (admin).

---

## Training (V1 - Đồng bộ)

### POST /training-file-local

Huấn luyện từ file CSV và file config YAML.

**Form Data**:
- `file_data` (file) - CSV data
- `file_config` (file) - YAML config

**Config YAML format**:

```yaml
choose: "new model"
list_feature: ["feature1", "feature2"]
target: "label"
metric_sort: "accuracy"
search_algorithm: "grid_search"  # grid_search, bayesian_search, genetic_algorithm
```

**Response**:

```json
{
  "best_model_id": 0,
  "best_model": "RandomForestClassifier()",
  "best_params": {"n_estimators": 100, "max_depth": 10},
  "best_score": 0.95,
  "orther_model_scores": [...]
}
```

### POST /train-from-requestbody-json/?userId={id}&id_data={id}

Huấn luyện từ JSON request body. Lưu kết quả vào MongoDB.

**Body** (Item schema):

```json
{
  "data": [{"col1": 1, "col2": "a", ...}],
  "config": {
    "choose": "new model",
    "list_feature": ["col1", "col2"],
    "target": "label",
    "metric_sort": "accuracy",
    "search_algorithm": "bayesian_search"
  }
}
```

---

## Training (V2 - Phân tán)

Prefix: `/v2/auto`

### GET /v2/auto/features?id_data={id}&problem_type={type}

Lấy danh sách features và gợi ý target cho dataset.

### GET /v2/auto/data?id_data={id}

Lấy preview dữ liệu của dataset.

### POST /v2/auto/jobs/training

Gửi job huấn luyện phân tán qua Kafka.

**Body** (InputRequest):

```json
{
  "id_data": "mongodb_object_id",
  "id_user": "mongodb_object_id",
  "config": {
    "choose": "new_model",
    "metric_sort": "accuracy",
    "list_feature": ["feature1", "feature2"],
    "problem_type": "classification",
    "search_algorithm": "bayesian_search",
    "target": "Revenue"
  }
}
```

**Luồng xử lý**:
1. Lưu job vào MongoDB (status: pending)
2. Gửi message vào Kafka topic
3. Consumer nhận message → cache dataset vào MinIO → tạo tasks
4. Workers polling tasks → huấn luyện → submit kết quả
5. Master tổng hợp → lưu best model vào MinIO → cập nhật MongoDB

### GET /v2/auto/jobs?id_user={id}

Lấy danh sách jobs của user.

---

## Inference

### POST /inference-model

Chạy dự đoán trên dữ liệu mới bằng mô hình đã huấn luyện.

**Form Data**:
- `job_id` (string) - ID của job đã hoàn thành
- `user_id` (string)
- `file_data` (file) - CSV dữ liệu mới

---

## Model Management

### POST /activate-model?job_id={id}&activate={0|1}

Kích hoạt/vô hiệu hóa mô hình.

### POST /get-list-job-by-userId

Lấy danh sách jobs của user.

**Body**: `user_id` (string)

### POST /get-job-info

Lấy thông tin chi tiết 1 job.

**Body**: `id` (string) - Job ID

---

## Internal APIs (Master-Worker)

Các API nội bộ cho giao tiếp giữa Master và Worker nodes.

### GET /task/get?worker_url={url}&cached_key_hint={key}

Worker polling để nhận task. Master trả về task phù hợp theo cache affinity.

### POST /task/submit

Worker gửi kết quả huấn luyện về Master.

```json
{
  "job_id": "string",
  "model_name": "RandomForestClassifier",
  "worker_url": "http://worker1:8000",
  "success": true,
  "score": 0.95,
  "best_params": {},
  "scores": {},
  "model": {
    "bucket_name": "temp",
    "object_name": "task_id.pkl"
  }
}
```

---

## Supported Models

### Classification

Định nghĩa trong `assets/system_models/classification.yml`:
- RandomForestClassifier
- DecisionTreeClassifier
- SVC
- KNeighborsClassifier
- LogisticRegression
- GaussianNB

### Regression

Định nghĩa trong `assets/system_models/regression.yml`:
- LinearRegression
- DecisionTreeRegressor
- RandomForestRegressor
- GradientBoostingRegressor
- XGBRegressor

---

## Error Handling

Tất cả endpoints trả về HTTP status codes chuẩn:

| Status | Mô tả |
|--------|-------|
| 200 | Thành công |
| 400 | Request không hợp lệ |
| 401 | Token không hợp lệ hoặc hết hạn |
| 403 | Không có quyền truy cập |
| 404 | Không tìm thấy resource |
| 500 | Lỗi server |
