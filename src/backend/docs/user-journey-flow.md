# Luồng Hành Trình Người Dùng - HAutoML

## Tổng Quan

Tài liệu này mô tả chi tiết hành trình của người dùng từ khi truy cập hệ thống đến khi nhận được kết quả từ AutoML.

---

## 🎯 Kịch Bản 1: Người Dùng Mới - Training Model Lần Đầu

### Bước 1: Đăng Nhập Hệ Thống

**Hành động người dùng:**
```
1. Truy cập: http://localhost:3000
2. Click nút "Đăng nhập"
3. Chọn phương thức:
   - Option A: Nhập username/password
   - Option B: Click "Login with Google"
```

**Luồng xử lý:**
```
User → Web UI → POST /login → API Server
                              ↓
                         MongoDB (tbl_User)
                              ↓
                         Verify credentials
                              ↓
                         Generate JWT token
                              ↓
User ← Web UI ← Response {token, user_info}
```

**Response nhận được:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "507f1f77bcf86cd799439011",
    "username": "user123",
    "email": "user@example.com",
    "role": "User"
  }
}
```

**Thời gian:** < 1 giây

---

### Bước 2: Upload Dataset

**Hành động người dùng:**
```
1. Click menu "Datasets" → "Upload Dataset"
2. Điền form:
   - Tên dataset: "Iris Flowers"
   - Loại: "Classification"
   - Chọn file: iris.csv
3. Click "Upload"
```

**Luồng xử lý:**
```
User → Web UI → POST /upload-dataset (FormData)
                              ↓
                         API Server
                              ↓
                    ┌────────┴────────┐
                    ↓                 ↓
              MinIO Storage      MongoDB (tbl_Data)
              (Lưu file CSV)     (Lưu metadata)
                    ↓                 ↓
                    └────────┬────────┘
                             ↓
User ← Web UI ← Response {dataset_id, success}
```

**Request gửi đi:**
```http
POST /upload-dataset
Content-Type: multipart/form-data

user_id: 507f1f77bcf86cd799439011
data_name: Iris Flowers
data_type: Classification
file_data: [binary CSV data]
```

**Response nhận được:**
```json
{
  "success": true,
  "dataset_id": "65a1b2c3d4e5f6789abcdef0",
  "message": "Dataset uploaded successfully"
}
```

**Thời gian:** 2-5 giây (tùy kích thước file)

---

### Bước 3: Xem Features của Dataset

**Hành động người dùng:**
```
1. Click vào dataset vừa upload
2. Xem danh sách features
```

**Luồng xử lý:**
```
User → Web UI → GET /v2/auto/features?id_data={id}
                              ↓
                         API Server
                              ↓
                    MongoDB (Get metadata)
                              ↓
                    MinIO (Get CSV file)
                              ↓
                    Parse CSV → Extract columns
                              ↓
User ← Web UI ← Response {features: [...]}
```

**Response nhận được:**
```json
{
  "features": [
    "sepal_length",
    "sepal_width", 
    "petal_length",
    "petal_width",
    "species"
  ]
}
```

**Thời gian:** 1-2 giây

---

### Bước 4: Cấu Hình Training

**Hành động người dùng:**
```
1. Click "Train Model"
2. Chọn features:
   ☑ sepal_length
   ☑ sepal_width
   ☑ petal_length
   ☑ petal_width
3. Chọn target: species
4. Chọn metric: accuracy
5. Chọn algorithm: bayesian
6. Click "Start Training"
```

**Config được tạo:**
```json
{
  "choose": "new model",
  "list_feature": [
    "sepal_length",
    "sepal_width",
    "petal_length",
    "petal_width"
  ],
  "target": "species",
  "metric_sort": "accuracy",
  "search_algorithm": "bayesian"
}
```

---

### Bước 5: Gửi Request Training (Bất Đồng Bộ)

**Luồng xử lý:**
```
User → Web UI → POST /v2/auto/jobs/training
                              ↓
                         API Server
                              ↓
                    Tạo job_id (UUID)
                              ↓
                    MongoDB (Insert job, status=0)
                              ↓
                    Kafka (Send message)
                              ↓
