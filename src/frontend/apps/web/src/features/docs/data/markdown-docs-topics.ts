/**
 * Dedicated Vietnamese Markdown content for sub-topics in HAutoML documentation.
 * Ensures every single sidebar navigation item has comprehensive, detailed data.
 */

export const FIRST_TRAINING_MD = `# Hướng dẫn Huấn luyện Mô hình Đầu tiên

Tài liệu này sẽ hướng dẫn bạn từng bước từ khâu chuẩn bị dữ liệu đến khi huấn luyện thành công mô hình học máy đầu tiên với **HAutoML**, xem báo cáo đánh giá và thực hiện suy luận (Inference).

---

## 🎯 Mục tiêu bài học
- Nắm vững quy trình huấn luyện tự động (End-to-End AutoML) trên giao diện HAutoML.
- Tải lên tập dữ liệu dạng bảng và xác định bài toán học máy phù hợp.
- Thiết lập không gian tìm kiếm và theo dõi tiến độ chạy thời gian thực qua Kafka Worker.
- Đánh giá bảng xếp hạng Leaderboard và thử nghiệm suy luận trên dữ liệu mới.

---

## 📋 Bước 1: Chuẩn bị tập dữ liệu (Dataset)

HAutoML hỗ trợ các định dạng dữ liệu dạng bảng chuẩn: **CSV (.csv)**, **Excel (.xlsx)**, và **JSON (.json)**.

> [!TIP]
> Bạn có thể sử dụng các tập dữ liệu mẫu có sẵn trong hệ thống (như **Iris Flower**, **Titanic Survival**, **Wine Quality**, hoặc **California Housing**) để trải nghiệm ngay mà không cần chuẩn bị file tải lên.

**Quy chuẩn dữ liệu đầu vào:**
1. **Hàng đầu tiên**: Chứa tiêu đề tên các cột đặc trưng (Feature names).
2. **Cột nhãn (Target column)**: Cần có một cột chứa giá trị muốn dự đoán (ví dụ \`species\` hoặc \`price\`).
3. **Giá trị khuyết (Missing Values)**: Không cần tự xóa hàng hay điền giá trị khuyết thủ công, hệ thống sẽ tự động phân loại và xử lý thích ứng (imputation).

---

## 🚀 Bước 2: Tải tập dữ liệu lên hệ thống

1. Đăng nhập vào hệ thống HAutoML bằng tài khoản cá nhân hoặc tài khoản **Google**.
2. Trên menu chính, chọn mục **"Tập dữ liệu của tôi"** (\`/my-datasets\`).
3. Nhấp nút **"Tải lên tập dữ liệu" (Upload Dataset)**:
   - **Tên dữ liệu**: Nhập tên gợi nhớ (ví dụ: \`Iris Flower Dataset\`).
   - **Loại bài toán**: Chọn \`Phân loại (Classification)\` hoặc \`Hồi quy (Regression)\`.
   - **Tệp tin**: Kéo thả tệp CSV vào vùng tải lên.
4. Nhấn **Xác nhận**. Tệp sẽ được lưu trữ an toàn trên máy chủ đối tượng **MinIO** và hiển thị bản xem trước 10 dòng đầu tiên kèm theo thống kê kiểu dữ liệu.

---

## ⚙️ Bước 3: Cấu hình Huấn luyện AutoML (Training Wizard)

Nhấn vào nút **"Bắt đầu huấn luyện" (Train)** bên cạnh tập dữ liệu vừa tải lên:

### 1. Chọn cột mục tiêu (Target Column)
- Chỉ định cột dữ liệu mục tiêu cần dự đoán (ví dụ: cột \`species\` cho bài toán phân loại loài hoa).

### 2. Chọn các đặc trưng đầu vào (Feature Selection)
- Mặc định tất cả các cột còn lại sẽ được chọn làm đặc trưng đầu vào.
- Bạn có thể bỏ tích các cột không mang tính dự đoán (như ID, Mã sinh viên, Tên riêng).

### 3. Lựa chọn thuật toán
- **Phân loại**: Random Forest, Logistic Regression, LightGBM, Support Vector Machine (SVM), Decision Tree.
- **Hồi quy**: Random Forest Regressor, Linear Regression, Ridge, Lasso, Gradient Boosting.
- *Khuyến nghị*: Giữ tùy chọn **Tất cả thuật toán** để HAutoML tự động tìm kiếm mô hình tối ưu nhất.

### 4. Chiến lược tìm kiếm siêu tham số (HPO)
- **Phương pháp**: Chọn \`Bayesian Optimization\` (Tối ưu Bayes) hoặc \`Random Search\`.
- **Tiêu chí tối ưu (Metric)**: Chọn \`F1-Score\` hoặc \`Accuracy\` cho bài toán phân loại; chọn \`RMSE\` hoặc \`R²\` cho bài toán hồi quy.
- **Kiểm định chéo**: Chọn $k=5$ fold cross-validation để phòng chống overfitting.

---

## ⚡ Bước 4: Khởi chạy và Theo dõi tiến độ

1. Nhấn nút **"Khởi chạy huấn luyện" (Submit Job)**.
2. Hệ thống sẽ phát sinh một \`job_id\` và đẩy yêu cầu vào hàng đợi **Apache Kafka**.
3. Cụm **Worker** chạy ngầm sẽ nhận công việc và huấn luyện song song các mô hình.
4. Bạn có thể theo dõi tiến độ trên trang **Lịch sử huấn luyện** (\`/training-history\`):
   - Trạng thái công việc: \`Queued\` ➔ \`Processing\` ➔ \`Completed\`.
   - Log tiến độ theo thời gian thực của từng fold và từng thuật toán.

---

## 📊 Bước 5: Phân tích kết quả & Leaderboard

Khi công việc hoàn tất:
1. **Bảng xếp hạng (Leaderboard)**: Hiển thị danh sách các mô hình đã thử nghiệm sắp xếp theo điểm số metric từ cao đến thấp. Mô hình tốt nhất được trao cúp **Best Model**.
2. **Chi tiết đánh giá**:
   - Ma trận nhầm lẫn (**Confusion Matrix**).
   - Báo cáo phân loại (**Classification Report**): Precision, Recall, F1-Score cho từng nhãn.
   - Mức độ quan trọng của đặc trưng (**Feature Importance**).
   - Bộ tham số tối ưu đạt được từ thuật toán HPO.

---

## 🔮 Bước 6: Kích hoạt & Thử nghiệm suy luận (Inference)

1. Nhấn nút **"Kích hoạt mô hình" (Activate)** trên thẻ mô hình tối ưu.
2. Chuyển sang tab **"Thử nghiệm (Playground)"**:
   - Nhập giá trị cho các thuộc tính đặc trưng trực tiếp trên giao diện web.
   - Nhấn **"Dự đoán" (Predict)** để nhận kết quả nhãn dự đoán cùng độ tin cậy (Confidence Score).
3. Tích hợp trực tiếp vào hệ thống bên ngoài qua API endpoint \`POST /inference-model/\`.
`;

