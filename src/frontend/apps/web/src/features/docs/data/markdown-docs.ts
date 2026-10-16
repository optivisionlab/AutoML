/**
 * Full, unedited Markdown documentation mirrored 100% from AutoML/docs/
 * and https://optivisionlab.github.io/AutoML/docs/
 */

export const INDEX_MD = `# Chào mừng đến với HAutoML

**HAutoML** là nền tảng **tự động hóa học máy (Automated Machine Learning - AutoML)** mã nguồn mở được phát triển bởi [OptiVisionLab](https://optivisionlab.fit-haui.edu.vn/), Trường Công nghệ Thông tin và Truyền thông, Đại học Công nghiệp Hà Nội.

Nền tảng này tự động hóa toàn bộ quy trình xây dựng mô hình học máy - từ tiền xử lý dữ liệu, lựa chọn mô hình, tinh chỉnh siêu tham số, cho đến triển khai mô hình - cho phép người dùng dễ dàng tải dữ liệu lên và tự động tạo ra các mô hình học máy chất lượng cao **mà không cần kiến thức sâu về lập trình hay khoa học dữ liệu**.

## 🎯 Tầm nhìn

HAutoML được thiết kế để **dân chủ hóa học máy** - giúp bất cứ ai (dù là sinh viên, nhân viên kinh doanh, hoặc chuyên gia) có thể xây dựng các mô hình học máy hiệu quả mà không cần phải thành thạo các chi tiết kỹ thuật phức tạp.

## ✨ Tính năng chính

- **Quản lý người dùng & Xác thực**: Hệ thống đăng ký/đăng nhập an toàn với hỗ trợ OAuth 2.0 (Google)
- **Quản lý tập dữ liệu**: Giao diện trực quan để tải lên, xem, cập nhật và xóa các tập dữ liệu
- **Quy trình AutoML tự động**: 
  - 🔄 **Tiền xử lý dữ liệu thông minh**: Tự động phát hiện kiểu dữ liệu (số, phân loại, văn bản) và áp dụng các kỹ thuật xử lý phù hợp
  - 🔍 **Tìm kiếm siêu tham số**: Tự động tìm sự kết hợp siêu tham số tốt nhất (Grid Search, Random Search, ...)
  - 🎯 **Lựa chọn mô hình**: So sánh hiệu suất và chọn mô hình tối ưu
- **Xử lý công việc không đồng bộ**: Sử dụng Apache Kafka để xử lý các tác vụ huấn luyện song song (scalable)
- **Theo dõi công việc thời gian thực**: Giám sát trạng thái của các công việc huấn luyện
- **Triển khai & Suy luận (Inference)**: API đơn giản để đưa ra dự đoán trên dữ liệu mới
- **Giao diện hiện đại**: Được xây dựng bằng Next.js + TypeScript + Tailwind CSS

## 🔬 Phương pháp khoa học

HAutoML sử dụng các phương pháp khoa học hiện đại trong AutoML:

### Tiền xử lý dữ liệu thông minh
- Phát hiện tự động kiểu dữ liệu (numeric, categorical, text)
- Xử lý giá trị thiếu (imputation) phù hợp cho từng loại dữ liệu
- Chuẩn hóa (normalization) và mã hóa (encoding)
- Pipeline xử lý để tránh data leakage

### Tìm kiếm siêu tham số
- Grid Search và Random Search
- Kiểm định chéo k-fold (k-fold cross-validation)
- Đánh giá dựa trên multiple metrics

### Đánh giá mô hình
- **Phân loại**: Accuracy, Precision, Recall, F1-Score, Balanced Accuracy
- **Hồi quy**: MAE, MSE, RMSE, R²
- Xác thực generalization để tránh overfitting

Xem chi tiết tại [Phương pháp khoa học](/docs?topic=scientific-approach).

## 🏗️ Kiến trúc hệ thống

HAutoML sử dụng kiến trúc **microservices** hiện đại:

\`\`\`
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js)                       │
│                  Giao diện người dùng web                    │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTP/REST
┌────────────────────────────▼────────────────────────────────┐
│                  Backend (FastAPI)                          │
│              API, Business Logic, Orchestration              │
└─┬────────────┬──────────────┬─────────────┬─────────────────┘
  │            │              │             │
  │            │              │             │
┌─▼─┐    ┌────▼────┐    ┌────▼─────┐  ┌──▼───────┐
│   │    │ MongoDB │    │  Apache  │  │  MinIO   │
│   │    │(Database│    │  Kafka   │  │ (Storage │
│   │    │ Metadata│    │ (Queue)  │  │ Datasets)│
│   │    └─────────┘    └─────┬────┘  └──────────┘
│   │                         │
│   └─────────────────────────┼─────────────────────┐
│                             │ Task dispatch       │
└─────────────────────────────┼─────────────────────┘
                              │
                   ┌──────────▼──────────┐
                   │       Workers       │
                   │  (Process Training  │
                   │   Jobs from Kafka)  │
                   └─────────────────────┘
\`\`\`

Xem chi tiết tại [Kiến trúc hệ thống](/docs?topic=architecture).

## 🚀 Bắt đầu nhanh

### Cách đơn giản nhất: Sử dụng Docker

Cách được khuyến nghị nhất để chạy toàn bộ hệ thống là sử dụng Docker và Docker Compose.

**Yêu cầu**: [Docker](https://www.docker.com/get-started) và [Docker Compose](https://docs.docker.com/compose/install/)

---

### Triển khai từ mã nguồn

**1. Tải mã nguồn dự án**
\`\`\`bash
git clone https://github.com/optivisionlab/AutoML.git
cd AutoML
\`\`\`

**2. Cấu hình môi trường**
\`\`\`bash
cp src/backend/temp.env src/backend/.env
cp src/frontend/temp.env src/frontend/.env
\`\`\`

**3. Khởi chạy các thành phần hệ thống**
> **Backend & Worker cluster**
> 
> Tại thư mục: AutoML/src/backend
\`\`\`bash
pip install -r requirements.txt # Cài đặt các thư viện cần thiết

python app.py # Khởi chạỵ API server
python -m cluster.worker # Kích hoạt worker xử lý tác vụ
\`\`\`

> **Frontend**
> 
> Tại thư mục: AutoML/src/frontend
\`\`\`bash
npm install # Cài đặt các gói phụ thuộc
npm run dev # Chạy ứng dụng ở chế độ phát triển
\`\`\`

**4. Địa chỉ truy cập**

- Giao diện người dùng: [http://localhost:3000](http://localhost:3000)

- Backend API: [http://localhost:8000](http://localhost:8000)

---

### Triển khai qua docker
> **Tự động hóa việc thiết lập và khởi chạy toàn bộ môi trường**
> 
> Tại thư mục: AutoML/
\`\`\`bash
docker-compose up -d --build
\`\`\`

> **Để dừng hệ thống**
\`\`\`bash
docker-compose down
\`\`\`

Chi tiết đầy đủ xem tại [Bắt đầu](/docs?topic=getting-started).

## 📦 Các phiên bản đã phát hành

| Phiên bản | Ngày | Đặc điểm chính | Trạng thái |
|----------|------|----------------|-----------|
| **v2.2.0** | 11/04/2026 | 🚀 Distributed Computing, Smart Scheduling, Account Classification | ✅ Latest |
| **v2.1.0** | 05/12/2025 | 🔍 Optima Search (GA, Bayesian Optimization) | ✅ Supported |
| **v2.0.0** | 19/10/2025 | 🏗️ MapReduce 1.0, MinIO, Async API | ✅ Stable |
| **v1.1.2** | 21/06/2025 | 🎨 UI Updates + Security Fixes | ⚠️ Supported |
| **v1.1.0** | 03/06/2025 | 🚀 Model Deployment & Inference API | ⚠️ Supported |
| **v1.0.0** | 17/05/2025 | 🎉 Initial Release | ❌ EOL |

**→ [Xem chi tiết tất cả các phiên bản](/docs?topic=releases)**

## 📚 Tài liệu

| Trang | Nội dung |
|------|---------|
| [Bắt đầu](/docs?topic=getting-started) | Hướng dẫn cài đặt và chạy hệ thống |
| [Kiến trúc](/docs?topic=architecture) | Các thành phần hệ thống và công nghệ |
| [Phương pháp khoa học](/docs?topic=scientific-approach) | Chi tiết về quá trình AutoML, tiền xử lý, tuning, v.v. |
| [Backend API](/docs?topic=backend-api) | Tài liệu API endpoints |
| [Lịch sử phát hành](/docs?topic=releases) | Các phiên bản đã phát hành và hướng phát triển |
| [Ghi nhận & Giấy phép](/docs?topic=citation-license) | Cách trích dẫn và thông tin giấy phép |

## 👥 Người đóng góp

Chúng tôi xin chân thành cảm ơn tất cả những người đã đóng góp cho dự án HAutoML.

<a href="https://github.com/optivisionlab/AutoML/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=optivisionlab/AutoML" alt="Contributors" />
</a>

## 📖 Trích dẫn

### Bài báo khoa học (Recommended) 📄

Nếu bạn sử dụng HAutoML trong **nghiên cứu hoặc công bố công khai**, xin vui lòng trích dẫn bài báo sau:

\`\`\`bibtex
@InProceedings{Do2026HAutoML,
  author="Do, Manh Quang
  and Chu, Thi Anh
  and Ngo, Cong Binh
  and Bui, Huy Nam
  and Nguyen, Thi My Khanh
  and Nguyen, Thi Minh
  and Vu, Viet Thang",
  editor="Thi Dieu Linh, Nguyen
  and Yu, Shiqi
  and Selamat, Ali
  and Tran, Duc-Tan",
  title="HAutoML: Open-Source for Automated Machine Learning",
  booktitle="Proceedings of the Fifth International Conference on Intelligent Systems and Networks",
  year="2026",
  publisher="Springer Nature Singapore",
  address="Singapore",
  pages="415--423",
  isbn="978-981-95-1746-6"
}
\`\`\`

**Full Citation:**
> Do, M. Q., Chu, T. A., Ngo, C. B., Bui, H. N., Nguyen, T. M. K., Nguyen, T. M., & Vu, V. T. (2026). HAutoML: Open-Source for Automated Machine Learning. In Proceedings of the Fifth International Conference on Intelligent Systems and Networks (pp. 415–423). Springer Nature Singapore. https://doi.org/10.1007/978-981-95-1746-6_46

### Phần mềm (Software Citation) 💻

Ngoài ra, bạn cũng có thể trích dẫn phần mềm trực tiếp:

\`\`\`bibtex
@software{hautoml2024,
  title = {HAutoML: Open-source Automated Machine Learning Platform},
  author = {OptiVisionLab},
  url = {https://github.com/optivisionlab/AutoML},
  year = {2024},
  license = {CC BY-NC 4.0}
}
\`\`\`

Xem chi tiết tại [Ghi nhận & Giấy phép](/docs?topic=citation-license).
`;