User ← Web UI ← Response {job_id} (NGAY LẬP TỨC)
```

**Request gửi đi:**
```json
{
  "id_data": "65a1b2c3d4e5f6789abcdef0",
  "config": {
    "choose": "new model",
    "list_feature": ["sepal_length", "sepal_width", "petal_length", "petal_width"],
    "target": "species",
    "metric_sort": "accuracy",
    "search_algorithm": "bayesian"
  }
}
```

**Response nhận được (< 1 giây):**
```json
{
  "status": "success",
  "message": "Training job initiated successfully",
  "job_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**UI hiển thị:**
```
✅ Training đã bắt đầu!
Job ID: 550e8400-e29b-41d4-a716-446655440000
⏳ Đang xử lý... (có thể mất vài phút)
```

---

### Bước 6: Background Processing (Kafka Consumer)

**Luồng xử lý (không thấy bởi user):**
```
Kafka Consumer → Nhận message
                      ↓
                MongoDB (Get job)
                      ↓
                Get dataset từ MinIO
                      ↓
            ┌─────────┴─────────┐
            ↓                   ↓
    Preprocess Data      Load Models
    (LabelEncoder,       (6 models từ
     StandardScaler)      model.yml)
            ↓                   ↓
            └─────────┬─────────┘
                      ↓
            Create Search Strategy
            (BayesianSearchStrategy)
                      ↓
        ┌─────────────┼─────────────┐
        ↓             ↓             ↓
   Model 1       Model 2       Model 3
   (DTree)       (RForest)     (SVM)
        ↓             ↓             ↓
   Search        Search        Search
   best params   best params   best params
        ↓             ↓             ↓
   CV=5          CV=5          CV=5
   (25 calls)    (25 calls)    (25 calls)
        ↓             ↓             ↓
        └─────────────┼─────────────┘
                      ↓
            Chọn model tốt nhất
                      ↓
            pickle.dumps(model)
                      ↓
        MongoDB (Update job, status=1)
```

**Thời gian:** 30 giây - 5 phút (tùy dataset & algorithm)

---

### Bước 7: Polling - Kiểm Tra Kết Quả

**Hành động người dùng:**
```
UI tự động refresh mỗi 5 giây
hoặc user click "Refresh"
```

**Luồng xử lý:**
```
User → Web UI → GET /get-job-info?id={job_id}
                              ↓
                         API Server
                              ↓
                    MongoDB (Query job)
                              ↓
                    Check status
                              ↓
                ┌───────────┴───────────┐
                ↓                       ↓
          status = 0              status = 1
          (Pending)               (Completed)
                ↓                       ↓
User ← "⏳ Đang xử lý..."    "✅ Hoàn thành!" + Results
```

**Response khi đang xử lý:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": 0,
  "create_at": 1699123456.789,
  "message": "Training in progress"
}
```

**Response khi hoàn thành:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": 1,
  "best_model_id": "2",
  "best_model": "RandomForestClassifier(max_depth=10, n_estimators=100)",
  "best_score": 0.9733,
  "best_params": {
    "max_depth": 10,
    "n_estimators": 100,
    "min_samples_split": 2
  },
  "model_scores": [
    {
      "model_id": 0,
      "model_name": "DecisionTreeClassifier",
      "scores": {"accuracy": 0.9533, "f1": 0.9521}
    },
    {
      "model_id": 1,
      "model_name": "RandomForestClassifier",
      "scores": {"accuracy": 0.9733, "f1": 0.9728}
    },
    {
      "model_id": 2,
      "model_name": "SVC",
      "scores": {"accuracy": 0.9667, "f1": 0.9655}
    }
  ],
  "create_at": 1699123456.789,
  "user": {
    "id": "507f1f77bcf86cd799439011",
    "name": "user123"
  },
  "data": {
    "id": "65a1b2c3d4e5f6789abcdef0",
    "name": "Iris Flowers"
  }
}
```

