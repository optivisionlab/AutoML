# Phương pháp khoa học & Cách tiếp cận kỹ thuật

## Giới thiệu

HAutoML là một nền tảng **Automated Machine Learning (AutoML)** được thiết kế để tự động hóa toàn bộ quy trình xây dựng mô hình học máy. Tài liệu này mô tả các phương pháp khoa học, chiến lược kỹ thuật và cách tiếp cận được sử dụng trong hệ thống.

## 1. Quá trình AutoML toàn quy trình

### 1.1 Pipeline xử lý tự động

HAutoML thực hiện tự động hóa các giai đoạn chính của pipeline học máy:

```
Dữ liệu thô → Tiền xử lý → Lựa chọn mô hình & Tuning → Mô hình tối ưu → Suy luận (Inference)
```

#### Giai đoạn 1: Tiền xử lý dữ liệu (Data Preprocessing)

**a) Phát hiện kiểu dữ liệu (Feature Type Detection)**

Hệ thống tự động phân loại từng cột dữ liệu thành các loại:
- **Dữ liệu số (Numeric)**: Detects sử dụng `pd.api.types.is_numeric_dtype()`
- **Dữ liệu phân loại (Categorical)**: Các cột có số lượng giá trị độc lập nhỏ
- **Dữ liệu văn bản (Text)**: Các cột có số lượng giá trị độc lập lớn (vượt quá ngưỡng cardinality)

**b) Xử lý giá trị thiếu (Missing Value Imputation)**

- **Dữ liệu số**: Sử dụng trung vị (median) - phương pháp robust với outlier
- **Dữ liệu phân loại**: Sử dụng giá trị xuất hiện nhiều nhất (mode)

**c) Chuẩn hóa dữ liệu (Normalization & Scaling)**

- **Dữ liệu số**: Áp dụng `StandardScaler` để chuẩn hóa (mean=0, std=1)
- **Dữ liệu phân loại**: Sử dụng `OneHotEncoder` với `sparse_output=True`
- **Dữ liệu văn bản**: Sử dụng `TfidfVectorizer` để chuyển đổi thành vector số

**d) Pipeline xử lý (Preprocessing Pipeline)**

Hệ thống sử dụng `scikit-learn Pipeline` và `ColumnTransformer` để:
- Áp dụng các phép biến đổi phù hợp cho từng loại dữ liệu
- Đảm bảo tính nhất quán giữa dữ liệu huấn luyện và kiểm tra
- Tránh data leakage bằng cách fit trên training set và transform trên cả training/test set

```python
numeric_transformer = Pipeline([
    ('imputer', SimpleImputer(strategy='median')),
    ('scaler', StandardScaler())
])

categorical_transformer = Pipeline([
    ('imputer', SimpleImputer(strategy='most_frequent')),
    ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=True))
])

text_transformer = Pipeline([
    ('tfidf', TfidfVectorizer(...))
])

preprocessor = ColumnTransformer(transformers=[
    ('num', numeric_transformer, numeric_cols),
    ('cat', categorical_transformer, categorical_cols),
    ('text', text_transformer, text_cols)
])
```

#### Giai đoạn 2: Lựa chọn mô hình & Tinh chỉnh siêu tham số (Hyperparameter Tuning)

**a) Chiến lược tìm kiếm siêu tham số**

Hệ thống sử dụng các chiến lược khác nhau để tìm kiếm sự kết hợp siêu tham số tốt nhất:
- **Grid Search**: Tìm kiếm toàn bộ không gian siêu tham số được xác định trước
- **Random Search**: Lấy mẫu ngẫu nhiên từ không gian siêu tham số
- **Hybrid approaches**: Kết hợp các phương pháp để cân bằng hiệu suất và thời gian

**b) Kiểm định chéo (Cross-Validation)**

Sử dụng k-fold cross-validation (mặc định k=5) để đánh giá hiệu suất mô hình trên từng fold:

$$\text{CV Score} = \frac{1}{k} \sum_{i=1}^{k} \text{Score}_i$$

Điều này giúp:
- Giảm phương sai của đánh giá hiệu suất
- Tận dụng tối đa dữ liệu có sẵn
- Phát hiện overfitting

