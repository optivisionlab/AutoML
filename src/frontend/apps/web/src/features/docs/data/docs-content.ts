export type DocCategory = {
  id: string;
  title: string;
  items: DocNavItem[];
};

export type DocNavItem = {
  id: string;
  title: string;
  badge?: string;
  icon?: string;
  description?: string;
};

export type FeatureCard = {
  id: string;
  title: string;
  desc: string;
  icon: string;
  topicId: string;
  tag?: string;
};

export type ApiEndpoint = {
  method: "GET" | "POST" | "PUT" | "DELETE";
  path: string;
  desc: string;
  group: "Auth" | "Datasets" | "Training & Inference" | "v2 AutoML";
  params?: string;
  requestBody?: string;
  response?: string;
};

export type ReleaseItem = {
  version: string;
  date: string;
  status: string;
  badge: string;
  color: string;
  description: string;
  highlights: string[];
  team?: {
    backend?: string;
    frontend?: string;
    pm?: string;
  };
};

export const DOC_CATEGORIES: DocCategory[] = [
  {
    id: "getting-started",
    title: "BẮT ĐẦU (GETTING STARTED)",
    items: [
      { id: "overview", title: "Trang chủ (Overview)", icon: "BookOpen" },
      {
        id: "getting-started",
        title: "Bắt đầu nhanh (Quickstart)",
        badge: "Core",
        icon: "Rocket",
      },
      {
        id: "first-training",
        title: "Huấn luyện mô hình đầu tiên",
        icon: "PlayCircle",
      },
    ],
  },
  {
    id: "architecture",
    title: "KIẾN TRÚC HỆ THỐNG",
    items: [
      {
        id: "architecture",
        title: "Kiến trúc Microservices",
        badge: "v2.2",
        icon: "Boxes",
      },
      {
        id: "distributed-computing",
        title: "Tính toán phân tán & Worker",
        icon: "Cpu",
      },
    ],
  },
  {
    id: "scientific-approach",
    title: "PHƯƠNG PHÁP KHOA HỌC",
    items: [
      {
        id: "scientific-approach",
        title: "Quy trình AutoML & Tiền xử lý",
        icon: "Workflow",
      },
      {
        id: "hpo-tuning",
        title: "Tìm kiếm siêu tham số (HPO)",
        icon: "Sliders",
      },
      {
        id: "evaluation-metrics",
        title: "Đánh giá & Tiêu chí mô hình",
        icon: "LineChart",
      },
    ],
  },
  {
    id: "api-reference",
    title: "TÀI LIỆU API (API REFERENCE)",
    items: [
      {
        id: "backend-api",
        title: "Backend API (FastAPI)",
        badge: "FastAPI",
        icon: "Code2",
      },
      {
        id: "api-auth",
        title: "Xác thực & Người dùng (Auth)",
        icon: "ShieldCheck",
      },
      {
        id: "api-datasets",
        title: "Quản lý Dataset (Data API)",
        icon: "Database",
      },
      {
        id: "api-training-inference",
        title: "Training & Suy luận (Inference)",
        icon: "Zap",
      },
    ],
  },
  {
    id: "resources",
    title: "TÀI NGUYÊN & PHÁT HÀNH",
    items: [
      {
        id: "releases",
        title: "Lịch sử phát hành (Releases)",
        badge: "v2.2.0",
        icon: "History",
      },
      {
        id: "citation-license",
        title: "Ghi nhận & Giấy phép (Citation)",
        icon: "FileText",
      },
    ],
  },
];

export const TOP_NAV_TABS = [
  { id: "overview", label: "Trang chủ" },
  { id: "getting-started", label: "Bắt đầu" },
  { id: "architecture", label: "Kiến trúc" },
  { id: "scientific-approach", label: "Phương pháp khoa học" },
  { id: "backend-api", label: "Tài liệu API" },
  { id: "releases", label: "Lịch sử phát hành" },
  { id: "citation-license", label: "Ghi nhận & Giấy phép" },
];