export const GETTING_STARTED_MD = `## Bắt đầu
---

### Cách đơn giản nhất: Sử dụng Docker

Cách được khuyến nghị nhất để chạy toàn bộ hệ thống là sử dụng Docker và Docker Compose.

**Yêu cầu**: [Docker](https://www.docker.com/get-started) và [Docker Compose](https://docs.docker.com/compose/install/)

---

### Triển khai từ mã nguồn

**1. Tải mã nguồn dự án**
\`\`\`bash
git clone https://github.com/optivisionlab/AutoML.git
cd AutoML
\`\`\`

**2. Cấu hình môi trường**
\`\`\`bash
cp src/backend/temp.env src/backend/.env
cp src/frontend/temp.env src/frontend/.env
\`\`\`

**3. Khởi chạy các thành phần hệ thống**
> **Backend & Worker cluster**
> 
> Tại thư mục: AutoML/src/backend
\`\`\`bash
pip install -r requirements.txt # Cài đặt các thư viện cần thiết

python app.py # Khởi chạỵ API server
python -m cluster.worker # Kích hoạt worker xử lý tác vụ
\`\`\`

> **Frontend**
> 
> Tại thư mục: AutoML/src/frontend
\`\`\`bash
npm install # Cài đặt các gói phụ thuộc
npm run dev # Chạy ứng dụng ở chế độ phát triển
\`\`\`

**4. Địa chỉ truy cập**
- Giao diện người dùng: [http://localhost:3000](http://localhost:3000)

- Backend API: [http://localhost:8000](http://localhost:8000)

---

### Triển khai qua docker
> [!TIP]
> Để tránh việc phải chỉnh sửa trực tiếp file \`docker-compose.yaml\`, bạn chỉ cần clone mã nguồn, sau đó chỉnh sửa và đổi tên các file cầu hình mẫu từ \`temp.env\` thành \`.env\` ở cả thư mục backend và frontend.

> **Tự động hóa việc thiết lập và khởi chạy toàn bộ môi trường**
> 
> **Tại thư mục: AutoML/**
\`\`\`bash
docker-compose up -d --build
\`\`\`

> **Để dừng hệ thống**
\`\`\`bash
docker-compose down
\`\`\`

**5. Giải thích biến môi trường**
> Hệ thống sử dụng các biến môi trường để linh hoạt giữa các chế độ chạy (local hoặc docker).

**A. Cấu hình hạ tầng (Infrastructure)**
> Dành cho việc kết nối đến các dịch vụ lưu trữ và hàng đợi
- \`MINIO_ENDPOINT\`: Địa chỉ server MinIO (mặc định: \`localhost:9000\`). Nếu chạy docker, hãy đổi thành \`minio:9000\`.
- \`KAFKA_SERVER\`: Địa chỉ broker Kafka. Dùng \`kafka:9092\` trong môi trường docker.
- \`MONGODB_CONNECT\`: Chuỗi kết nối database. Nếu dùng docker thì dùng \`mongodb:27017\`.

**B. Cấu hình phân tán (Master - Worker)**
> Đây là phần cốt lõi để hệ thống AutoML có thể chạy đa máy (Distributed).
- \`HOST_BACK_END\`: Địa chỉ API Server sẽ lắng nghe. Nên để \`0.0.0.0\` để chấp nhận kết nối từ các Worker bên ngoài.
- \`WORKER_LIST\`: Danh sách các địa chỉ Worker và Master quản lý.
- \`TASK_TIMEOUT_SECONDS\`: Thời gian tối đa (giây) chờ một tác vụ training. Sau thời gian này, Master sẽ coi Worker đã chết hoặc tác vụ bị treo.
- \`MAX_TASK_SNOOZES\`: Số lần cho phép thử lại (retry) một tác vụ trước khi đánh dấu là thất bại.

**C. Bảo mật và xác thực (Security & Auth)**
- \`SECRET_KEY\`: Chuỗi ký tự dùng để mã hóa JWT Token. Nên tạo 1 chuỗi ngẫu nhiên dài để bảo mật.
- \`GOOGLE_CLIENT_ID\`/\`GOOGLE_CLIENT_SECRET\`: Thông tin định danh ứng dụng lấy từ Google Cloud Console để kích hoạt tính năng đăng nhập bằng Google.
- \`ACCESS_EXPIRE\`: Thời gian của Token đăng nhập (tính bằng phút).

**D. Dịch vụ Email (Notification)**
- \`MAIL_USERNAME\`: Email dùng để gửi thông báo (ví dụ: gmail).
- \`MAIL_PASSWORD\`: Mật khẩu ứng dụng (app password) của Gmail, không phải mật khẩu tài khoản chính.

> [!IMPORTANT]
> **Quy tắc về localhost trong Docker**
> 
> Nếu chạy hệ thống bằng docker, tuyệt đối không sử dụng \`localhost\` cho các biến kết nối giữa các dịch vụ (như \`MONGODB_CONNECT\` hay \`KAFKA_SERVER\`)
> Thay vào đó, hãy sử dụng tên dịch vụ được định nghĩa trong file \`docker-compose.yaml\` (ví dụ: \`mongodb\`, \`kafka\`)

**6. Kiểm tra trạng thái hệ thống**
> Sau khi khởi chạy, bạn có thể kiểm tra xem các thành phần đã thông với nhau chưa bằng cách:
> 
> 1. Truy cập vào Dashboard tại: \`http://localhost:3000\`
> 2. Kiểm tra log của Master để xem các worker đã đăng ký thành công chưa: \`docker logs -f hautoml-toolkit\`

---

## Xem tài liệu trên máy Local

Trước khi triển khai, bạn có thể xem trước trang web tài liệu trên máy tính của mình.

1.  **Cài đặt các gói cần thiết (chỉ cần làm một lần):**
    Mở terminal và chạy lệnh sau để cài đặt MkDocs và theme Material:
    \`\`\`bash
    pip install mkdocs-material
    \`\`\`

2.  **Chạy máy chủ phát triển:**
    Từ thư mục gốc của dự án, chạy lệnh:
    \`\`\`bash
    mkdocs serve
    \`\`\`

3.  **Xem trang tài liệu:**
    Mở trình duyệt và truy cập vào địa chỉ \`http://127.0.0.1:8000\`. Máy chủ này có tính năng tự động tải lại (live-reloading), có nghĩa là bất kỳ khi nào bạn lưu một thay đổi trong các tệp Markdown, trang web trên trình duyệt sẽ tự động cập nhật.
`;

