# Tài liệu API Backend

Tài liệu này mô tả các endpoint REST của backend HAutoML (FastAPI). Khi backend đang chạy, bạn cũng có thể xem tài liệu tương tác tại `http://localhost:<BACKEND_PORT>/docs` (Swagger UI).

## Thông tin chung

- **URL cơ sở**: `http://localhost:9996/api/v1` (cổng lấy từ biến `BACKEND_PORT`). Mọi đường dẫn bên dưới đều tương đối so với `/api/v1`.
- **Health check**: `GET /` (không có tiền tố `/api/v1`) trả về tên dự án, phiên bản, môi trường và trạng thái.
- **Xác thực**: gửi header `Authorization: Bearer <access_token>` cho mọi endpoint, trừ các endpoint trong nhóm [Xác thực](#1-xac-thuc-auth) được ghi chú là công khai. Refresh token được lưu thêm trong cookie `HttpOnly`.
- **Phân quyền**: `admin` được truy cập mọi tài nguyên; `user` chỉ truy cập tài nguyên của chính mình (`owner`).

### Định dạng response

Mọi response thành công đều có dạng:

```json
{
  "success": true,
  "message": "Success",
  "data": {},
  "meta": null
}
```

Các endpoint trả về danh sách có thêm `meta` để phân trang. Có hai kiểu phân trang:

=== "Theo trang (`page`)"

    Dùng cho datasets, users, inference jobs/models.

    ```json
    "meta": { "total_items": 42, "current_page": 1, "page_size": 10, "total_pages": 5 }
    ```

=== "Theo offset (`offset`/`limit`)"

    Dùng cho notifications.

    ```json
    "meta": { "offset": 0, "limit": 10, "total_items": 42, "has_more": true }
    ```

### Mã lỗi

| Status | `error_code` | Ý nghĩa |
|--------|--------------|---------|
| 400 | `BAD_REQUEST` | Request không hợp lệ |
| 401 | `UNAUTHORIZED` | Thiếu, sai hoặc hết hạn token |
| 403 | `FORBIDDEN` | Không đủ quyền (ví dụ cần `admin`) |
| 404 | `NOT_FOUND` | Không tìm thấy tài nguyên |
| 422 | `VALIDATION_ERROR` | Dữ liệu gửi lên không qua kiểm tra |
| 500 | `INTERNAL_SERVER_ERROR` | Lỗi phía máy chủ |

---

## 1. Xác thực (Auth) { #1-xac-thuc-auth }

Tiền tố: `/auth`

| Method | Đường dẫn | Mô tả | Yêu cầu token |
|--------|-----------|-------|:---:|
| POST | `/auth/signup` | Đăng ký tài khoản, gửi email xác thực | Không |
| POST | `/auth/login` | Đăng nhập, nhận `access_token` và `refresh_token` | Không |
| POST | `/auth/refresh` | Cấp lại cặp token từ `refresh_token` | Không |
| GET | `/auth/me` | Thông tin tài khoản hiện tại | Có |
| POST | `/auth/logout` | Đăng xuất (xóa cookie refresh token) | Có |
| POST | `/auth/google` | Bắt đầu luồng đăng nhập Google OAuth2 | Không |
| GET | `/auth/google/callback` | URL callback để Google chuyển hướng về | Không |
| POST | `/auth/verifications` | Xác thực email (đổi token xác thực lấy token đăng nhập) | Không |
| POST | `/auth/token/verifications` | Gửi lại email xác thực dạng liên kết | Không |
| POST | `/auth/otp/verifications` | Gửi lại email xác thực dạng OTP | Không |
| POST | `/auth/forgot-password` | Yêu cầu đặt lại mật khẩu, gửi OTP qua email | Không |
| POST | `/auth/verify-otp` | Kiểm tra OTP, trả về token đặt lại mật khẩu | Không |
| POST | `/auth/reset-password` | Đặt mật khẩu mới bằng token | Không |

### `POST /auth/signup`

```json
{
  "username": "holmes",
  "email": "user@example.com",
  "gender": "male",
  "date": "01/01/2026",
  "number": "486909281",
  "fullName": "Sherlock Holmes",
  "password": "abc@123"
}
```

Ràng buộc: `username` tối thiểu 3 ký tự, `number` tối thiểu 10 ký tự, `email` đúng định dạng. Trả về `201` cùng thông tin người dùng.

### `POST /auth/login`

```json
{ "username": "holmes", "password": "abc@123" }
```

Response `data`: `{ "access_token": "...", "refresh_token": "...", "token_type": "bearer" }`.

### Các body khác

| Endpoint | Body |
|----------|------|
| `/auth/refresh` | `{ "refresh_token": "..." }` |
| `/auth/verifications` | `{ "token": "..." }` |
| `/auth/token/verifications`, `/auth/otp/verifications` | `{ "email": "user@example.com" }` |
| `/auth/forgot-password` | `{ "email": "user@example.com" }` |
| `/auth/verify-otp` | `{ "email": "user@example.com", "otp": "123456" }` (OTP đúng 6 ký tự) |
| `/auth/reset-password` | `{ "token": "...", "new_password": "...", "confirm_password": "..." }` (mật khẩu mới tối thiểu 6 ký tự) |

---

## 2. Người dùng (Users)

Tiền tố: `/users`. `{id}` là ID người dùng.

| Method | Đường dẫn | Quyền | Mô tả |
|--------|-----------|-------|-------|
| GET | `/users` | admin | Danh sách người dùng (`page`, `page_size` ≤ 100) |
| GET | `/users/{id}` | owner/admin | Chi tiết người dùng |
| PUT | `/users/{id}` | owner/admin | Cập nhật hồ sơ |
| DELETE | `/users/{id}` | admin | Xóa người dùng |
| GET | `/users/{id}/avatar` | owner/admin | Tải ảnh đại diện (stream) |
| POST | `/users/{id}/avatar` | owner/admin | Tải lên ảnh đại diện (`multipart/form-data`, trường `file`) |
| POST | `/users/{id}/password` | owner/admin | Đổi mật khẩu |

`PUT /users/{id}` – các trường đều tùy chọn:

```json
{ "fullName": "Tên đầy đủ", "gender": "male", "date": "01/01/2026", "number": "0123456789" }
```

`gender` chỉ nhận `male`, `female` hoặc `other`.

`POST /users/{id}/password`:

```json
{ "old_password": "abc@123", "new_password": "newpass123" }
```

Sau khi đổi mật khẩu thành công, người dùng cần đăng nhập lại.

---

## 3. Tập dữ liệu (Datasets)

Tiền tố: `/datasets`. `{id}` là ID tập dữ liệu. Tất cả endpoint đều yêu cầu token.

| Method | Đường dẫn | Mô tả |
|--------|-----------|-------|
| GET | `/datasets` | Danh sách tập dữ liệu của người dùng hiện tại |
| GET | `/datasets/default` | Danh sách tập dữ liệu công khai (`public = true`) |
| GET | `/datasets/all` | Tất cả tập dữ liệu của mọi người dùng (**admin**) |
| GET | `/datasets/metrics` | Danh sách metric theo loại bài toán |
| POST | `/datasets` | Tải lên tập dữ liệu mới |
| GET | `/datasets/{id}` | Siêu dữ liệu của một tập dữ liệu |
| PUT | `/datasets/{id}` | Cập nhật siêu dữ liệu / ảnh đại diện |
| DELETE | `/datasets/{id}` | Xóa tập dữ liệu |
| GET | `/datasets/{id}/features` | Danh sách cột/đặc trưng của tập dữ liệu |
| GET | `/datasets/{id}/data` | Xem trước dữ liệu (`num_rows`, mặc định 50) |
| POST | `/datasets/{id}/training` | Tạo job huấn luyện trên tập dữ liệu |
| POST | `/datasets/database/connect` | Kiểm tra kết nối CSDL ngoài, lấy danh sách bảng |
| POST | `/datasets/database/table-info` | Xem cấu trúc và dữ liệu mẫu của một bảng |
| POST | `/datasets/database/import` | Nhập một bảng CSDL thành tập dữ liệu |

### Tham số truy vấn của danh sách

`GET /datasets`, `/datasets/default` và `/datasets/all` dùng chung:

| Tham số | Mặc định | Mô tả |
|---------|----------|-------|
| `current_page` | 1 | Trang hiện tại |
| `page_size` | 10 | Số bản ghi mỗi trang (1–100) |
| `data_type` | – | Lọc theo `table`, `image` hoặc `text` |
| `sort_name` | – | `asc` (A–Z) hoặc `desc` (Z–A) |
| `sort_time` | `desc` | `desc` (mới nhất) hoặc `asc` (cũ nhất) |

### `POST /datasets`

`multipart/form-data` gồm:

| Trường | Bắt buộc | Mô tả |
|--------|:---:|-------|
| `file` | Có | File dữ liệu |
| `dataName` | Có | Tên tập dữ liệu |
| `dataType` | Có | `table`, `image` hoặc `text` |
| `description` | Không | Mô tả |
| `public` | Không | `true` để chia sẻ công khai (mặc định `false`) |
| `thumbnail_file` | Không | Ảnh đại diện của tập dữ liệu (lưu trên Backblaze) |

### `PUT /datasets/{id}`

`multipart/form-data`, mọi trường đều tùy chọn: `dataName`, `description`, `public`, `thumbnail_file`. Endpoint này chỉ cập nhật siêu dữ liệu và ảnh đại diện, không thay thế file dữ liệu.

### `GET /datasets/metrics`

Tham số `problem_type`: `classification` (mặc định), `regression` hoặc `time_series`. Response `data`:

```json
{ "problem_type": "regression", "metrics": ["mse", "mae", "mape", "r2"] }
```

### `POST /datasets/{id}/training`

Tạo một job huấn luyện, ghi metadata vào MongoDB và đẩy tác vụ vào hàng đợi Kafka. Worker (`src.kafka_consumer`) sẽ nhận và thực hiện. Xem [Phương pháp khoa học](scientific_approach.md) để biết pipeline xử lý.

```json
{
  "choose": null,
  "timeout": 600,
  "metric_sort": "accuracy",
  "list_feature": ["f1", "f2", "f3"],
  "problem_type": "classification",
  "search_algorithm": "tpe_search",
  "target": "label"
}
```

| Trường | Bắt buộc | Mô tả |
|--------|:---:|-------|
| `problem_type` | Có | `classification`, `regression` hoặc `time_series` |
| `target` | Có | Tên cột mục tiêu |
| `list_feature` | Có | Danh sách cột đặc trưng đầu vào |
| `metric_sort` | Có | Metric dùng để xếp hạng mô hình (xem `/datasets/metrics`) |
| `search_algorithm` | Không | `grid_search`, `random_search`, `bayesian_search`, `genetic_algorithm`, `tpe_search` (mặc định `tpe_search`). Xem [Tối ưu siêu tham số](hpo.md) |
| `timeout` | Không | Thời gian tối đa (giây) cho tác vụ huấn luyện |
| `choose` | Không | Lựa chọn bổ sung của giao diện huấn luyện |

Với `problem_type = time_series`, không cần thêm tham số: cột thời gian và các lag được tự động chọn từ dữ liệu. Xem [Dự báo chuỗi thời gian](time_series.md).

Response `data`: `{ "job_id": "..." }`. Tiến trình và kết quả được báo qua [thông báo](#5-thong-bao-notifications-notifications) và `GET /inference/jobs`.

### Kết nối CSDL ngoài

Hỗ trợ 12 loại: `postgres`, `mysql`, `sqlite`, `mssql`, `snowflake`, `bigquery`, `duckdb`, `clickhouse`, `oracle`, `trino`, `hive`, `redshift`.

Ba endpoint `database/*` dùng chung các trường kết nối:

| Trường | Bắt buộc | Mô tả |
|--------|:---:|-------|
| `db_type` | Có | Loại CSDL (danh sách ở trên) |
| `database` | Có | Tên CSDL, đường dẫn file, hoặc `:memory:` (SQLite/DuckDB) |
| `host` | Không | Mặc định `localhost` |
| `port` | Không | Tự điền theo từng loại CSDL |
| `user`, `password` | Không | Thông tin đăng nhập |
| `schema_name` | Không | Ví dụ `public`, `analytics` |
| `extra_params` | Không | Tham số riêng của từng CSDL (bảng dưới) |

| CSDL | `extra_params` |
|------|----------------|
| Snowflake | `account`, `warehouse`, `role` |
| MSSQL | `driver` (tên ODBC driver), `trust_server_certificate` |
| Oracle | `service_name`, `sid` |
| BigQuery | `cred_file_path` (đường dẫn file service account JSON) |
| Hive | `auth` |

Các trường bổ sung:

- `POST /datasets/database/connect`: không có trường thêm. Response chứa trạng thái kết nối và `tables: [...]`.
- `POST /datasets/database/table-info`: thêm `table_name` (bắt buộc) và `limit` (1–100, mặc định 10) – số dòng xem trước.
- `POST /datasets/database/import`: thêm `table_name` (bắt buộc), `data_name` (bắt buộc), `description`, `public`. Dữ liệu được trích xuất thành Parquet, lưu vào MinIO và đăng ký vào MongoDB; response là siêu dữ liệu của tập dữ liệu mới.

---

## 4. Suy luận & Triển khai mô hình (Inference)

Tiền tố: `/inference`. `{id}` là ID của **job huấn luyện** (cũng chính là ID mô hình). Tất cả endpoint đều yêu cầu token; `admin` xem được job của mọi người dùng.

| Method | Đường dẫn | Mô tả |
|--------|-----------|-------|
| GET | `/inference/jobs` | Danh sách tất cả job huấn luyện |
| POST | `/inference/jobs/{id}/cancel` | Hủy job đang huấn luyện |
| GET | `/inference/models` | Danh sách mô hình đang được kích hoạt (`activate = 1`) |
| PUT | `/inference/models/{id}/activation` | Kích hoạt / hủy kích hoạt mô hình |
| GET | `/inference/models/{id}/deployment` | Thông tin triển khai và code mẫu |
| POST | `/inference/models/{id}/predict` | Dự đoán thời gian thực (JSON) |
| POST | `/inference/models/{id}/predict/file` | Dự đoán hàng loạt từ file CSV/Excel, tải về kết quả |
| GET | `/inference/models/{id}/export/notebook` | Xuất Jupyter Notebook (`.ipynb`) |
| GET | `/inference/models/{id}/export/docker` | Xuất gói Docker microservice (`.zip`) |
| GET | `/inference/models/{id}/export/model` | Tải file mô hình thô (`.pkl`) |

`GET /inference/jobs` và `/inference/models` nhận `current_page`, `page_size`, `sort_name`, `sort_time` giống danh sách dataset. Mỗi phần tử có: `status`, `activate`, `data`, `user`, `config`, `best_model`, `best_score`, `best_params`, `create_at`...

Trạng thái job (`status`): `0` đang huấn luyện, `1` thành công, `-1` thất bại.

### `PUT /inference/models/{id}/activation`

```json
{ "activate": 1 }
```

`1` triển khai API dự đoán, `0` gỡ triển khai. Response là thông tin triển khai (xem bên dưới).

### `GET /inference/models/{id}/deployment`

Response `data` gồm: `job_id`, `dataset_id`, `model_name`, `status`, `activate`, `best_score`, `endpoint_url`, `features`, `features_schema` (tên, kiểu dữ liệu, giá trị mẫu), `sample_payload` và `code_snippets` (`curl`, `python`, `javascript`, `csharp`, `php`) để gọi API chỉ với một lần sao chép.

### `POST /inference/models/{id}/predict`

Mô hình phải đang ở trạng thái `activate = 1`, nếu không API trả về `403`. Mỗi bản ghi phải có đủ các cột trong `list_feature` của job, nếu thiếu API trả về `400`. Với mô hình `time_series`, mỗi bản ghi chứa cột thời gian của các mốc cần dự báo, xem [Dự báo chuỗi thời gian](time_series.md#du-doan).

```json
{
  "data": [
    { "f1": 5.1, "f2": 3.5, "f3": 1.4 },
    { "f1": 6.2, "f2": 2.9, "f3": 4.3 }
  ]
}
```

Response `data`:

```json
{
  "job_id": "...",
  "model_name": "RandomForestClassifier",
  "predictions": ["a", "b"],
  "latency_ms": 12.4,
  "total_samples": 2
}
```

### `POST /inference/models/{id}/predict/file`

`multipart/form-data` với trường `file` (CSV hoặc Excel). Response là file gốc kèm cột dự đoán mới, trả về dạng tải xuống.

---

## 5. Thông báo (Notifications) { #5-thong-bao-notifications-notifications }

Tiền tố: `/notifications`. Hệ thống tạo thông báo khi job huấn luyện bắt đầu, thành công hoặc thất bại. Thông báo vừa được lưu vào MongoDB, vừa được đẩy realtime qua MQTT (xem [Kiến trúc](architecture.md#thong-bao-realtime-mqtt)).

| Method | Đường dẫn | Mô tả |
|--------|-----------|-------|
| GET | `/notifications` | Tất cả thông báo của người dùng |
| GET | `/notifications/unread` | Chỉ thông báo chưa đọc |
| PUT | `/notifications/{notification_id}/read` | Đánh dấu đã đọc |

Tham số truy vấn: `offset` (mặc định 0), `limit` (1–50, mặc định 10).

Mỗi thông báo gồm: `id`, `job_id`, `status` (`1` thành công, `-1` thất bại, `0` đang huấn luyện), `message`, `metadata`, `is_read`, `created_at`.

---

## 6. Các mô hình được hỗ trợ

Danh sách mô hình, lưới siêu tham số và metric mặc định nằm trong các file cấu hình `src/backend/assets/{classification,regression,time_series}.yml`. Thêm mô hình mới bằng cách khai báo trong file YAML và đăng ký lớp ở `modules/models/registry.py`.

| Loại bài toán | Mô hình |
|---------------|---------|
| `classification` | DecisionTreeClassifier, RandomForestClassifier, KNeighborsClassifier, SVC, LogisticRegression, GaussianNB |
| `regression` | LinearRegression, DecisionTreeRegressor, RandomForestRegressor, GradientBoostingRegressor, KNeighborsRegressor, Ridge, Lasso, SVR |
| `time_series` | Ridge, RandomForestRegressor, GradientBoostingRegressor (dự báo một bước) |

Metric theo loại bài toán:

| Loại bài toán | Metric |
|---------------|--------|
| `classification` | `accuracy`, `balanced_accuracy`, `precision_macro`, `precision_weighted`, `recall_macro`, `recall_weighted`, `f1_macro`, `f1_weighted` |
| `regression` | `mse`, `mae`, `mape`, `r2` |
| `time_series` | `mse`, `mae`, `rmse`, `r2` |