export const LAB_INFO = {
  name: "OptiVisionLab",
  institution:
    "Trường Công nghệ Thông tin và Truyền thông, Trường Đại học Công nghiệp Hà Nội (HaUI)",
  address: "Số 298 đường Cầu Diễn, Quận Bắc Từ Liêm, Hà Nội",
  website: "https://optivisionlab.fit-haui.edu.vn/",
  github: "https://github.com/optivisionlab/AutoML",
  docsUrl: "https://optivisionlab.github.io/AutoML/docs/",
  mission:
    "HAutoML là nền tảng tự động hóa học máy (Automated Machine Learning - AutoML) mã nguồn mở được phát triển bởi OptiVisionLab, Trường Công nghệ Thông tin và Truyền thông, Đại học Công nghiệp Hà Nội. Nền tảng này tự động hóa toàn bộ quy trình xây dựng mô hình học máy - từ tiền xử lý dữ liệu, lựa chọn mô hình, tinh chỉnh siêu tham số, cho đến triển khai mô hình - cho phép người dùng dễ dàng tải dữ liệu lên và tự động tạo ra các mô hình học máy chất lượng cao mà không cần kiến thức sâu về lập trình hay khoa học dữ liệu.",
};

export const FEATURE_CARDS: FeatureCard[] = [
  {
    id: "datasets",
    title: "Quản lý tập dữ liệu",
    desc: "Giao diện trực quan để tải lên, xem, cập nhật và xóa các tập dữ liệu, tự động phát hiện định dạng và kiểm tra tính toàn vẹn.",
    icon: "Database",
    topicId: "api-datasets",
    tag: "Data Ops",
  },
  {
    id: "models",
    title: "Quy trình AutoML tự động",
    desc: "Tiền xử lý thông minh, tự động tìm kiếm siêu tham số (Grid, Random, Bayes, GA) và so sánh hiệu suất chọn mô hình tối ưu.",
    icon: "BrainCircuit",
    topicId: "scientific-approach",
    tag: "Core AI",
  },
  {
    id: "deployments",
    title: "Triển khai & Suy luận",
    desc: "API đơn giản để kích hoạt hoặc vô hiệu hóa mô hình đã huấn luyện và đưa ra dự đoán thời gian thực trên dữ liệu mới.",
    icon: "Rocket",
    topicId: "api-training-inference",
    tag: "Production",
  },
  {
    id: "architecture",
    title: "Kiến trúc Microservices",
    desc: "Hệ thống phân tán với Apache Kafka quản lý hàng đợi, MinIO Object Storage, MongoDB và các Workers xử lý song song.",
    icon: "Boxes",
    topicId: "architecture",
    tag: "Distributed",
  },
  {
    id: "backend-api",
    title: "Tài liệu Backend API",
    desc: "Danh mục REST API hoàn chỉnh xây dựng trên FastAPI, tài liệu hóa chi tiết tham số, payload và định dạng phản hồi.",
    icon: "Code2",
    topicId: "backend-api",
    tag: "FastAPI REST",
  },
  {
    id: "citation",
    title: "Công bố khoa học",
    desc: "Bài báo khoa học được xuất bản trong tuyển tập Springer Nature ISINC 2026. Hỗ trợ trích dẫn BibTeX cho các nghiên cứu học thuật.",
    icon: "Sparkles",
    topicId: "citation-license",
    tag: "Springer 2026",
  },
];