export const DISTRIBUTED_COMPUTING_MD = `# Kiến trúc Tính toán Phân tán & Cụm Worker (Distributed Computing)

HAutoML v2.2 được thiết kế theo kiến trúc phân tán hiện đại, phân tách hoàn toàn giữa API Gateway và tầng tính toán chuyên sâu (Worker Cluster) thông qua hàng đợi tin nhắn Apache Kafka và lưu trữ đối tượng MinIO.

---

## 🏗️ Tổng quan Mô hình Master - Worker

\`\`\`
┌─────────────────────────────────────────────────────────────┐
│                   HAutoML Master / API                      │
│                  (FastAPI Backend Service)                  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                Giao nhiệm vụ  │  Gửi tin nhắn Kafka
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 Apache Kafka Message Broker                 │
│              Topic: 'automl_training_tasks'                 │
└───────┬──────────────────────┬──────────────────────┬───────┘
        │                      │                      │
        ▼                      ▼                      ▼
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│   Worker 1   │       │   Worker 2   │       │   Worker N   │
│  (Node Alpha)│       │  (Node Beta) │       │ (Auto-scale) │
└───────┬──────┘       └───────┬──────┘       └───────┬──────┘
        │                      │                      │
        └──────────────────────┼──────────────────────┘
                               ▼
        ┌─────────────────────────────────────────────┐
        │        MinIO Object Storage & MongoDB       │
        │      (Lưu trữ Models, Artifacts & Logs)     │
        └─────────────────────────────────────────────┘
\`\`\`

---

## ⚙️ Các Thành phần cốt lõi

### 1. Master Service (API Server)
- **Framework**: FastAPI (Python 3.11).
- **Trách nhiệm**:
  - Nhận yêu cầu huấn luyện từ người dùng qua REST API.
  - Kiểm tra hợp lệ của tập dữ liệu và siêu tham số cấu hình.
  - Tạo công việc (\`job_id\`), ghi nhận trạng thái ban đầu vào MongoDB.
  - Đóng gói thông số bài toán và đẩy (produce) message vào topic Kafka.

### 2. Message Broker (Apache Kafka)
- Đảm bảo độ trễ thấp và khả năng chịu tải hàng ngàn tác vụ huấn luyện đồng thời.
- **Topic chính**:
  - \`automl_training_tasks\`: Chứa các yêu cầu huấn luyện chờ xử lý.
  - \`automl_status_updates\`: Gửi cập nhật tiến độ phần trăm và log về cho Master.

### 3. Worker Cluster
- Các tiến trình Python độc lập lắng nghe (consume) từ Kafka topic.
- Mỗi Worker có thể chạy trên một container riêng, một máy chủ vật lý khác nhau hoặc cụm GPU:
  - Tải dữ liệu từ MinIO về bộ nhớ đệm nội bộ.
  - Thực thi tiền xử lý dữ liệu và thuật toán AutoML (Scikit-Learn, LightGBM, XGBoost).
  - Tối ưu siêu tham số bằng Cross-Validation song song.
  - Lưu file mô hình đã huấn luyện (\`.pkl\`, \`.joblib\`) lên MinIO.
  - Cập nhật kết quả cuối cùng vào MongoDB.

---

## 📈 Khả năng mở rộng ngang (Horizontal Scaling)

Bạn có thể dễ dàng mở rộng số lượng Worker để tăng tốc độ xử lý hàng đợi mà không cần khởi động lại hệ thống:

### Mở rộng bằng Docker Compose
\`\`\`bash
# Tăng số lượng worker lên 4 tiến trình độc lập
docker-compose up -d --scale worker=4
\`\`\`

### Khởi chạy Worker trên máy chủ từ xa
\`\`\`bash
# Chạy worker độc lập kết nối đến Kafka và MinIO tập trung
python -m cluster.worker \\
  --kafka-server 192.168.1.100:9092 \\
  --minio-endpoint 192.168.1.100:9000 \\
  --mongodb-connect mongodb://192.168.1.100:27017
\`\`\`

---

## 🛡️ Cơ chế Chịu lỗi (Fault Tolerance) & Snoozing

Hệ thống được trang bị các giải pháp bảo vệ độ tin cậy cao:
- **Task Timeout (\`TASK_TIMEOUT_SECONDS\`)**: Nếu một Worker bị treo hoặc xử lý vượt quá thời gian cho phép (mặc định 1800 giây), Master sẽ đánh dấu tác vụ quá hạn.
- **Tự động thử lại (\`MAX_TASK_SNOOZES\`)**: Khi một Worker đột ngột tắt (crash), Kafka tự động tái phân bổ tin nhắn chưa được commit cho Worker khác tiếp tục xử lý (tối đa 3 lần thử).
- **Lưu trữ độc lập**: Dữ liệu và Artifacts được lưu trên MinIO, do đó bất kỳ Worker nào cũng có thể truy cập mà không phụ thuộc vào ổ cứng cục bộ của máy khác.
`;