export const ARCHITECTURE_MD = `# Kiến trúc hệ thống

HAutoML được xây dựng theo kiến trúc microservices, bao gồm các thành phần chính sau:

- **Frontend**: Một ứng dụng Single Page Application (SPA) được xây dựng bằng **Next.js (React)** và **TypeScript**. Giao diện người dùng được thiết kế với **Tailwind CSS** và các thành phần từ **Radix UI**. Quản lý trạng thái bằng **Redux Toolkit**.
- **Backend**: Một hệ thống API mạnh mẽ được xây dựng bằng **Python** với framework **FastAPI**. Backend chịu trách nhiệm xử lý logic nghiệp vụ, xác thực người dùng và điều phối các công việc AutoML.
- **Cơ sở dữ liệu**: Sử dụng **MongoDB** để lưu trữ thông tin người dùng, siêu dữ liệu về các tập dữ liệu và các công việc huấn luyện.
- **Hàng đợi tin nhắn (Message Queue)**: **Apache Kafka** được sử dụng để quản lý hàng đợi các công việc huấn luyện. Khi người dùng yêu cầu huấn luyện một mô hình, một tin nhắn sẽ được gửi đến Kafka.
- **Workers**: Các tiến trình Python độc lập (consumers) lắng nghe các tin nhắn từ Kafka. Mỗi worker sẽ nhận một công việc huấn luyện, thực hiện nó, và cập nhật kết quả vào cơ sở dữ liệu.
- **Lưu trữ đối tượng (Object Storage)**: **Minio** được sử dụng để lưu trữ các tệp dữ liệu lớn (datasets) và các mô hình đã được huấn luyện.

\`\`\`
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js)                       │
│                  Giao diện người dùng web                    │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTP/REST
┌────────────────────────────▼────────────────────────────────┐
│                  Backend (FastAPI)                          │
│              API, Business Logic, Orchestration              │
└─┬────────────┬──────────────┬─────────────┬─────────────────┘
  │            │              │             │
  │            │              │             │
┌─▼─┐    ┌────▼────┐    ┌────▼─────┐  ┌──▼───────┐
│   │    │ MongoDB │    │  Apache  │  │  MinIO   │
│   │    │(Database│    │  Kafka   │  │ (Storage │
│   │    │ Metadata│    │ (Queue)  │  │ Datasets)│
│   │    └─────────┘    └─────┬────┘  └──────────┘
│   │                         │
│   └─────────────────────────┼─────────────────────┐
│                             │ Task dispatch       │
└─────────────────────────────┼─────────────────────┘
                              │
                   ┌──────────▼──────────┐
                   │       Workers       │
                   │  (Process Training  │
                   │   Jobs from Kafka)  │
                   └─────────────────────┘
\`\`\`

## Công nghệ sử dụng

### Backend (Python)
- **Framework**: FastAPI
- **Web Server**: Uvicorn
- **Cơ sở dữ liệu**: MongoDB (với Pymongo)
- **Học máy**: Scikit-learn, Pandas, Numpy
- **Hàng đợi tin nhắn**: Kafka (với kafka-python, aiokafka)
- **Lưu trữ đối tượng**: Minio
- **Xác thực**: Authlib, PyJWT
- **Containerization**: Docker

### Frontend (TypeScript)
- **Framework**: Next.js (v.15), React (v.18)
- **Ngôn ngữ**: TypeScript
- **Quản lý trạng thái**: Redux Toolkit
- **Styling**: Tailwind CSS, Sass
- **Thành phần UI**: Radix UI, Lucide React
- **Biểu đồ**: Recharts
- **Xử lý biểu mẫu**: React Hook Form, Zod
- **Client API**: Axios
- **Xác thực**: NextAuth.js
- **Containerization**: Docker
`;