export const RELEASES_LIST: ReleaseItem[] = [
  {
    version: "v2.2.0",
    date: "11/04/2026",
    status: "Latest",
    badge: "v2.2.0",
    color: "bg-emerald-500/15 text-emerald-600 border border-emerald-500/30 dark:text-emerald-300",
    description: "Distributed Computing, Smart Scheduling, Account Classification",
    highlights: [
      "MapReduce Optimization: Kiến trúc MapReduce nâng cao để xử lý song song trên nhiều máy",
      "Data Parallelization: Song song hóa dữ liệu chia theo model",
      "Smart Scheduling: Thuật toán lập lịch dựa trên Locality + Capacity + Cost",
      "Enhanced Scheduling: Tích hợp thông tin băng thông mạng để tối ưu hóa lập lịch",
      "Fault Tolerance: Khả năng chịu lỗi và tự động thử lại công việc (automatic job retry)",
      "Timeout Management: Thực thi giới hạn thời gian với giám sát nền tảng",
      "Account Classification: Phân loại tài khoản đăng ký trực tiếp và bên thứ ba (Google OAuth)",
      "Frontend: Giao diện cấu hình huấn luyện gợi ý tính năng, tối ưu hóa hiệu năng, thêm Marketplace",
    ],
    team: {
      backend: "@VanAnh-13, @xuanndong",
      frontend: "@vanhdz74",
      pm: "@DoManhQuang",
    },
  },
  {
    version: "v2.1.0",
    date: "05/12/2025",
    status: "Supported",
    badge: "v2.1.0",
    color: "bg-blue-500/15 text-blue-600 border border-blue-500/30 dark:text-cyan-300",
    description: "Optima Search (GA, Bayesian Optimization)",
    highlights: [
      "Advanced Hyperparameter Tuning: Genetic Algorithm (GA) và Bayesian Optimization (BO)",
      "Cập nhật thuật toán quản lý các worker trong cụm tính toán",
      "Tiền xử lý dữ liệu string cơ bản (basic string preprocessing)",
      "Cập nhật lại giao diện người dùng và Dockerfile & Docker Compose",
      "Hotfix: Sửa lỗi không thể training trên trang model",
    ],
    team: {
      backend: "@VanAnh-13, @xuanndong",
      frontend: "@vanhdz74",
      pm: "@DoManhQuang",
    },
  },
  {
    version: "v2.0.0",
    date: "19/10/2025",
    status: "Stable (ISINC 2026)",
    badge: "v2.0.0",
    color: "bg-indigo-500/15 text-indigo-600 border border-indigo-500/30 dark:text-indigo-300",
    description: "MapReduce 1.0, MinIO Object Storage, Async API",
    highlights: [
      "Kiến trúc MapReduce 1.0: Xây dựng kiến trúc xử lý phân tán (distributed processing)",
      "MinIO Object Storage: Lưu trữ dữ liệu, mô hình AI (tiến đến HCloud 1.0)",
      "Async API: Thêm xử lý bất đồng bộ cho các API",
      "Admin Frontend: Phân trang (pagination) cho quản trị viên",
      "Hotfixes: Xử lý dữ liệu NULL và tối ưu truy vấn dữ liệu trong quá trình huấn luyện",
    ],
    team: {
      backend: "@xuanndong",
      frontend: "@vanhdz74",
      pm: "@DoManhQuang",
    },
  },
  {
    version: "v1.1.2",
    date: "21/06/2025",
    status: "Supported",
    badge: "v1.1.2",
    color: "bg-amber-500/15 text-amber-600 border border-amber-500/30 dark:text-amber-300",
    description: "UI Updates + Security Fixes",
    highlights: [
      "Cập nhật giao diện người dùng theo chuẩn thiết kế mới",
      "Bổ sung các bản vá bảo mật và kiểm tra quyền truy cập",
      "Cải thiện độ ổn định khi xử lý dữ liệu dạng bảng lớn",
    ],
  },
  {
    version: "v1.1.0",
    date: "03/06/2025",
    status: "Supported",
    badge: "v1.1.0",
    color: "bg-cyan-500/15 text-cyan-600 border border-cyan-500/30 dark:text-cyan-300",
    description: "Model Deployment & Inference API",
    highlights: [
      "Triển khai mô hình 1-Click sang REST API",
      "Endpoint dự đoán thời gian thực qua /inference-model/",
      "Quản lý trạng thái kích hoạt/vô hiệu hóa mô hình (/activate-model)",
    ],
  },
  {
    version: "v1.0.0",
    date: "17/05/2025",
    status: "Initial Release",
    badge: "v1.0.0",
    color: "bg-slate-100 text-slate-800 dark:bg-white/10 dark:text-slate-300",
    description: "Initial Release - Nền tảng HAutoML",
    highlights: [
      "Khởi tạo kiến trúc FastAPI backend và Next.js frontend",
      "Tích hợp MongoDB lưu trữ dữ liệu và người dùng",
      "Hỗ trợ 6 thuật toán học máy cơ bản (SVM, RF, k-NN, Decision Tree, Logistic, Naive Bayes)",
      "Quy trình quản lý người dùng và tập dữ liệu",
    ],
  },
];