export const HPO_TUNING_MD = `# Tìm kiếm Siêu tham số & Tối ưu hóa Mô hình (Hyperparameter Optimization - HPO)

Tối ưu hóa siêu tham số (Hyperparameter Optimization - HPO) là một trong những thành phần trọng tâm của hệ thống HAutoML, quyết định trực tiếp đến chất lượng và khả năng khái quát hóa của mô hình học máy.

---

## 🔍 Khái niệm Không gian Siêu tham số (Search Space)

Mỗi thuật toán học máy có một tập hợp các siêu tham số định hướng cách học:
- **Random Forest**:
  - \`n_estimators\`: Số lượng cây quyết định trong rừng ($[10, 50, 100, 200]$).
  - \`max_depth\`: Độ sâu tối đa của mỗi cây ($[3, 5, 10, \\text{None}]$).
  - \`min_samples_split\`: Số lượng mẫu tối thiểu để phân chia nút ($[2, 5, 10]$).
  - \`criterion\`: Tiêu chí phân chia (\`gini\`, \`entropy\`, \`log_loss\`).
- **LightGBM / Gradient Boosting**:
  - \`learning_rate\`: Tốc độ học ($\\eta \\in [0.01, 0.2]$).
  - \`num_leaves\`: Số lá tối đa trong một cây ($[15, 31, 63]$).
  - \`subsample\`: Tỷ lệ lấy mẫu dữ liệu trên mỗi vòng lặp ($[0.6, 0.8, 1.0]$).
- **Support Vector Machine (SVM)**:
  - \`C\`: Hệ số phạt sai số biên ($[0.1, 1, 10, 100]$).
  - \`kernel\`: Hàm nhân (\`linear\`, \`rbf\`, \`poly\`).
  - \`gamma\`: Hệ số ảnh hưởng khoảng cách của các điểm hỗ trợ.

---

## 🧠 Các Chiến lược Tối ưu hóa trong HAutoML

### 1. Grid Search (Tìm kiếm lưới)
- Duyệt qua toàn bộ tích Descartes của các tham số được chỉ định.
- **Ưu điểm**: Đảm bảo tìm thấy tổ hợp tốt nhất trong lưới hữu hạn.
- **Hạn chế**: Bùng nổ tổ hợp (Curse of Dimensionality), tốn kém chi phí tính toán khi không gian lớn.

### 2. Random Search (Tìm kiếm ngẫu nhiên)
- Lấy mẫu ngẫu nhiên $N$ tổ hợp từ không gian phân phối tham số.
- **Ưu điểm**: Thực nghiệm của Bergstra & Bengio chứng minh Random Search tìm ra tham số tiệm cận tối ưu nhanh hơn Grid Search gấp nhiều lần với cùng số lần thử nghiệm.

### 3. Bayesian Optimization (Tối ưu hóa Bayes - Khuyến nghị)
- Sử dụng quá trình Gaussian (Gaussian Process) hoặc TPE (Tree-structured Parzen Estimator) để xây dựng mô hình đại diện xác suất của hàm mục tiêu:
$$\\theta^* = \\arg\\max_{\\theta \\in \\Theta} \\mathbb{E}[f(\\theta)]$$
- Cân bằng giữa hai yếu tố:
  - **Exploitation (Khai thác)**: Thử nghiệm quanh các vùng tham số đã cho điểm số cao.
  - **Exploration (Khám phá)**: Thử nghiệm các vùng tham số chưa có nhiều dữ liệu để tránh rơi vào cực trị cục bộ.

### 4. Genetic Algorithm (Thuật toán Di truyền - GA trong v2.1+)
- Khởi tạo quần thể các cá thể mang bộ gen là tập tham số.
- Đánh giá độ thích nghi (Fitness Score), chọn lọc cá thể vượt trội, thực hiện lai ghép (Crossover) và đột biến (Mutation) qua từng thế hệ.

---

## 🛡️ Kiểm định Chéo k-Fold (k-Fold Cross Validation)

Để đảm bảo điểm số tìm được không bị học vẹt (overfitting), HAutoML áp dụng cơ chế kiểm định chéo $k$-fold (mặc định $k=5$):

$$\\text{CV Score} = \\frac{1}{k} \\sum_{i=1}^{k} \\mathcal{M}\\left(f_\\theta(D_{\\text{train}}^{(i)}), D_{\\text{val}}^{(i)}\\right)$$

- Dữ liệu được chia thành $k$ phần cân bằng (Stratified k-Fold cho bài toán phân loại).
- Pipeline tiền xử lý (Scaling, Imputation, One-Hot Encoding) được khớp (fit) **độc lập** trên từng fold để loại bỏ rò rỉ dữ liệu (Data Leakage).
`;