**c) Chỉ số đánh giá (Evaluation Metrics)**

**Cho bài toán Phân loại (Classification):**
- **Accuracy**: Tỷ lệ dự đoán đúng
- **Precision**: Trong các dự đoán dương tính, bao nhiêu phần trăm là đúng
- **Recall**: Trong các mẫu dương tính thực sự, bao nhiêu phần trăm được phát hiện
- **F1 Score**: Trung bình hài hòa của Precision và Recall
- **Balanced Accuracy**: Trung bình của recall cho từng lớp (hữu ích với dữ liệu mất cân bằng)

$$\text{F1} = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$$

$$\text{Balanced Accuracy} = \frac{1}{K} \sum_{i=1}^{K} \frac{TP_i}{TP_i + FN_i}$$

**Cho bài toán Hồi quy (Regression):**
- **MAE (Mean Absolute Error)**: Sai số tuyệt đối trung bình
- **MSE (Mean Squared Error)**: Bình phương sai số trung bình
- **RMSE (Root Mean Squared Error)**: Căn bậc hai của MSE
- **R² (Coefficient of Determination)**: Phần trăm phương sai được giải thích

$$\text{MAE} = \frac{1}{n} \sum_{i=1}^{n} |y_i - \hat{y}_i|$$

$$\text{R}^2 = 1 - \frac{\sum_{i=1}^{n} (y_i - \hat{y}_i)^2}{\sum_{i=1}^{n} (y_i - \bar{y})^2}$$

#### Giai đoạn 3: Lựa chọn mô hình tối ưu (Model Selection)

Sau khi tìm kiếm, hệ thống:
1. So sánh hiệu suất từ các cấu hình khác nhau
2. Chọn mô hình có chỉ số đánh giá cao nhất
3. Lưu trữ mô hình tối ưu và siêu tham số của nó
4. Chuẩn bị cho triển khai và suy luận

## 2. Kiến trúc xử lý bất đồng bộ

### 2.1 Hàng đợi công việc với Apache Kafka

Hệ thống sử dụng Apache Kafka để quản lý hàng đợi công việc huấn luyện:

```
Frontend → Backend → Kafka Queue → Workers → MongoDB (kết quả)
```

**Ưu điểm:**
- **Scalability**: Có thể thêm workers để xử lý song song
- **Reliability**: Nếu worker crash, công việc không bị mất
- **Decoupling**: Frontend không phải chờ công việc huấn luyện hoàn thành
- **Real-time monitoring**: Theo dõi trạng thái công việc real-time

### 2.2 Các trạng thái công việc (Job States)

```
Submitted → Queued → Processing → Completed
                          ↓
                       Failed (retry)
```

**Trạng thái:**
- **Submitted**: Công việc được submittted từ user
- **Queued**: Chờ trong Kafka queue
- **Processing**: Worker đang xử lý
- **Completed**: Hoàn thành thành công
- **Failed**: Có lỗi, có thể retry

## 3. Cơ sở hạ tầng & Lưu trữ

### 3.1 MongoDB - Lưu trữ Metadata

Lưu trữ:
- Thông tin người dùng (users)
- Metadata datasets (tên, kích thước, loại task)
- Kết quả huấn luyện (cấu hình mô hình, chỉ số hiệu suất, siêu tham số)
- Lịch sử công việc

**Schema ví dụ:**
```json
{
  "_id": ObjectId("..."),
  "userId": ObjectId("..."),
  "dataName": "iris",
  "taskType": "classification",
  "models": [
    {
      "modelId": "model_123",
      "algorithm": "RandomForest",
      "hyperparameters": {...},
      "metrics": {
        "accuracy": 0.95,
        "f1_score": 0.94
      },
      "timestamp": "2024-01-15T10:30:00Z"
    }
  ]
}
```

### 3.2 Minio - Lưu trữ Objects

Lưu trữ:
- Datasets (CSV, JSON, v.v.)
- Mô hình serialized (`.pickle`, `.joblib`)
- Preprocessors (để sử dụng lại trong suy luận)