export const API_ENDPOINTS: ApiEndpoint[] = [
  // 1. User & Auth
  {
    method: "POST",
    path: "/signup",
    group: "Auth",
    desc: "Đăng ký tài khoản người dùng mới vào hệ thống",
    requestBody:
      '{\n  "username": "your_username",\n  "email": "user@example.com",\n  "password": "your_password",\n  "fullName": "Nguyen Van A",\n  "gender": "male",\n  "date": "2000-01-01",\n  "number": "0123456789"\n}',
    response: '{\n  "message": "User registered successfully"\n}',
  },
  {
    method: "POST",
    path: "/login",
    group: "Auth",
    desc: "Đăng nhập cho người dùng và nhận JWT access token",
    requestBody: '{\n  "username": "your_username",\n  "password": "your_password"\n}',
    response:
      '{\n  "access_token": "eyJhbGciOi...",\n  "refresh_token": "eyJhbGciOi...",\n  "token_type": "bearer"\n}',
  },
  {
    method: "GET",
    path: "/users",
    group: "Auth",
    desc: "Lấy danh sách tất cả người dùng (dành cho quản trị viên)",
    response:
      '[\n  {\n    "_id": "64a...",\n    "username": "admin",\n    "email": "admin@example.com",\n    "role": "admin"\n  }\n]',
  },
  {
    method: "GET",
    path: "/users/",
    group: "Auth",
    desc: "Lấy thông tin một người dùng cụ thể bằng tên đăng nhập",
    params: "Query: username (string)",
    response:
      '{\n  "_id": "64a...",\n  "username": "user123",\n  "email": "user@example.com",\n  "role": "user"\n}',
  },
  {
    method: "PUT",
    path: "/update/{username}",
    group: "Auth",
    desc: "Cập nhật thông tin hồ sơ của người dùng",
    params: "Path: username (string)",
    requestBody:
      '{\n  "email": "updated@example.com",\n  "fullName": "Nguyen Van B",\n  "gender": "male",\n  "date": "2000-01-01",\n  "number": "0987654321"\n}',
    response: '{\n  "message": "User updated successfully"\n}',
  },
  {
    method: "DELETE",
    path: "/delete/{username}",
    group: "Auth",
    desc: "Xóa một người dùng khỏi hệ thống",
    params: "Path: username (string)",
    response: '{\n  "message": "User deleted successfully"\n}',
  },
  {
    method: "POST",
    path: "/change_password",
    group: "Auth",
    desc: "Thay đổi mật khẩu của người dùng",
    params: "Query: username (string)",
    requestBody:
      '{\n  "password": "old_password",\n  "new1_password": "new_password",\n  "new2_password": "confirm_new_password"\n}',
    response: '{\n  "message": "Password changed successfully"\n}',
  },
  {
    method: "POST",
    path: "/forgot_password/{email}",
    group: "Auth",
    desc: "Bắt đầu quy trình đặt lại mật khẩu cho một email",
    params: "Path: email (string)",
    response: '{\n  "message": "Password reset instructions sent"\n}',
  },
  {
    method: "GET",
    path: "/login_google",
    group: "Auth",
    desc: "Bắt đầu luồng đăng nhập SSO thông qua Google OAuth 2.0",
    response: "302 Redirect to Google Accounts login",
  },
  {
    method: "GET",
    path: "/auth",
    group: "Auth",
    desc: "URL callback để Google chuyển hướng đến sau khi xác thực",
    response: "Sets session cookie or redirects with tokens",
  },

  // 2. Datasets
  {
    method: "POST",
    path: "/upload-dataset",
    group: "Datasets",
    desc: "Tải lên một tập dữ liệu mới (lưu trữ trên MinIO Storage)",
    params: "Query: user_id (string)",
    requestBody:
      "multipart/form-data: file_data (binary), data_name (string), data_type (string)",
    response:
      '{\n  "_id": "64b...",\n  "dataName": "heart_disease",\n  "dataType": "tabular",\n  "userId": "usr_123"\n}',
  },
  {
    method: "GET",
    path: "/get-list-data-user",
    group: "Datasets",
    desc: "Lấy danh sách tất cả các tập dữ liệu từ tất cả người dùng",
    response:
      '[\n  {\n    "_id": "ds_01",\n    "dataName": "diabetes.csv",\n    "dataType": "tabular",\n    "createDate": 1720000000\n  }\n]',
  },
  {
    method: "POST",
    path: "/get-list-data-by-userid",
    group: "Datasets",
    desc: "Lấy danh sách các tập dữ liệu cho một người dùng cụ thể",
    params: "Query: id (string - userId)",
    response:
      '[\n  {\n    "_id": "ds_01",\n    "dataName": "churn_data.csv",\n    "dataType": "tabular",\n    "createDate": 1720000000\n  }\n]',
  },
  {
    method: "GET",
    path: "/get-data-info",
    group: "Datasets",
    desc: "Lấy thông tin chi tiết và siêu dữ liệu của một tập dữ liệu",
    params: "Query: id (string - datasetId)",
    response:
      '{\n  "_id": "ds_01",\n  "dataName": "heart.csv",\n  "dataType": "tabular",\n  "userId": "usr_123"\n}',
  },
  {
    method: "PUT",
    path: "/update-dataset/{dataset_id}",
    group: "Datasets",
    desc: "Cập nhật thông tin hoặc tệp của một tập dữ liệu",
    params: "Path: dataset_id (string)",
    requestBody:
      "multipart/form-data (tùy chọn): data_name, data_type, file_data",
    response: '{\n  "message": "Dataset updated successfully"\n}',
  },
  {
    method: "DELETE",
    path: "/delete-dataset/{dataset_id}",
    group: "Datasets",
    desc: "Xóa một tập dữ liệu khỏi cơ sở dữ liệu và MinIO Storage",
    params: "Path: dataset_id (string)",
    response: '{\n  "message": "Dataset deleted successfully"\n}',
  },

  // 3. Training & Inference
  {
    method: "POST",
    path: "/train-from-requestbody-json/",
    group: "Training & Inference",
    desc: "Bắt đầu một công việc huấn luyện mới dựa trên cấu hình JSON",
    params: "Query: userId (string), id_data (string)",
    requestBody:
      '{\n  "features": ["age", "sex", "chol"],\n  "target": "target",\n  "problem_type": "classification",\n  "metric_sort": "accuracy",\n  "choose": "all"\n}',
    response:
      '{\n  "job_id": "job_9841",\n  "status": "queued",\n  "message": "Job dispatched to Kafka queue"\n}',
  },
  {
    method: "POST",
    path: "/get-list-job-by-userId",
    group: "Training & Inference",
    desc: "Lấy danh sách tất cả các công việc huấn luyện của một người dùng",
    params: "Query: user_id (string)",
    response:
      '[\n  {\n    "_id": "job_01",\n    "job_id": "job_9841",\n    "status": "completed",\n    "best_score": 0.947\n  }\n]',
  },
  {
    method: "POST",
    path: "/get-job-info",
    group: "Training & Inference",
    desc: "Lấy thông tin chi tiết và bảng xếp hạng mô hình của một công việc",
    params: "Query: id (string - job_id)",
    response:
      '{\n  "_id": "job_01",\n  "job_id": "job_9841",\n  "best_model": "RandomForestClassifier",\n  "best_score": 0.947,\n  "status": "completed"\n}',
  },
  {
    method: "POST",
    path: "/inference-model/",
    group: "Training & Inference",
    desc: "Thực hiện suy luận (inference) bằng một mô hình đã được huấn luyện",
    params: "Query: job_id (string)",
    requestBody: "multipart/form-data: file_data (CSV file)",
    response: "File CSV hoặc JSON chứa các dự đoán của mô hình",
  },
  {
    method: "POST",
    path: "/activate-model",
    group: "Training & Inference",
    desc: "Kích hoạt hoặc vô hiệu hóa một mô hình đã được huấn luyện để suy luận",
    params: "Query: job_id (string), activate (0 hoặc 1)",
    response: '{\n  "message": "Model status updated successfully"\n}',
  },

  // 4. v2 AutoML APIs
  {
    method: "GET",
    path: "/v2/auto/features",
    group: "v2 AutoML",
    desc: "Lấy danh sách và trạng thái các features được phát hiện từ dataset",
    params: "Query: id_data (string), problem_type (string)",
    response: '{\n  "features": {\n    "age": true,\n    "income": true\n  }\n}',
  },
  {
    method: "GET",
    path: "/v2/auto/data",
    group: "v2 AutoML",
    desc: "Xem trước dữ liệu tập tin (Data Preview)",
    params: "Query: id_data (string)",
    response: '{\n  "rows": 100,\n  "data": [ ... ]\n}',
  },
  {
    method: "GET",
    path: "/v2/auto/metrics",
    group: "v2 AutoML",
    desc: "Lấy danh sách các metric đánh giá hợp lệ theo problem type",
    params: "Query: problem_type (classification | regression)",
    response:
      '{\n  "metrics": {\n    "accuracy": "Accuracy",\n    "f1": "F1-Score"\n  }\n}',
  },
  {
    method: "POST",
    path: "/v2/auto/jobs/training",
    group: "v2 AutoML",
    desc: "Bắt đầu công việc huấn luyện phân tán v2 qua Kafka",
    requestBody:
      '{\n  "datasetId": "ds_01",\n  "problemType": "classification",\n  "target": "label"\n}',
    response:
      '{\n  "status": "success",\n  "message": "Training job started",\n  "job_id": "job_v2_123"\n}',
  },
  {
    method: "GET",
    path: "/v2/auto/jobs/offset/{userId}",
    group: "v2 AutoML",
    desc: "Lấy danh sách các jobs của người dùng với phân trang (pagination)",
    params: "Path: userId, Query: page (number), limit (number)",
    response:
      '{\n  "total": 25,\n  "page": 1,\n  "limit": 5,\n  "items": [ ... ]\n}',
  },
  {
    method: "POST",
    path: "/v2/auto/{jobId}/predictions",
    group: "v2 AutoML",
    desc: "Chạy tác vụ suy luận trả về file kết quả CSV tải xuống",
    params: "Path: jobId (string)",
    requestBody: "multipart/form-data: file_data (CSV)",
    response: "Blob download: result.csv",
  },
];