export const EVALUATION_METRICS_MD = `# Tiêu chuẩn Đánh giá & Bộ Chỉ số Mô hình (Model Evaluation Metrics)

HAutoML cung cấp bộ chỉ số đánh giá khoa học chuẩn mực và toàn diện cho cả bài toán Phân loại (Classification) và Hồi quy (Regression). Hệ thống tự động tính toán các chỉ số này trong suốt quá trình thử nghiệm để xếp hạng và đề xuất Best Model.

---

## 📊 1. Bộ chỉ số cho Bài toán Phân loại (Classification)

Cho ma trận nhầm lẫn (Confusion Matrix) với các đại lượng:
- **TP (True Positive)**: Dự đoán Đúng là Dương tính.
- **TN (True Negative)**: Dự đoán Đúng là Âm tính.
- **FP (False Positive)**: Sai lầm loại I (Dự đoán Dương tính nhưng thực tế là Âm tính).
- **FN (False Negative)**: Sai lầm loại II (Dự đoán Âm tính nhưng thực tế là Dương tính).

### A. Accuracy (Độ chính xác tổng thể)
Tỷ lệ dự đoán chính xác trên toàn bộ tập dữ liệu:
$$\\text{Accuracy} = \\frac{TP + TN}{TP + TN + FP + FN}$$
> [!NOTE]
> Phù hợp khi các lớp trong tập dữ liệu có tỷ lệ tương đương nhau (balanced data).

### B. Precision (Độ chuẩn xác)
Trong số tất cả các trường hợp mô hình dự đoán là Dương tính, có bao nhiêu phần trăm là thực sự đúng:
$$\\text{Precision} = \\frac{TP}{TP + FP}$$
*Ứng dụng*: Lọc thư rác (Spam Filter), nhận diện giao dịch gian lận (cần hạn chế tối đa việc báo động giả).

### C. Recall (Độ thu hồi / Sensitivity)
Trong số tất cả các trường hợp thực tế là Dương tính, mô hình phát hiện được bao nhiêu phần trăm:
$$\\text{Recall} = \\frac{TP}{TP + FN}$$
*Ứng dụng*: Chẩn đoán y tế (phát hiện bệnh nhân ung thư, tuyệt đối không được bỏ sót ca bệnh).

### D. F1-Score (Điểm điều hòa F1)
Trung bình điều hòa giữa Precision và Recall, cân bằng giữa hai chỉ số:
$$\\text{F1} = 2 \\times \\frac{\\text{Precision} \\times \\text{Recall}}{\\text{Precision} + \\text{Recall}} = \\frac{2TP}{2TP + FP + FN}$$

### E. Balanced Accuracy (Độ chính xác cân bằng)
Tính trung bình độ thu hồi của từng lớp, đặc biệt hiệu quả với tập dữ liệu mất cân bằng nghiêm trọng:
$$\\text{Balanced Accuracy} = \\frac{1}{K} \\sum_{i=1}^{K} \\frac{TP_i}{TP_i + FN_i}$$

### F. ROC-AUC (Area Under the ROC Curve)
Diện tích dưới đường cong ROC (True Positive Rate theo False Positive Rate tại các ngưỡng xác suất khác nhau). Thể hiện năng lực phân biệt xác suất giữa các lớp của mô hình độc lập với ngưỡng quyết định.

---

## 📈 2. Bộ chỉ số cho Bài toán Hồi quy (Regression)

Với $y_i$ là giá trị thực tế, $\\hat{y}_i$ là giá trị dự đoán, và $\\bar{y}$ là giá trị trung bình:

### A. MAE (Mean Absolute Error)
Sai số tuyệt đối trung bình giữa giá trị dự đoán và thực tế:
$$\\text{MAE} = \\frac{1}{n} \\sum_{i=1}^{n} |y_i - \\hat{y}_i|$$
- Đơn vị đo trùng khớp với đơn vị của biến mục tiêu.
- Ít bị ảnh hưởng quá mức bởi các giá trị ngoại lai (outliers).

### B. MSE (Mean Squared Error) & RMSE (Root Mean Squared Error)
$$\\text{MSE} = \\frac{1}{n} \\sum_{i=1}^{n} (y_i - \\hat{y}_i)^2 \\quad \\Longrightarrow \\quad \\text{RMSE} = \\sqrt{\\text{MSE}}$$
- Phạt rất nặng các sai số lớn do phép lũy thừa bậc hai.
- Là tiêu chuẩn vàng trong nhiều bài toán dự báo tài chính và giá cả.

### C. $R^2$ Score (Hệ số xác định - Coefficient of Determination)
Tỷ lệ phương sai của biến mục tiêu được giải thích bởi mô hình:
$$R^2 = 1 - \\frac{\\sum_{i=1}^{n} (y_i - \\hat{y}_i)^2}{\\sum_{i=1}^{n} (y_i - \\bar{y})^2}$$
- $R^2 = 1.0$: Mô hình dự đoán hoàn hảo không có sai số.
- $R^2 = 0.0$: Mô hình tương đương việc lấy giá trị trung bình $\\bar{y}$ làm dự đoán.
- $R^2 < 0.0$: Mô hình hoạt động kém hơn cả dự đoán bằng giá trị trung bình.
`;