**Cấu trúc bucket:**
```
/datasets/{user_id}/{dataset_id}.csv
/models/{user_id}/{model_id}.pkl
/preprocessors/{user_id}/{model_id}_preprocessor.pkl
```

## 4. Quy trình suy luận (Inference)

Khi người dùng gửi dữ liệu mới để dự đoán:

1. **Tải mô hình & preprocessor** từ Minio
2. **Tiền xử lý dữ liệu mới** sử dụng cùng preprocessor (đảm bảo consistency)
3. **Suy luận** bằng mô hình đã huấn luyện
4. **Trả về kết quả** cho người dùng

```python
# Pseudocode
def inference(model_id, new_data):
    # Load model and preprocessor
    model = load_from_minio(f"models/{user_id}/{model_id}.pkl")
    preprocessor = load_from_minio(f"preprocessors/{user_id}/{model_id}_preprocessor.pkl")
    
    # Preprocess new data
    processed_data = preprocessor.transform(new_data)
    
    # Make prediction
    predictions = model.predict(processed_data)
    
    return predictions
```

## 5. Mở rộng & Hỗ trợ các loại bài toán

### 5.1 Phân loại (Classification)

HAutoML hỗ trợ các mô hình phân loại từ scikit-learn:
- Logistic Regression
- Decision Trees
- Random Forests
- Gradient Boosting
- SVM
- k-NN
- v.v.

### 5.2 Hồi quy (Regression)

Hỗ trợ các mô hình hồi quy:
- Linear Regression
- Ridge/Lasso Regression
- Decision Trees Regressor
- Random Forests Regressor
- Gradient Boosting Regressor
- Support Vector Regression
- v.v.


### 5.3 Dự báo chuỗi thời gian Forecasting

HAutoML hỗ trợ forecasting một bước tiếp theo bằng các mô hình regression của scikit-learn. Bài toán được triển khai theo hướng **reduction to tabular regression**: chuỗi thời gian được chuyển thành bảng đặc trưng `X` và target `y` trước khi huấn luyện.

**a) Tạo đặc trưng theo thời gian**

Từ giá trị target trong quá khứ, hệ thống tạo các lag feature như `lag_1`, `lag_7`, `lag_14`; rolling mean và rolling standard deviation trên các cửa sổ lịch sử; cùng calendar feature như thứ trong tuần, tháng và cờ cuối tuần. Khi dự đoán tại thời điểm *t*, các lag và rolling feature chỉ sử dụng target trước *t*. Target tại *t* và dữ liệu sau *t* không được dùng, nhằm tránh data leakage.

Lag feature được tạo trong `automl/process_forecasting.py`, trước Pipeline. Pipeline nhận bảng feature đã có lag để preprocessing và dự đoán; Pipeline không tự có lịch sử target để tạo `lag_1` hoặc `lag_7` tại thời điểm predict.

**b) Pipeline forecasting**

Sau khi tạo bảng feature, HAutoML xây dựng một `sklearn.pipeline.Pipeline` gồm:

```text
Bảng lag và calendar feature → ColumnTransformer → estimator
```

`ColumnTransformer` xử lý cột số bằng `SimpleImputer` và `StandardScaler`, xử lý cột dạng chữ bằng `SimpleImputer` và `OneHotEncoder`. Bước cuối là model sklearn như Ridge, RandomForestRegressor hoặc GradientBoostingRegressor. Pipeline được fit và đánh giá nguyên vẹn trong mỗi fold, vì vậy preprocessing chỉ học từ train fold và dùng lại quy tắc đó cho test fold.

**c) Đánh giá theo thời gian**

Forecasting dùng `TimeSeriesSplit` thay cho K-Fold. Với mỗi split, model học từ phần dữ liệu quá khứ và được kiểm tra trên phần dữ liệu xảy ra sau đó. `n_splits`, `test_size`, `gap` và `max_train_size` được cấu hình trong hàm `make_cv(...)`. Cách chia này mô phỏng đúng tình huống dự báo thực tế và ngăn việc học tương lai để dự đoán quá khứ.

**d) Tìm siêu tham số**