export const QUICKSTART_STEPS = [
  {
    title: "Cách 1: Khởi chạy bằng Docker (Khuyến nghị)",
    desc: "Cách đơn giản và toàn diện nhất để chạy toàn bộ hệ thống gồm Next.js frontend, FastAPI backend, Worker cluster, MongoDB, MinIO và Kafka:",
    code: `# 1. Tải mã nguồn dự án
git clone https://github.com/optivisionlab/AutoML.git
cd AutoML

# 2. Cấu hình biến môi trường từ file mẫu
cp src/backend/temp.env src/backend/.env
cp src/frontend/temp.env src/frontend/.env

# 3. Khởi chạy toàn bộ môi trường
docker-compose up -d --build

# Để dừng hệ thống khi không sử dụng
docker-compose down`,
  },
  {
    title: "Cách 2: Triển khai từ mã nguồn (Backend & Workers)",
    desc: "Chạy cục bộ Backend FastAPI và Worker node kết nối đến cụm tính toán phân tán:",
    code: `cd AutoML/src/backend

# 1. Cài đặt các thư viện Python
pip install -r requirements.txt

# 2. Khởi chạy API server
python app.py

# 3. Mở thêm một terminal khác để kích hoạt Worker xử lý tác vụ
python -m cluster.worker`,
  },
  {
    title: "Cách 3: Triển khai Frontend Web UI",
    desc: "Chạy ứng dụng giao diện người dùng Next.js 15 ở môi trường phát triển:",
    code: `cd AutoML/src/frontend

# 1. Cài đặt các gói phụ thuộc
npm install

# 2. Khởi chạy ứng dụng ở chế độ phát triển
npm run dev

# 3. Truy cập tại: http://localhost:3000
# Backend API hoạt động tại: http://localhost:8000`,
  },
];