export const API_AUTH_MD = `# Tài liệu API: Quản lý Người dùng & Xác thực (Auth API)

Tài liệu chi tiết các endpoint phục vụ đăng ký, đăng nhập, cấp phát JWT Bearer Token và quản lý tài khoản người dùng trong HAutoML.

---

## 🌐 URL Cơ sở
\`\`\`
http://localhost:8000
\`\`\`

Tất cả các endpoint yêu cầu xác thực cần gửi kèm Header:
\`\`\`http
Authorization: Bearer <access_token>
\`\`\`

---

## 📌 Danh sách Endpoints

### 1. Đăng ký tài khoản (\`POST /signup\`)
Đăng ký người dùng mới vào hệ thống.

- **URL**: \`/signup\`
- **Method**: \`POST\`
- **Request Body (JSON)**:
\`\`\`json
{
  "username": "vietanh",
  "email": "vietanh@example.com",
  "password": "SecurePassword123!",
  "fullName": "Hoàng Việt Anh"
}
\`\`\`
- **Response (200 OK)**:
\`\`\`json
{
  "status": "success",
  "message": "User registered successfully",
  "userId": "66123456789abcdef"
}
\`\`\`

---

### 2. Đăng nhập hệ thống (\`POST /login\`)
Xác thực người dùng và cấp phát JWT Bearer Token.

- **URL**: \`/login\`
- **Method**: \`POST\`
- **Request Body (JSON)**:
\`\`\`json
{
  "username": "vietanh",
  "password": "SecurePassword123!"
}
\`\`\`
- **Response (200 OK)**:
\`\`\`json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
  "token_type": "bearer",
  "expires_in": 1440,
  "user": {
    "id": "66123456789abcdef",
    "username": "vietanh",
    "email": "vietanh@example.com",
    "role": "user"
  }
}
\`\`\`

---

### 3. Lấy thông tin tài khoản (\`GET /users/\`)
- **URL**: \`/users/?username={username}\`
- **Method**: \`GET\`
- **Response (200 OK)**:
\`\`\`json
{
  "id": "66123456789abcdef",
  "username": "vietanh",
  "email": "vietanh@example.com",
  "createdAt": "2026-01-15T08:30:00Z"
}
\`\`\`

---

### 4. Đổi mật khẩu (\`POST /change_password\`)
- **URL**: \`/change_password?username={username}\`
- **Method**: \`POST\`
- **Request Body**:
\`\`\`json
{
  "password": "OldPassword123!",
  "new1_password": "NewSecurePassword456!",
  "new2_password": "NewSecurePassword456!"
}
\`\`\`

---

### 5. Xác thực với Google OAuth 2.0
- \`GET /login_google\`: Chuyển hướng người dùng sang trang xác thực Google Consent Screen.
- \`GET /auth\`: Callback URL tiếp nhận mã xác thực từ Google và tạo phiên đăng nhập.
`;