export const SCIENTIFIC_APPROACH_MD = `# Phương pháp khoa học & Cách tiếp cận kỹ thuật

## Giới thiệu

HAutoML là một nền tảng **Automated Machine Learning (AutoML)** được thiết kế để tự động hóa toàn bộ quy trình xây dựng mô hình học máy. Tài liệu này mô tả các phương pháp khoa học, chiến lược kỹ thuật và cách tiếp cận được sử dụng trong hệ thống.

## 1. Quá trình AutoML toàn quy trình

### 1.1 Pipeline xử lý tự động

HAutoML thực hiện tự động hóa các giai đoạn chính của pipeline học máy:

\`\`\`
Dữ liệu thô → Tiền xử lý → Lựa chọn mô hình & Tuning → Mô hình tối ưu → Suy luận (Inference)
\`\`\`

#### Giai đoạn 1: Tiền xử lý dữ liệu (Data Preprocessing)

**a) Phát hiện kiểu dữ liệu (Feature Type Detection)**

Hệ thống tự động phân loại từng cột dữ liệu thành các loại:
- **Dữ liệu số (Numeric)**: Detects sử dụng \`pd.api.types.is_numeric_dtype()\`
- **Dữ liệu phân loại (Categorical)**: Các cột có số lượng giá trị độc lập nhỏ
- **Dữ liệu văn bản (Text)**: Các cột có số lượng giá trị độc lập lớn (vượt quá ngưỡng cardinality)

**b) Xử lý giá trị thiếu (Missing Value Imputation)**

- **Dữ liệu số**: Sử dụng trung vị (median) - phương pháp robust với outlier
- **Dữ liệu phân loại**: Sử dụng giá trị xuất hiện nhiều nhất (mode)

**c) Chuẩn hóa dữ liệu (Normalization & Scaling)**

- **Dữ liệu số**: Áp dụng \`StandardScaler\` để chuẩn hóa (mean=0, std=1)
- **Dữ liệu phân loại**: Sử dụng \`OneHotEncoder\` với \`sparse_output=True\`
- **Dữ liệu văn bản**: Sử dụng \`TfidfVectorizer\` để chuyển đổi thành vector số

**d) Pipeline xử lý (Preprocessing Pipeline)**

Hệ thống sử dụng \`scikit-learn Pipeline\` và \`ColumnTransformer\` để:
- Áp dụng các phép biến đổi phù hợp cho từng loại dữ liệu
- Đảm bảo tính nhất quán giữa dữ liệu huấn luyện và kiểm tra
- Tránh data leakage bằng cách fit trên training set và transform trên cả training/test set

\`\`\`python
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
\`\`\`

#### Giai đoạn 2: Lựa chọn mô hình & Tinh chỉnh siêu tham số (Hyperparameter Tuning)

**a) Chiến lược tìm kiếm siêu tham số**

Hệ thống sử dụng các chiến lược khác nhau để tìm kiếm sự kết hợp siêu tham số tốt nhất:
- **Grid Search**: Tìm kiếm toàn bộ không gian siêu tham số được xác định trước
- **Random Search**: Lấy mẫu ngẫu nhiên từ không gian siêu tham số
- **Bayesian Optimization & Genetic Algorithms (v2.1+)**: Tối ưu hóa xác suất và tiến hóa
- **Hybrid approaches**: Kết hợp các phương pháp để cân bằng hiệu suất và thời gian

**b) Kiểm định chéo (Cross-Validation)**

Sử dụng k-fold cross-validation (mặc định k=5) để đánh giá hiệu suất mô hình trên từng fold:

\`\`\`
CV Score = (1 / k) * Σ (Score_i)
\`\`\`

Điều này giúp:
- Giảm phương sai của đánh giá hiệu suất
- Tận dụng tối đa dữ liệu có sẵn
- Phát hiện overfitting

**c) Chỉ số đánh giá (Evaluation Metrics)**

**Cho bài toán Phân loại (Classification):**
- **Accuracy**: Tỷ lệ dự đoán đúng
- **Precision**: Trong các dự đoán dương tính, bao nhiêu phần trăm là đúng
- **Recall**: Trong các mẫu dương tính thực sự, bao nhiêu phần trăm được phát hiện
- **F1 Score**: Trung bình hài hòa của Precision và Recall: \`F1 = 2 * (Precision * Recall) / (Precision + Recall)\`
- **Balanced Accuracy**: Trung bình của recall cho từng lớp (hữu ích với dữ liệu mất cân bằng)

**Cho bài toán Hồi quy (Regression):**
- **MAE (Mean Absolute Error)**: Sai số tuyệt đối trung bình
- **MSE (Mean Squared Error)**: Bình phương sai số trung bình
- **RMSE (Root Mean Squared Error)**: Căn bậc hai của MSE
- **R² (Coefficient of Determination)**: Phần trăm phương sai được giải thích

#### Giai đoạn 3: Lựa chọn mô hình tối ưu (Model Selection)

Sau khi tìm kiếm, hệ thống:
1. So sánh hiệu suất từ các cấu hình khác nhau
2. Chọn mô hình có chỉ số đánh giá cao nhất
3. Lưu trữ mô hình tối ưu và siêu tham số của nó
4. Chuẩn bị cho triển khai và suy luận

## 2. Kiến trúc xử lý bất đồng bộ

### 2.1 Hàng đợi công việc với Apache Kafka

Hệ thống sử dụng Apache Kafka để quản lý hàng đợi công việc huấn luyện:

\`\`\`
Frontend → Backend → Kafka Queue → Workers → MongoDB (kết quả)
\`\`\`

**Ưu điểm:**
- **Scalability**: Có thể thêm workers để xử lý song song
- **Reliability**: Nếu worker crash, công việc không bị mất
- **Decoupling**: Frontend không phải chờ công việc huấn luyện hoàn thành
- **Real-time monitoring**: Theo dõi trạng thái công việc real-time

### 2.2 Các trạng thái công việc (Job States)

\`\`\`
Submitted → Queued → Processing → Completed
                          ↓
                       Failed (retry)
\`\`\`

**Trạng thái:**
- **Submitted**: Công việc được submitted từ user
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

### 3.2 Minio - Lưu trữ Objects

Lưu trữ:
- Datasets (CSV, JSON, v.v.)
- Mô hình serialized (\`.pickle\`, \`.joblib\`)
- Preprocessors (để sử dụng lại trong suy luận)

**Cấu trúc bucket:**
\`\`\`
/datasets/{user_id}/{dataset_id}.csv
/models/{user_id}/{model_id}.pkl
/preprocessors/{user_id}/{model_id}_preprocessor.pkl
\`\`\`

## 4. Quy trình suy luận (Inference)

Khi người dùng gửi dữ liệu mới để dự đoán:

1. **Tải mô hình & preprocessor** từ Minio
2. **Tiền xử lý dữ liệu mới** sử dụng cùng preprocessor (đảm bảo consistency)
3. **Suy luận** bằng mô hình đã huấn luyện
4. **Trả về kết quả** cho người dùng

\`\`\`python
# Pseudocode
def inference(model_id, new_data):
    model = load_from_minio(f"models/{user_id}/{model_id}.pkl")
    preprocessor = load_from_minio(f"preprocessors/{user_id}/{model_id}_preprocessor.pkl")
    
    processed_data = preprocessor.transform(new_data)
    predictions = model.predict(processed_data)
    
    return predictions
\`\`\`

## 5. Mở rộng & Hỗ trợ các loại bài toán

### 5.1 Phân loại (Classification)
- Logistic Regression, Decision Trees, Random Forests, Gradient Boosting, SVM, k-NN, v.v.

### 5.2 Hồi quy (Regression)
- Linear Regression, Ridge/Lasso, Decision Trees Regressor, Random Forests Regressor, Gradient Boosting Regressor, SVR, v.v.

## 6. Xử lý dữ liệu mất cân bằng
- Sử dụng \`balanced_accuracy_score\` thay vì accuracy thông thường
- Có thể áp dụng các kỹ thuật như SMOTE, undersampling, hoặc class weighting
- Theo dõi precision, recall, và F1 score riêng cho từng lớp

## 7. Đánh giá và Xác thực Mô hình
- Preprocessor được fit **chỉ** trên training data (chống Data Leakage)
- Cross-validation được thực hiện chính xác (không mix train/test)
- Siêu tham số được tìm kiếm dựa trên training/validation data, không test data

## 8. State-of-the-Art & Giới hạn
- ✅ Tự động hóa toàn quy trình
- ✅ Hỗ trợ đa loại dữ liệu (số, phân loại, văn bản)
- ✅ Kiến trúc scalable với xử lý bất đồng bộ
- ✅ Giao diện user-friendly, mã nguồn mở
- 🔸 Chưa hỗ trợ deep learning trực tiếp (chỉ scikit-learn)
- 🔸 Hướng tới tích hợp PyTorch/TensorFlow và Time Series trong các bản tới
`;