export const TOP_NAV_TABS_EN = [
  { id: "overview", label: "Home" },
  { id: "getting-started", label: "Getting Started" },
  { id: "architecture", label: "Architecture" },
  { id: "scientific-approach", label: "Scientific Approach" },
  { id: "backend-api", label: "API Docs" },
  { id: "releases", label: "Releases" },
  { id: "citation-license", label: "Citation & License" },
];

export const DOC_CATEGORIES_EN: DocCategory[] = [
  {
    id: "getting-started",
    title: "GETTING STARTED",
    items: [
      { id: "overview", title: "Home (Overview)", icon: "BookOpen" },
      {
        id: "getting-started",
        title: "Quickstart Guide",
        badge: "Core",
        icon: "Rocket",
      },
      {
        id: "first-training",
        title: "First Model Training",
        icon: "PlayCircle",
      },
    ],
  },
  {
    id: "architecture",
    title: "SYSTEM ARCHITECTURE",
    items: [
      {
        id: "architecture",
        title: "Microservices Architecture",
        badge: "v2.2",
        icon: "Boxes",
      },
      {
        id: "distributed-computing",
        title: "Distributed Computing & Workers",
        icon: "Cpu",
      },
    ],
  },
  {
    id: "scientific-approach",
    title: "SCIENTIFIC APPROACH",
    items: [
      {
        id: "scientific-approach",
        title: "AutoML Pipeline & Preprocessing",
        icon: "Workflow",
      },
      {
        id: "hpo-tuning",
        title: "Hyperparameter Optimization (HPO)",
        icon: "Sliders",
      },
      {
        id: "evaluation-metrics",
        title: "Evaluation & Model Metrics",
        icon: "LineChart",
      },
    ],
  },
  {
    id: "api-reference",
    title: "API REFERENCE",
    items: [
      {
        id: "backend-api",
        title: "Backend API (FastAPI)",
        badge: "FastAPI",
        icon: "Code2",
      },
      {
        id: "api-auth",
        title: "Authentication & Users (Auth)",
        icon: "ShieldCheck",
      },
      {
        id: "api-datasets",
        title: "Dataset Management (Data API)",
        icon: "Database",
      },
      {
        id: "api-training-inference",
        title: "Training & Inference",
        icon: "Zap",
      },
    ],
  },
  {
    id: "resources",
    title: "RESOURCES & RELEASES",
    items: [
      {
        id: "releases",
        title: "Release History & Changelog",
        badge: "v2.2.0",
        icon: "History",
      },
      {
        id: "citation-license",
        title: "Citation & License",
        icon: "FileText",
      },
    ],
  },
];