`GridSearchCV` là baseline, thử toàn bộ các tổ hợp tham số trong `assets/system_models/forecasting.yml`. Vì model nằm ở bước cuối của Pipeline, tham số được truyền theo cú pháp `model__parameter`, ví dụ `model__alpha` hoặc `model__max_depth`.

GA và BO được tái sử dụng từ các strategy có sẵn của HAutoML. Không cần viết lại hai thuật toán này: Pipeline forecasting, param grid và `TimeSeriesSplit` được truyền vào strategy. Do đó cả GridSearchCV, GA và BO đều đánh giá cấu hình bằng quy tắc học ở quá khứ và kiểm tra ở tương lai.

**e) Kiểm thử**

Bộ test forecasting kiểm tra lag/rolling feature không dùng dữ liệu tương lai; dữ liệu thời gian không hợp lệ bị từ chối; Pipeline chỉ fit trên train fold; và GridSearchCV, GA, BO cùng hoạt động với `TimeSeriesSplit`. Lệnh chạy test là:

```bash
PYTHONPATH=. pytest automl/tests/test_forecasting.py -q
```

Phiên bản hiện tại hỗ trợ một chuỗi có mốc thời gian đều, không trùng lặp và dự báo một bước tiếp theo (`horizon = 1`). Multi-step forecasting, nhiều chuỗi độc lập và resampling nằm ngoài phạm vi hiện tại.

## 6. Xử lý dữ liệu mất cân bằng

Để xử lý các tập dữ liệu bị mất cân bằng (imbalanced datasets):

- Sử dụng `balanced_accuracy_score` thay vì accuracy thông thường
- Có thể áp dụng các kỹ thuật như SMOTE, undersampling, hoặc class weighting
- Theo dõi precision, recall, và F1 score riêng cho từng lớp

## 7. Đánh giá và Xác thực Mô hình

### 7.1 Tránh Data Leakage

Hệ thống đảm bảo:
- Preprocessor được fit **chỉ** trên training data
- Cross-validation được thực hiện chính xác (không mix train/test)
- Siêu tham số hỏi được tìm kiếm dựa trên training/validation data, không test data

### 7.2 Đánh giá Generalization

- Sử dụng cross-validation để đánh giá hiệu suất generalization
- Nếu có test set riêng, đánh giá thêm trên test set
- Theo dõi sự khác biệt giữa train score và validation score (overfitting indicator)

## 8. State-of-the-Art & Giới hạn

### 8.1 Điểm mạnh

- ✅ Tự động hóa toàn quy trình
- ✅ Hỗ trợ đa loại dữ liệu (số, phân loại, văn bản)
- ✅ Kiến trúc scalable với xử lý bất đồng bộ
- ✅ Giao diện user-friendly
- ✅ Mã nguồn mở, có thể customize

### 8.2 Giới hạn hiện tại

- 🔸 Chưa hỗ trợ deep learning trực tiếp (chỉ scikit-learn)
- 🔸 Forecasting hiện hỗ trợ một bước tiếp theo, một chuỗi và mốc thời gian đều; chưa hỗ trợ multi-step forecasting hoặc nhiều chuỗi độc lập
- 🔸 Chưa hỗ trợ ensemble methods nâng cao
- 🔸 Thời gian tìm kiếm siêu tham số có thể lâu với không gian tham số lớn

### 8.3 Hướng phát triển tương lai

- Tích hợp TensorFlow/PyTorch cho neural networks
- Mở rộng forecasting sang nhiều bước dự báo, nhiều chuỗi và resampling
- Ensemble methods và stacking
- Auto feature engineering
- Explainability tools (SHAP, LIME)

## Tài liệu tham khảo

- **Scikit-learn Documentation**: https://scikit-learn.org/
- **Scikit-learn Pipeline**: https://scikit-learn.org/stable/modules/generated/sklearn.pipeline.Pipeline.html
- **Scikit-learn TimeSeriesSplit**: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html
- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **Apache Kafka**: https://kafka.apache.org/
- **MongoDB Documentation**: https://docs.mongodb.com/

---

*Tài liệu này được cập nhật cho phiên bản HAutoML v2.0.0*