export const BACKEND_API_MD = `# Tài liệu API Backend

Tài liệu này cung cấp một cái nhìn tổng quan chi tiết về các điểm cuối (endpoints) API có sẵn trong backend của HAutoML.

## URL cơ sở
Tất cả các điểm cuối đều tương đối so với URL cơ sở nơi backend đang chạy (ví dụ: \`http://localhost:8000\`).

---

## 1. Quản lý người dùng & Xác thực

### \`POST /signup\`
- **Mô tả**: Đăng ký một người dùng mới.
- **Request Body**: Một đối tượng JSON chứa thông tin chi tiết của người dùng (\`username\`, \`email\`, \`password\`, v.v.).
- **Response**: Một thông báo xác nhận.

### \`POST /login\`
- **Mô tả**: Đăng nhập cho người dùng.
- **Request Body**: \`{"username": "your_username", "password": "your_password"}\`
- **Response**: Một đối tượng JSON chứa thông tin người dùng và một access token.

### \`GET /users\`
- **Mô tả**: Lấy danh sách tất cả người dùng.
- **Response**: Một mảng JSON chứa các đối tượng người dùng.

### \`GET /users/\`
- **Mô tả**: Lấy thông tin một người dùng cụ thể bằng tên đăng nhập.
- **Tham số truy vấn (Query Parameter)**: \`username\` (string).
- **Response**: Một đối tượng JSON của người dùng được chỉ định.

### \`PUT /update/{username}\`
- **Mô tả**: Cập nhật thông tin hồ sơ của người dùng.
- **Tham số đường dẫn (Path Parameter)**: \`username\` (string).
- **Request Body**: Một đối tượng JSON chứa các trường cần cập nhật.
- **Response**: Một thông báo xác nhận.

### \`DELETE /delete/{username}\`
- **Mô tả**: Xóa một người dùng.
- **Tham số đường dẫn (Path Parameter)**: \`username\` (string).
- **Response**: Một thông báo xác nhận.

### \`POST /change_password\`
- **Mô tả**: Thay đổi mật khẩu của người dùng.
- **Tham số truy vấn (Query Parameter)**: \`username\` (string).
- **Request Body**: \`{"password": "old_password", "new1_password": "new_password", "new2_password": "confirm_new_password"}\`
- **Response**: Một thông báo xác nhận.

### \`POST /forgot_password/{email}\`
- **Mô tả**: Bắt đầu quy trình đặt lại mật khẩu cho một email nhất định.
- **Tham số đường dẫn (Path Parameter)**: \`email\` (string).
- **Response**: Một thông báo xác nhận.

### Xác thực với Google
- \`GET /login_google\`: Bắt đầu luồng đăng nhập Google OAuth2.
- \`GET /auth\`: URL callback để Google chuyển hướng đến sau khi xác thực.

---

## 2. Quản lý tập dữ liệu (Dataset)

### \`POST /upload-dataset\`
- **Mô tả**: Tải lên một tập dữ liệu mới.
- **Request Body**: \`multipart/form-data\` chứa:
    - \`user_id\` (string)
    - \`data_name\` (string)
    - \`data_type\` (string)
    - \`file_data\` (file)
- **Response**: Một đối tượng JSON chứa siêu dữ liệu của tập dữ liệu mới.

### \`GET /get-list-data-user\`
- **Mô tả**: Lấy danh sách tất cả các tập dữ liệu từ tất cả người dùng (dành cho quản trị viên).
- **Response**: Một mảng JSON chứa các đối tượng tập dữ liệu.

### \`POST /get-list-data-by-userid\`
- **Mô tả**: Lấy danh sách các tập dữ liệu cho một người dùng cụ thể.
- **Request Body**: \`{"id": "user_id"}\`
- **Response**: Một mảng JSON chứa các đối tượng tập dữ liệu.

### \`POST /get-data-info\`
- **Mô tả**: Lấy siêu dữ liệu cho một tập dữ liệu duy nhất.
- **Request Body**: \`{"id": "dataset_id"}\`
- **Response**: Một đối tượng JSON chứa siêu dữ liệu của tập dữ liệu.

### \`PUT /update-dataset/{dataset_id}\`
- **Mô tả**: Cập nhật siêu dữ liệu hoặc tệp của một tập dữ liệu.
- **Tham số đường dẫn (Path Parameter)**: \`dataset_id\` (string).
- **Request Body**: \`multipart/form-data\` (các trường tùy chọn: \`data_name\`, \`data_type\`, \`file_data\`).
- **Response**: Một thông báo thành công.

### \`DELETE /delete-dataset/{dataset_id}\`
- **Mô tả**: Xóa một tập dữ liệu.
- **Tham số đường dẫn (Path Parameter)**: \`dataset_id\` (string).
- **Response**: Một thông báo thành công.

---

## 3. Tác vụ AutoML & Huấn luyện

### \`POST /train-from-requestbody-json/\`
- **Mô tả**: Bắt đầu một công việc huấn luyện mới dựa trên cấu hình JSON.
- **Tham số truy vấn (Query Parameters)**: \`userId\` (string), \`id_data\` (string).
- **Request Body**: Một đối tượng JSON (\`Item\`) chứa cấu hình huấn luyện (features, target, models, metrics, v.v.).
- **Response**: Một đối tượng JSON chứa ID và trạng thái của công việc.

### \`POST /get-list-job-by-userId\`
- **Mô tả**: Lấy danh sách tất cả các công việc huấn luyện cho một người dùng cụ thể.
- **Request Body**: \`{"user_id": "user_id"}\`
- **Response**: Một mảng JSON chứa các đối tượng công việc.

### \`POST /get-job-info\`
- **Mô tả**: Lấy thông tin chi tiết cho một công việc huấn luyện duy nhất.
- **Request Body**: \`{"id": "job_id"}\`
- **Response**: Một đối tượng JSON chứa chi tiết công việc.

### \`POST /inference-model/\`
- **Mô tả**: Thực hiện suy luận (inference) bằng một mô hình đã được huấn luyện.
- **Tham số truy vấn (Query Parameter)**: \`job_id\` (string).
- **Request Body**: \`multipart/form-data\` chứa \`file_data\` (dữ liệu cần dự đoán).
- **Response**: Kết quả dự đoán.

### \`POST /activate-model\`
- **Mô tả**: Kích hoạt hoặc vô hiệu hóa một mô hình đã được huấn luyện để suy luận.
- **Tham số truy vấn (Query Parameters)**: \`job_id\` (string), \`activate\` (integer, 0 hoặc 1).
- **Response**: Một thông báo xác nhận.
`;