---

### Bước 8: Xem Kết Quả Chi Tiết

**UI hiển thị:**
```
╔════════════════════════════════════════════════════════╗
║           🎉 TRAINING HOÀN THÀNH!                      ║
╠════════════════════════════════════════════════════════╣
║                                                        ║
║  🏆 Best Model: RandomForestClassifier                 ║
║  📊 Best Score: 0.9733 (97.33%)                        ║
║                                                        ║
║  ⚙️ Best Parameters:                                   ║
║     • max_depth: 10                                    ║
║     • n_estimators: 100                                ║
║     • min_samples_split: 2                             ║
║                                                        ║
╠════════════════════════════════════════════════════════╣
║  📈 All Model Scores:                                  ║
║                                                        ║
║  1. RandomForestClassifier    97.33% ⭐                ║
║  2. SVC                        96.67%                  ║
║  3. DecisionTreeClassifier     95.33%                  ║
║  4. KNeighborsClassifier       94.67%                  ║
║  5. LogisticRegression         93.33%                  ║
║  6. GaussianNB                 92.00%                  ║
║                                                        ║
╠════════════════════════════════════════════════════════╣
║  [Kích hoạt Model]  [Download Model]  [Dự đoán]       ║
╚════════════════════════════════════════════════════════╝
```

---

## 🔮 Kịch Bản 2: Sử Dụng Model Để Dự Đoán

### Bước 1: Kích Hoạt Model

**Hành động người dùng:**
```
1. Vào trang "My Jobs"
2. Chọn job đã train
3. Click "Kích hoạt Model"
```

**Luồng xử lý:**
```
User → Web UI → POST /activate-model
                              ↓
                         API Server
                              ↓
                MongoDB (Update activate=1)
                              ↓
User ← Web UI ← Response {success}
```

**Request:**
```http
POST /activate-model?job_id=550e8400-e29b-41d4-a716-446655440000&activate=1
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "cập nhập trạng thái mô hình thành công",
  "activate": 1
}
```

---

### Bước 2: Upload Dữ Liệu Cần Dự Đoán

**Hành động người dùng:**
```
1. Click "Dự đoán"
2. Upload file CSV mới (test_data.csv)
```

**File test_data.csv:**
```csv
sepal_length,sepal_width,petal_length,petal_width
5.1,3.5,1.4,0.2
6.2,2.9,4.3,1.3
7.3,2.9,6.3,1.8
```

---

### Bước 3: Gửi Request Inference

**Luồng xử lý:**
```
User → Web UI → POST /inference-model/
                              ↓
                         API Server
                              ↓
                MongoDB (Get job & model)
                              ↓
                Check activate = 1
                              ↓
                pickle.loads(model)
                              ↓
                Read & Preprocess CSV
                              ↓
                model.predict(X)
                              ↓
                Add "predict" column
                              ↓
User ← Web UI ← Response {data with predictions}
```

**Request:**
```http
POST /inference-model/?job_id=550e8400-e29b-41d4-a716-446655440000
Content-Type: multipart/form-data

file_data: [test_data.csv]
```

**Response:**
```json
[
  {
    "sepal_length": 5.1,
    "sepal_width": 3.5,
    "petal_length": 1.4,
    "petal_width": 0.2,
    "predict": "setosa"
  },
  {
    "sepal_length": 6.2,
    "sepal_width": 2.9,
    "petal_length": 4.3,
    "petal_width": 1.3,
    "predict": "versicolor"
  },
  {
    "sepal_length": 7.3,
    "sepal_width": 2.9,
    "petal_length": 6.3,
    "petal_width": 1.8,
    "predict": "virginica"
  }
]
```