export const API_DATASETS_MD = `# Tài liệu API: Quản lý Tập dữ liệu (Dataset API)

Cung cấp các giao diện API để tải lên, truy vấn danh sách, kiểm tra siêu dữ liệu (metadata) và xóa các tập dữ liệu phục vụ huấn luyện AutoML.

---

## 🌐 URL Cơ sở
\`\`\`
http://localhost:8000
\`\`\`

---

## 📌 Danh sách Endpoints

### 1. Tải lên tập dữ liệu mới (\`POST /upload-dataset\`)
Tải tệp dữ liệu lên hệ thống và lưu trữ trên MinIO Object Storage.

- **URL**: \`/upload-dataset\`
- **Method**: \`POST\`
- **Content-Type**: \`multipart/form-data\`
- **Form Fields**:
  - \`user_id\` (string, bắt buộc): ID của người dùng sở hữu.
  - \`data_name\` (string, bắt buộc): Tên gợi nhớ của tập dữ liệu.
  - \`data_type\` (string, bắt buộc): \`classification\` hoặc \`regression\`.
  - \`file_data\` (file, bắt buộc): Tệp tin dữ liệu (\`.csv\`, \`.xlsx\`, \`.json\`).
- **Response (200 OK)**:
\`\`\`json
{
  "status": "success",
  "dataset_id": "data_987654321",
  "data_name": "Iris Flower",
  "rows": 150,
  "columns": 5,
  "file_url": "minio/datasets/66123456789abcdef/data_987654321.csv"
}
\`\`\`

---

### 2. Lấy danh sách Dataset của người dùng (\`POST /get-list-data-by-userid\`)
- **URL**: \`/get-list-data-by-userid\`
- **Method**: \`POST\`
- **Request Body**:
\`\`\`json
{
  "id": "66123456789abcdef"
}
\`\`\`
- **Response (200 OK)**:
\`\`\`json
[
  {
    "id": "data_987654321",
    "name": "Iris Flower Dataset",
    "dataType": "classification",
    "rowCount": 150,
    "columnCount": 5,
    "createdAt": "2026-03-10T14:20:00Z"
  }
]
\`\`\`

---

### 3. Xem chi tiết thông tin Dataset (\`POST /get-data-info\`)
- **URL**: \`/get-data-info\`
- **Method**: \`POST\`
- **Request Body**: \`{"id": "data_987654321"}\`
- **Response (200 OK)**:
\`\`\`json
{
  "id": "data_987654321",
  "columns": [
    { "name": "sepal_length", "type": "numeric", "missing_count": 0 },
    { "name": "sepal_width", "type": "numeric", "missing_count": 0 },
    { "name": "petal_length", "type": "numeric", "missing_count": 0 },
    { "name": "petal_width", "type": "numeric", "missing_count": 0 },
    { "name": "species", "type": "categorical", "unique_values": 3 }
  ],
  "preview": [
    { "sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4, "petal_width": 0.2, "species": "setosa" }
  ]
}
\`\`\`

---

### 4. Xóa tập dữ liệu (\`DELETE /delete-dataset/{dataset_id}\`)
- **URL**: \`/delete-dataset/{dataset_id}\`
- **Method**: \`DELETE\`
- **Response (200 OK)**:
\`\`\`json
{
  "status": "success",
  "message": "Dataset data_987654321 deleted successfully"
}
\`\`\`
`;