export const RELEASES_MD = `# Lịch sử phát hành (Releases)

Trang này liệt kê tất cả các phiên bản của HAutoML đã được phát hành, cùng với các tính năng và cải tiến chính.

---

## v2.2.0 (11 Tháng 4, 2026) - Distributed Computing 🚀

**Phiên bản chính - Xử lý phân tán nâng cao và tối ưu hóa hiệu suất**

### Tính năng chính

#### Distributed Computing
- ✅ **MapReduce Optimization**: Kiến trúc MapReduce nâng cao để xử lý song song trên nhiều máy
- ✅ **Data Parallelization**: Chia dữ liệu theo mô hình ("Song song hóa dữ liệu: Chia theo model")
- ✅ **Smart Scheduling**: Thuật toán lập lịch dựa trên **Locality + Capacity + Cost**
- ✅ **Enhanced Scheduling**: Tích hợp thông tin băng thông mạng để tối ưu hóa lập lịch
- ✅ **Fault Tolerance**: Khả năng chịu lỗi và tự động thử lại công việc (automatic job retry)
- ✅ **Timeout Management**: Thực thi giới hạn thời gian với giám sát nền tảng

#### Backend Improvements
- ✅ **Account Classification**: Hệ thống phân loại tài khoản cho đăng ký trực tiếp và của bên thứ ba
- ✅ **Enhanced Authentication**: Cải tiến quá trình xác thực và phân quyền (authorization)

#### Frontend Improvements
- ✅ **Training Configuration UI**: Giao diện cấu hình huấn luyện với gợi ý tính năng dựa trên loại bài toán
- ✅ **Performance Optimization**: Cải tiến tối giảm thời gian chờ đợi trên giao diện
- ✅ **Marketplace Interface**: Thêm giao diện marketplace mới

#### Documentation
- ✅ Cải tiến các mô tả tài liệu

### Nhóm phát triển
- 🧑‍💼 Backend: @VanAnh-13, @xuanndong
- 🎨 Frontend: @vanhdz74
- 👮 PM: @DoManhQuang

### Downloads
- **GitHub**: [v2.2.0 Release](https://github.com/optivisionlab/AutoML/releases/tag/v2.2.0)

---

## v2.1.0 (05 Tháng 12, 2025) - Optima Search 🔍

**Cập nhập thuật toán tìm kiếm siêu tham số nâng cao**

### Tính năng chính
- ✅ **Advanced Hyperparameter Tuning**:
  - Genetic Algorithm (GA) - tìm kiếm dựa trên tiến hóa
  - Bayesian Optimization (BO) - tối ưu xác suất
- ✅ Cập nhật thuật toán quản lý các worker
- ✅ Tiền xử lý dữ liệu string cơ bản (basic string preprocessing)
- ✅ Cập nhật lại giao diện người dùng
- ✅ Cập nhật Dockerfile & Docker Compose

### Hotfixes
- 🐛 Fix lỗi không thể training trên page model (training page errors)

### Nhóm phát triển
- 🧑‍💼 Backend: @VanAnh-13, @xuanndong
- 🎨 Frontend: @vanhdz74
- 👮 PM: @DoManhQuang

### Downloads
- **GitHub**: [v2.1.0 Release](https://github.com/optivisionlab/AutoML/releases/tag/v2.1.0)

---

## v2.0.0 (19 Tháng 10, 2025) - MapReduce 1.0 🏗️

**Phiên bản được công bố tại ISINC 2026**

### Tính năng chính
- ✅ **Kiến trúc MapReduce 1.0**: Xây dựng kiến trúc xử lý phân tán (distributed processing)
- ✅ **MinIO Object Storage**: Lưu trữ dữ liệu, mô hình AI (tiến đến HCloud 1.0)
- ✅ **Async API**: Thêm xử lý bất đồng bộ cho các API
- ✅ **Admin Frontend**: Phân trang (pagination) cho quản trị viên

### Hotfixes & Tối ưu
- 🐛 Xử lý dữ liệu NULL trong quá trình huấn luyện
- ⚡ Tối ưu lại truy vấn dữ liệu trong quá trình huấn luyện

### Nhóm phát triển
- 🧑‍💼 Backend: @xuanndong
- 🎨 Frontend: @vanhdz74
- 👮 PM: @DoManhQuang

### Downloads
- **GitHub**: [v2.0.0 Release](https://github.com/optivisionlab/AutoML/releases/tag/v2.0.0)

---

## v1.1.2 (21 Tháng 6, 2025) - UI Update 🎨

**Cải tiến giao diện & bảo mật**

### Tính năng
- ✅ Frontend phân trang (pagination) - hiển thị theo trang
- ✅ Thanh loading (progress bar) - hiển thị tiến độ
- ✅ Thông tin về lab
- ✅ Chuẩn hóa Docker - có thể chạy trên localhost với docker-compose

### Hotfixes & Bảo mật
- 🔒 **Security Hotfix**: Ngăn chặn chiếm quyền admin qua API signup
- 🔒 Maintain lại class User với chức năng signup

### Nhóm phát triển
- 🔒 Security: @l3eol3eo
- 🎨 Frontend: @nguyenkhanh0310
- 🧑‍💼 Hotfix: @BuiHuyNam
- 👮 PM: @DoManhQuang

### Downloads
- **GitHub**: [v1.1.2 Release](https://github.com/optivisionlab/AutoML/releases/tag/v1.1.2)

---

## v1.1.1 (07 Tháng 6, 2025) - Quick Hotfix 🔧

**Sửa chữa nhanh cho vấn đề Kafka**

### Hotfixes
- 🐛 Fix lỗi gọi API push Kafka
- 🔧 Tạo Dockerfile và Docker Compose mới

### Nhóm phát triển
- 🧑‍💼 Hotfix: @DoManhQuang

### Downloads
- **GitHub**: [v1.1.1 Release](https://github.com/optivisionlab/AutoML/releases/tag/v1.1.1)

---

## v1.1.0 (03 Tháng 6, 2025) - Big Update 🚀

**Cập nhập lớn - Thêm khả năng triển khai mô hình**

### Tính năng chính
- ✅ **Model Deployment**: Triển khai mô hình với API cho end-user
- ✅ **API Inference**: API suy luận, kích hoạt và vô hiệu hóa mô hình
- ✅ **Docker Compose**: Nano, Toolkit, Kafka, MongoDB
- ✅ **Model Storage**: Lưu base64 model best vào MongoDB
- ✅ **Code Refactor**: Tái cấu trúc frontend, backend và fix lỗi

### Fixes
- 🐛 Fix lỗi không thể kết nối từ HAutoML Toolkit ↔ Kafka

### Nhóm phát triển
- 🛠️ Backend: @BuiHuyNam, @MinhSky17
- 🎨 Frontend: @nguyenkhanh0310
- 🗄️ Data: @chuanh1214
- 🔄 Automation: @CongBinh05
- 👮 PM: @DoManhQuang

### Downloads
- **GitHub**: [v1.1.0 Release](https://github.com/optivisionlab/AutoML/releases/tag/v1.1.0)

---

## v1.0.0 (17 Tháng 5, 2025) - Initial Release 🎉

**Phiên bản đầu tiên - Foundation**

### Các thành phần chính
- ✅ **HAutoML Nano**: No-code interface với Gradio
- ✅ **HAutoML Toolkits**: API server với FastAPI  
- ✅ **HAutoML Pro**: Giao diện thương mại

### Tính năng
- ✅ Huấn luyện No-Code với dữ liệu cá nhân (bài toán bảng)
- ✅ Quản trị thông tin dữ liệu cá nhân, tài khoản
- ✅ Bộ dữ liệu có sẵn
- ✅ Quản trị màn hình Admin
- ✅ Lịch sử huấn luyện mô hình

### Các mô hình hỗ trợ
- SVM (Support Vector Machine)
- Decision Tree
- Random Forest
- k-NN (k-Nearest Neighbors)
- Logistic Regression
- Gaussian Naive Bayes

### Nhóm phát triển
- 🛠️ Backend: @BuiHuyNam, @MinhSky17
- 🎨 Frontend: @nguyenkhanh0310
- 🗄️ Data: @chuanh1214
- 🔄 Automation: @CongBinh05
- 👮 PM: @DoManhQuang
- 🌟 Contributor: @MinhSky17

### Downloads
- **GitHub**: [v1.0.0 Release](https://github.com/optivisionlab/AutoML/releases/tag/v1.0.0)

---

## Hướng phát triển tương lai 🚀

### Sắp ra mắt (Planned)
- [ ] Hỗ trợ Deep Learning (TensorFlow, PyTorch)
- [ ] Time Series Forecasting
- [ ] Ensemble Methods nâng cao
- [ ] Auto Feature Engineering
- [ ] Explainability tools (SHAP, LIME)
- [ ] Hỗ trợ GPU acceleration
- [ ] Multi-language support
- [ ] Advanced monitoring & logging

### Đang xem xét (Under consideration)
- Federated Learning
- Reinforcement Learning support
- Mobile app
- GraphQL API
- Real-time collaboration features
- Advanced visualization tools

---

## Hỗ trợ các phiên bản (Version Support)

| Phiên bản | Trạng thái | Kết thúc hỗ trợ |
|-----------|-----------|-----------------|
| v2.0.0 | ✅ LTS (Long-term Support) | Oct 2027 |
| v1.0.0 | ❌ End-of-Life | Oct 2024 |

---

## Cách nâng cấp

Để nâng cấp từ phiên bản cũ:

\`\`\`bash
# Pull phiên bản mới nhất
git pull origin main

# Cập nhật dependencies
pip install -r requirements.txt

# Rebuild Docker images nếu cần
docker-compose down
docker-compose up -d --build
\`\`\`

---

## Báo cáo lỗi & Yêu cầu tính năng

- 🐛 **Báo cáo lỗi**: [GitHub Issues](https://github.com/optivisionlab/AutoML/issues)
- 💡 **Yêu cầu tính năng**: [GitHub Discussions](https://github.com/optivisionlab/AutoML/discussions)
- 📧 **Email**: [optivisionlab@fit-haui.edu.vn](mailto:optivisionlab@fit-haui.edu.vn)
`;

