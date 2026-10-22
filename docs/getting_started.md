# Bắt đầu

HAutoML có thể chạy bằng Docker Compose (khuyến nghị) hoặc chạy từng thành phần từ mã nguồn.

## Yêu cầu hệ thống

- **Python** ≥ 3.10 (backend)
- **Node.js** (frontend)
- **Hạ tầng**: MongoDB (27017), Apache Kafka (9092), MinIO (9000/9001), Mosquitto MQTT (1883/1884)
- [Docker](https://www.docker.com/get-started) và [Docker Compose](https://docs.docker.com/compose/install/) nếu dùng cách triển khai bằng Docker

---

## 1. Tải mã nguồn

```bash
git clone https://github.com/optivisionlab/AutoML.git
cd AutoML
```

## 2. Cấu hình môi trường

```bash
cp src/backend/.env.example src/backend/.env
cp src/frontend/apps/web/temp.env src/frontend/apps/web/.env
```

Giải thích các biến môi trường của backend ở [mục 5](#5-bien-moi-truong).

---

## 3. Chạy bằng Docker Compose (khuyến nghị)

Compose của backend nằm ở `src/backend/deploy/` và khởi chạy cả API, training consumer, Demo UI cùng MongoDB, MinIO, Kafka và MQTT.

```bash
cd src/backend/deploy
docker compose up -d --build
```

Dừng hệ thống:

```bash
docker compose down
```

| Dịch vụ | Container | Cổng |
|---------|-----------|------|
| Backend API | `hautoml_service` | `9999` (đổi bằng `PORT_BACK_END`) |
| Training consumer | `hautoml_consumer` | – |
| Demo UI (Gradio) | `hautoml_toolkit` | `7860` (đổi bằng `DEMO_PORT`) |
| MQTT | `mqtt_broker` | `1883`, `1884` |
| MinIO | – | `9000`, `9001` (console) |
| Kafka | – | `9092`, `9093` |
| MongoDB | – | `27017` |

!!! important "Không dùng `localhost` giữa các container"
    Trong Docker, các dịch vụ gọi nhau bằng tên dịch vụ, không phải `localhost`. File compose đã ghi đè sẵn `MONGODB_CONNECT`, `MINIO_ENDPOINT`, `KAFKA_SERVER` và `MQTT_HOSTNAME` cho container backend. Nếu tự thêm biến kết nối, hãy dùng tên dịch vụ trong `docker-compose.yml`.

Muốn chạy cả frontend (cổng 3000) và agent (cổng 9500) cùng backend, dùng `docker-compose.yaml` ở thư mục gốc repo: `docker compose up -d --build`. Frontend build từ `src/frontend/Dockerfile`.

---

## 4. Chạy từ mã nguồn

### Backend

Tại thư mục `src/backend`:

```bash
# Tạo môi trường ảo và cài thư viện
python3 -m venv venv
source venv/bin/activate        # Windows: .\venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

Khởi động các dịch vụ hạ tầng nếu chưa có (MongoDB, MinIO, Kafka, MQTT):

```bash
cd deploy
docker compose up -d mongo minio kafka mqtt
cd ..
```

Backend gồm hai tiến trình chạy song song, mở hai terminal:

```bash
# Terminal 1: API server
python -m src.main
# hoặc: uvicorn src.main:app --host 0.0.0.0 --port 9996 --reload

# Terminal 2: training consumer (nhận job từ Kafka)
python -m src.kafka_consumer
```

!!! note
    API chạy ở cổng `BACKEND_PORT` trong `.env` (mặc định `9996` theo `.env.example`). Swagger UI có tại `http://localhost:9996/docs`.

### Demo UI (tùy chọn)

Giao diện Gradio để thử nhanh tiền xử lý và tìm kiếm mô hình, không cần hạ tầng:

```bash
python -m demo.app      # http://localhost:7860
```

### Cụm PyMapReduce (tùy chọn, nhiều máy)

Đặt `MAPREDUCE_MODE=cluster` và `MAPREDUCE_HEAD_ADDRESS` trong `.env`, sau đó:

```bash
# Máy chủ head
./deploy/start_head.sh --port 7777 --scheduler Adaptive

# Mỗi máy worker
./deploy/start_worker.sh --head-addr <ip-head>:7777

# Dừng cụm
./deploy/stop_cluster.sh
```

Chế độ mặc định `MAPREDUCE_MODE=local` chạy tác vụ ngay trên máy hiện tại.

### Frontend

Tại thư mục `src/frontend`:

```bash
npm install
npm run dev        # http://localhost:3000
```

Các biến chính trong `src/frontend/apps/web/.env`:

| Biến | Mô tả |
|------|-------|
| `NEXT_PUBLIC_BASE_API` | URL backend, ví dụ `http://localhost:9996/api/v1` |
| `NEXTAUTH_URL`, `NEXTAUTH_SECRET` | Cấu hình NextAuth |
| `NEXT_PUBLIC_MQTT_URL`, `NEXT_PUBLIC_MQTT_USERNAME`, `NEXT_PUBLIC_MQTT_PASSWORD` | Kết nối MQTT để nhận thông báo realtime |
| `NEXT_PUBLIC_TIMEOUT_CAROUSEL` | Thời gian chuyển slide (ms) |

### Địa chỉ truy cập

- Giao diện người dùng: <http://localhost:3000>
- Backend API: <http://localhost:9996> (chạy từ mã nguồn) hoặc <http://localhost:9999> (Docker)
- Swagger UI: `<địa chỉ backend>/docs`

---

## 5. Biến môi trường { #5-bien-moi-truong }

Backend đọc cấu hình từ `src/backend/.env` (xem [settings.py](https://github.com/optivisionlab/AutoML/blob/main/src/backend/src/config/settings.py)).

**Lưu trữ và cơ sở dữ liệu**

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `MONGODB_CONNECT` | `localhost:27017` | Địa chỉ MongoDB |
| `MINIO_ENDPOINT` | `localhost:9000` | Địa chỉ MinIO (dataset, model) |
| `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` | `admin`, `password123` | Thông tin đăng nhập MinIO |
| `BACKBLAZE_ACCESS_KEY_ID`, `BACKBLAZE_SECRET_ACCESS_KEY` | – | Khóa Backblaze B2 (avatar, thumbnail) |
| `BACKBLAZE_ENDPOINT_URL`, `BACKBLAZE_BUCKET_NAME` | –, `hautoml-storage` | Endpoint và bucket |
| `BACKBLAZE_MAX_FILE_SIZE_MB` | `10` | Kích thước tối đa của file tải lên |

**Hàng đợi và thông báo**

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `KAFKA_SERVER` | `localhost:9092` | Địa chỉ Kafka broker |
| `KAFKA_TOPIC` | `train-job-topic` | Topic chứa job huấn luyện |
| `MQTT_HOSTNAME`, `MQTT_PORT` | `localhost`, `1883` | Địa chỉ MQTT broker |
| `MQTT_USERNAME`, `MQTT_PASSWORD` | `admin`, `Admin@123` | Thông tin đăng nhập MQTT |

**Huấn luyện phân tán (PyMapReduce)**

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `MAPREDUCE_MODE` | `local` | `local` hoặc `cluster` |
| `MAPREDUCE_HEAD_ADDRESS` | `localhost:7777` | Địa chỉ head node (chế độ `cluster`) |
| `MAPREDUCE_WORKER_IDLE_TIMEOUT` | `0` | Số giây tối đa một tiến trình worker rảnh trước khi bị thu hồi |
| `MAPREDUCE_ACTOR_IDLE_TIMEOUT` | `0` | Số giây tối đa giữ mô hình trong RAM worker khi không có yêu cầu dự đoán |

**Bảo mật và xác thực**

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `SECRET_KEY` | – | Khóa ký JWT. Đặt một chuỗi ngẫu nhiên dài |
| `ALGORITHM` | `HS256` | Thuật toán ký JWT |
| `ACCESS_EXPIRE` | `15` | Thời hạn access token (phút) |
| `REFRESH_EXPIRE` | `7` | Thời hạn refresh token (ngày) |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | – | Thông tin ứng dụng từ Google Cloud Console |
| `REDIRECT_URI` | `http://localhost:9996` | Gốc URL callback của Google OAuth |
| `FRONTEND_URL` | `http://localhost:3000` | URL frontend để chuyển hướng sau khi xác thực |
| `BACKEND_CORS_ORIGINS` | `localhost:3000, 5173` | Danh sách origin được phép gọi API |

**Email**

| Biến | Mô tả |
|------|-------|
| `MAIL_USERNAME` | Tài khoản email gửi thông báo (ví dụ Gmail) |
| `MAIL_PASSWORD` | Mật khẩu ứng dụng (app password), không phải mật khẩu chính |
| `MAIL_LOGO` | URL logo hiển thị trong email |

**Địa chỉ backend**

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `BACKEND_HOST` | `localhost` | Địa chỉ lắng nghe. Dùng `0.0.0.0` để nhận kết nối từ bên ngoài, `::` để nhận cả IPv4 và IPv6 |
| `BACKEND_PORT` | `9999` | Cổng API (`.env.example` đặt `9996`) |

---

## 6. Kiểm tra hệ thống

1. Gọi health check: `curl http://localhost:9996/` sẽ trả về `{"project": "HAutoML", "version": "...", "status": "Running"}`.
2. Mở Swagger UI tại `/docs` và thử `POST /api/v1/auth/signup`.
3. Xem log consumer để chắc chắn nó đã nhận job:

    ```bash
    docker logs -f hautoml_consumer
    ```

4. Mở giao diện tại <http://localhost:3000>.

## 7. Chạy kiểm thử

Tại thư mục `src/backend`:

```bash
pytest tests/unit
pytest tests/integration
```

---

## Xem tài liệu trên máy local

```bash
pip install mkdocs-material
mkdocs serve
```

Mở `http://127.0.0.1:8000`. Máy chủ tự tải lại khi bạn lưu thay đổi trong các file Markdown.