**Thời gian:** 1-3 giây

---

### Bước 4: Xem & Download Kết Quả

**UI hiển thị:**
```
╔═══════════════════════════════════════════════════════════╗
║              🔮 KẾT QUẢ DỰ ĐOÁN                           ║
╠═══════════════════════════════════════════════════════════╣
║                                                           ║
║  Model: RandomForestClassifier                            ║
║  Job ID: 550e8400-e29b-41d4-a716-446655440000             ║
║                                                           ║
╠═══════════════════════════════════════════════════════════╣
║                                                           ║
║  📊 Bảng Kết Quả:                                         ║
║                                                           ║
║  ┌────────┬────────┬────────┬────────┬────────────────┐  ║
║  │ S_Len  │ S_Wid  │ P_Len  │ P_Wid  │ Prediction     │  ║
║  ├────────┼────────┼────────┼────────┼────────────────┤  ║
║  │ 5.1    │ 3.5    │ 1.4    │ 0.2    │ setosa         │  ║
║  │ 6.2    │ 2.9    │ 4.3    │ 1.3    │ versicolor     │  ║
║  │ 7.3    │ 2.9    │ 6.3    │ 1.8    │ virginica      │  ║
║  └────────┴────────┴────────┴────────┴────────────────┘  ║
║                                                           ║
╠═══════════════════════════════════════════════════════════╣
║  [💾 Download CSV]  [📋 Copy to Clipboard]  [🔄 Dự đoán mới] ║
╚═══════════════════════════════════════════════════════════╝
```

---

## 📊 Tổng Hợp Thời Gian Xử Lý

| Bước | Hành động | Thời gian | Loại |
|------|-----------|-----------|------|
| 1 | Đăng nhập | < 1s | Đồng bộ |
| 2 | Upload dataset | 2-5s | Đồng bộ |
| 3 | Xem features | 1-2s | Đồng bộ |
| 4 | Cấu hình training | - | Client-side |
| 5 | Gửi training request | < 1s | Bất đồng bộ |
| 6 | Training (background) | 30s-5m | Background |
| 7 | Polling kết quả | < 1s/lần | Đồng bộ |
| 8 | Kích hoạt model | < 1s | Đồng bộ |
| 9 | Inference | 1-3s | Đồng bộ |

**Tổng thời gian từ upload đến có model:** 1-6 phút

---

## 🔄 Luồng Xử Lý Lỗi

### Lỗi 1: Dataset Không Hợp Lệ

```
User upload file → API validate
                        ↓
                   File không phải CSV
                        ↓
User ← Error: "File phải là định dạng CSV"
```

### Lỗi 2: Model Chưa Kích Hoạt

```
User request inference → API check activate
                              ↓
                         activate = 0
                              ↓
User ← Error: "Model chưa được kích hoạt"
```

### Lỗi 3: Training Thất Bại

```
Kafka Consumer → Training
                      ↓
                 Exception xảy ra
                      ↓
            MongoDB (Update status=-1)
                      ↓
User polling → Response: "Training failed"
```

---

## 💡 Tips Cho Người Dùng

### Chọn Search Algorithm

- **Grid Search**: Dùng khi có ít tham số (< 50 combinations)
- **Genetic Algorithm**: Dùng khi cần kết quả nhanh
- **Bayesian Search**: Dùng khi dataset lớn, training chậm

### Chọn Metric

- **Accuracy**: Dùng khi classes cân bằng
- **F1**: Dùng khi classes không cân bằng
- **Precision**: Quan trọng với False Positive
- **Recall**: Quan trọng với False Negative

### Tối Ưu Thời Gian

1. Dùng training bất đồng bộ cho dataset lớn
2. Chọn Genetic Algorithm nếu cần nhanh
3. Giảm số features nếu có thể
4. Sử dụng distributed training cho nhiều models