export const CITATION_LICENSE_MD = `# Ghi nhận & Giấy phép

## Trích dẫn

### Bài báo khoa học (Recommended)

Nếu bạn sử dụng HAutoML trong nghiên cứu hoặc công bố công khai, xin vui lòng trích dẫn bài báo sau:

\`\`\`bibtex
@InProceedings{Do2026HAutoML,
  author="Do, Manh Quang
  and Chu, Thi Anh
  and Ngo, Cong Binh
  and Bui, Huy Nam
  and Nguyen, Thi My Khanh
  and Nguyen, Thi Minh
  and Vu, Viet Thang",
  editor="Thi Dieu Linh, Nguyen
  and Yu, Shiqi
  and Selamat, Ali
  and Tran, Duc-Tan",
  title="HAutoML: Open-Source for Automated Machine Learning",
  booktitle="Proceedings of the Fifth International Conference on Intelligent Systems and Networks",
  year="2026",
  publisher="Springer Nature Singapore",
  address="Singapore",
  pages="415--423",
  isbn="978-981-95-1746-6"
}
\`\`\`

**Full Citation:**
Do, M. Q., Chu, T. A., Ngo, C. B., Bui, H. N., Nguyen, T. M. K., Nguyen, T. M., & Vu, V. T. (2026). HAutoML: Open-Source for Automated Machine Learning. In Proceedings of the Fifth International Conference on Intelligent Systems and Networks (pp. 415–423). Springer Nature Singapore. https://doi.org/10.1007/978-981-95-1746-6_46

### Phần mềm (Software Citation)

Ngoài ra, bạn cũng có thể trích dẫn phần mềm trực tiếp:

\`\`\`bibtex
@software{Do_OptiVisionLab_HAutoML_2025,
  author = {Do, Manh-Quang},
  title = {{OptiVisionLab HAutoML}},
  month = {10},
  year = {2025},
  publisher = {OptiVisionLab},
  version = {2.0.0},
  url = {https://github.com/optivisionlab/AutoML}
}
\`\`\`

## Giấy phép
Dự án này được cấp phép theo [Creative Commons Attribution-NonCommercial 4.0 International License](https://creativecommons.org/licenses/by-nc/4.0/).

Vui lòng xem tệp [LICENSE](https://github.com/optivisionlab/AutoML/blob/main/LICENSE) để biết chi tiết. Phần mềm này được phát hành chỉ dành cho **mục đích học thuật và nghiên cứu**. Việc sử dụng cho mục đích thương mại bị **nghiêm cấm** nếu không có sự đồng ý trước bằng văn bản từ OptivisionLab.
`;