export const API_TRAINING_INFERENCE_MD = `# Tài liệu API: Huấn luyện AutoML & Suy luận (Training & Inference API)

Đây là phân hệ API quan trọng nhất của HAutoML, cho phép kích hoạt tác vụ tìm kiếm mô hình tự động, truy vấn kết quả Leaderboard và gọi dự đoán thời gian thực.

---

## 🌐 URL Cơ sở
\`\`\`
http://localhost:8000
\`\`\`

---

## 📌 Danh sách Endpoints

### 1. Khởi chạy Huấn luyện AutoML (\`POST /train-from-requestbody-json/\`)
Tạo một công việc huấn luyện AutoML mới và đẩy vào hàng đợi Apache Kafka.

- **URL**: \`/train-from-requestbody-json/?userId={userId}&id_data={id_data}\`
- **Method**: \`POST\`
- **Request Body (JSON)**:
\`\`\`json
{
  "task_type": "classification",
  "target_column": "species",
  "feature_columns": [
    "sepal_length",
    "sepal_width",
    "petal_length",
    "petal_width"
  ],
  "algorithms": [
    "RandomForest",
    "LightGBM",
    "LogisticRegression"
  ],
  "tuning_method": "bayesian",
  "metric": "f1_score",
  "cv_folds": 5
}
\`\`\`
- **Response (200 OK)**:
\`\`\`json
{
  "status": "queued",
  "job_id": "job_20260416_001",
  "message": "Training task queued successfully via Kafka"
}
\`\`\`

---

### 2. Lấy thông tin trạng thái & Kết quả Job (\`POST /get-job-info\`)
- **URL**: \`/get-job-info\`
- **Method**: \`POST\`
- **Request Body**: \`{"id": "job_20260416_001"}\`
- **Response (200 OK)**:
\`\`\`json
{
  "job_id": "job_20260416_001",
  "status": "completed",
  "progress": 100,
  "best_model": {
    "algorithm": "RandomForest",
    "score": 0.98,
    "metric": "f1_score",
    "hyperparameters": {
      "n_estimators": 100,
      "max_depth": 5,
      "criterion": "gini"
    }
  },
  "leaderboard": [
    { "rank": 1, "algorithm": "RandomForest", "accuracy": 0.98, "f1_score": 0.98 },
    { "rank": 2, "algorithm": "LightGBM", "accuracy": 0.96, "f1_score": 0.95 },
    { "rank": 3, "algorithm": "LogisticRegression", "accuracy": 0.92, "f1_score": 0.91 }
  ]
}
\`\`\`

---

### 3. Kích hoạt mô hình phục vụ suy luận (\`POST /activate-model\`)
- **URL**: \`/activate-model?job_id={job_id}&activate=1\`
- **Method**: \`POST\`
- **Response (200 OK)**:
\`\`\`json
{
  "status": "success",
  "message": "Model for job_20260416_001 is now active for inference"
}
\`\`\`

---

### 4. Thực hiện Suy luận / Dự đoán (\`POST /inference-model/\`)
Gửi dữ liệu kiểm thử mới để nhận kết quả nhãn dự đoán từ mô hình đã kích hoạt.

- **URL**: \`/inference-model/?job_id={job_id}\`
- **Method**: \`POST\`
- **Content-Type**: \`multipart/form-data\`
- **Form Field**: \`file_data\` (tệp CSV hoặc JSON chứa các hàng dữ liệu cần dự đoán).
- **Response (200 OK)**:
\`\`\`json
{
  "job_id": "job_20260416_001",
  "predictions": [
    { "row_index": 0, "predicted_label": "setosa", "confidence": 0.992 },
    { "row_index": 1, "predicted_label": "versicolor", "confidence": 0.945 }
  ],
  "total_records": 2
}
\`\`\`

---

### 5. Ví dụ gọi API bằng Python
\`\`\`python
import requests

url = "http://localhost:8000/inference-model/?job_id=job_20260416_001"
files = {"file_data": open("test_data.csv", "rb")}
response = requests.post(url, files=files)

print("Predictions:", response.json())
\`\`\`
`;