export const FEATURE_CARDS_EN: FeatureCard[] = [
  {
    id: "datasets",
    title: "Dataset Management",
    desc: "Intuitive interface to upload, preview, update, and delete datasets, with automated format detection and integrity verification.",
    icon: "Database",
    topicId: "api-datasets",
    tag: "Data Ops",
  },
  {
    id: "models",
    title: "Automated AutoML Pipeline",
    desc: "Intelligent preprocessing, automated hyperparameter search (Grid, Random, Bayes, GA), and performance benchmarking.",
    icon: "BrainCircuit",
    topicId: "scientific-approach",
    tag: "Core AI",
  },
  {
    id: "deployments",
    title: "Deployment & Inference",
    desc: "Simple REST API to activate or deactivate trained models and make real-time batch predictions on new CSV data.",
    icon: "Rocket",
    topicId: "api-training-inference",
    tag: "Production",
  },
  {
    id: "architecture",
    title: "Microservices Architecture",
    desc: "Distributed microservices powered by Apache Kafka message queues, MinIO Object Storage, MongoDB, and parallel Workers.",
    icon: "Boxes",
    topicId: "architecture",
    tag: "Distributed",
  },
  {
    id: "backend-api",
    title: "Backend API Docs",
    desc: "Complete REST API catalogue built with FastAPI, providing detailed schemas for parameters, request bodies, and responses.",
    icon: "Code2",
    topicId: "backend-api",
    tag: "FastAPI REST",
  },
  {
    id: "citation",
    title: "Scientific Publication",
    desc: "Research paper published in Springer Nature ISINC 2026. Official BibTeX citation support for academic research.",
    icon: "Sparkles",
    topicId: "citation-license",
    tag: "Springer Nature",
  },
];