import {
  FIRST_TRAINING_MD,
  DISTRIBUTED_COMPUTING_MD,
  HPO_TUNING_MD,
  EVALUATION_METRICS_MD,
  API_AUTH_MD,
  API_DATASETS_MD,
  API_TRAINING_INFERENCE_MD,
} from "./markdown-docs-topics";

export const DOCS_PAGES: Record<string, { title: string; markdown: string }> = {
  overview: {
    title: "Trang chủ (Overview)",
    markdown: INDEX_MD,
  },
  "getting-started": {
    title: "Bắt đầu nhanh (Quickstart)",
    markdown: GETTING_STARTED_MD,
  },
  "first-training": {
    title: "Huấn luyện mô hình đầu tiên",
    markdown: FIRST_TRAINING_MD,
  },
  architecture: {
    title: "Kiến trúc hệ thống Microservices",
    markdown: ARCHITECTURE_MD,
  },
  "distributed-computing": {
    title: "Tính toán phân tán & Worker",
    markdown: DISTRIBUTED_COMPUTING_MD,
  },
  "scientific-approach": {
    title: "Phương pháp khoa học: Quy trình AutoML & Tiền xử lý",
    markdown: SCIENTIFIC_APPROACH_MD,
  },
  "hpo-tuning": {
    title: "Phương pháp khoa học: Tìm kiếm siêu tham số (HPO)",
    markdown: HPO_TUNING_MD,
  },
  "evaluation-metrics": {
    title: "Phương pháp khoa học: Tiêu chuẩn đánh giá",
    markdown: EVALUATION_METRICS_MD,
  },
  "backend-api": {
    title: "Tài liệu API Backend (FastAPI)",
    markdown: BACKEND_API_MD,
  },
  "api-auth": {
    title: "Tài liệu API: Quản lý người dùng & Xác thực",
    markdown: API_AUTH_MD,
  },
  "api-datasets": {
    title: "Tài liệu API: Quản lý tập dữ liệu (Dataset)",
    markdown: API_DATASETS_MD,
  },
  "api-training-inference": {
    title: "Tài liệu API: Huấn luyện AutoML & Suy luận",
    markdown: API_TRAINING_INFERENCE_MD,
  },
  releases: {
    title: "Lịch sử phát hành (Releases)",
    markdown: RELEASES_MD,
  },
  "citation-license": {
    title: "Ghi nhận & Giấy phép (Citation)",
    markdown: CITATION_LICENSE_MD,
  },
};

import { DOCS_PAGES_EN, INDEX_MD_EN } from "./markdown-docs-en";
export { INDEX_MD_EN };

export function getDocsPage(topicId: string, locale: string = "vi"): { title: string; markdown: string } {
  if (locale === "en") {
    return DOCS_PAGES_EN[topicId] || DOCS_PAGES_EN["overview"];
  }
  return DOCS_PAGES[topicId] || DOCS_PAGES["overview"];
}