export const QUICKSTART_STEPS_EN = [
  {
    title: "Method 1: Docker Compose (Recommended)",
    desc: "The fastest and most complete way to run Next.js, FastAPI, Worker cluster, MongoDB, MinIO, and Kafka:",
    code: `# 1. Clone repository
git clone https://github.com/optivisionlab/AutoML.git
cd AutoML

# 2. Configure environment from templates
cp src/backend/temp.env src/backend/.env
cp src/frontend/temp.env src/frontend/.env

# 3. Launch full stack in background
docker-compose up -d --build

# To stop the system
docker-compose down`,
  },
  {
    title: "Method 2: Local Source (Backend & Workers)",
    desc: "Run FastAPI backend and background Worker nodes connecting to the distributed compute cluster:",
    code: `cd AutoML/src/backend

# 1. Install Python requirements
pip install -r requirements.txt

# 2. Start API server
python app.py

# 3. Open another terminal to activate the Worker node
python -m cluster.worker`,
  },
  {
    title: "Method 3: Frontend Web UI",
    desc: "Run the Next.js 15 web application in local development mode:",
    code: `cd AutoML/src/frontend

# 1. Install npm dependencies
npm install

# 2. Start development server
npm run dev

# 3. Access at: http://localhost:3000
# Backend API available at: http://localhost:8000`,
  },
];

export function getTopNavTabs(locale: string = "vi") {
  return locale === "en" ? TOP_NAV_TABS_EN : TOP_NAV_TABS;
}

export function getDocCategories(locale: string = "vi") {
  return locale === "en" ? DOC_CATEGORIES_EN : DOC_CATEGORIES;
}

export function getFeatureCards(locale: string = "vi") {
  return locale === "en" ? FEATURE_CARDS_EN : FEATURE_CARDS;
}

export function getQuickstartSteps(locale: string = "vi") {
  return locale === "en" ? QUICKSTART_STEPS_EN : QUICKSTART_STEPS;
}

