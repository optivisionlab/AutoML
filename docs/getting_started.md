## Bắt đầu
---

### Cách đơn giản nhất: Sử dụng Docker

Cách được khuyến nghị nhất để chạy toàn bộ hệ thống là sử dụng Docker và Docker Compose.

**Yêu cầu**: [Docker](https://www.docker.com/get-started) và [Docker Compose](https://docs.docker.com/compose/install/)

---

### Triển khai từ mã nguồn

**1. Tải mã nguồn dự án**
```bash
git clone https://github.com/optivisionlab/AutoML.git
cd AutoML
```

**2. Cấu hình môi trường**
```bash
cp src/backend/temp.env src/backend/.env
cp src/frontend/temp.env src/frontend/.env
```

**3. Khởi chạy các thành phần hệ thống**
> **Backend & Worker cluster**
> 
> Tại thư mục: AutoML/src/backend
```bash
pip install -r requirements.txt # Cài đặt các thư viện cần thiết

python app.py # Khởi chạỵ API server
python -m cluster.worker # Kích hoạt worker xử lý tác vụ
```

> **Frontend**
> 
> Tại thư mục: AutoML/src/frontend
```bash
npm install # Cài đặt các gói phụ thuộc
npm run dev # Chạy ứng dụng ở chế độ phát triển
```

**4. Địa chỉ truy cập**
- Giao diện người dùng: [http://localhost:3000](http://localhost:3000)

- Backend API: [http://localhost:8000](http://localhost:8000)

---

### Triển khai qua docker
> **Tự động hóa việc thiết lập và khởi chạy toàn bộ môi trường**
> 
> Tại thư mục: AutoML/
```bash
docker-compose up -d --build
```

> **Để dừng hệ thống**
```bash
docker-compose down
```

**5. Giải thích biến môi trường**
> Hệ thống sử dụng các biến môi trường để linh hoạt giữa các chế độ chạy (local hoặc docker).

**A. Cấu hình hạ tầng (Infrastructure)**
> Dành cho việc kết nối đến các dịch vụ lưu trữ và hàng đợi
- ```MINIO_ENDPOINT```: Địa chỉ server MinIO (mặc định: ```localhost:9000```). Nếu chạy docker, hãy đổi thành ```minio:9000```.

- ```KAFKA_SERVER```: Địa chỉ broker Kafka. Dùng ```kafka:9092``` trong môi trường docker.

- ```MONGODB_CONNECT```: Chuỗi kết nối database. Nếu dùng docker thì dùng ```mongodb:27017```.

**B. Cấu hình phân tán (Master - Worker)**
> Đây là phần cốt lõi để hệ thống AutoML có thể chạy đa máy (Distributed).
- ```HOST_BACK_END```: Địa chỉ API Server sẽ lắng nghe. Nên để ```0.0.0.0``` để chấp nhận kết nối từ các Worker bên ngoài.

- ```WORKER_LIST```: Danh sách các địa chỉ Worker và Master quản lý.

- ```TASK_TIMEOUT_SECONDS```: Thời gian tối đa (giây) chờ một tác vụ training. Sau thời gian này, Master sẽ coi Worker đã chết hoặc tác vụ bị treo.

- ```MAX_TASK_SNOOZES```: Số lần cho phép thử lại (retry) một tác vụ trước khi đánh dấu là thất bại.

**C. Bảo mật và xác thực (Security & Auth)**
- ```SECRET_KEY```: Chuỗi ký tự dùng để mã hóa JWT Token. Nên tạo 1 chuỗi ngẫu nhiên dài để bảo mật.

- ```GOOGLE_CLIENT_ID```/```GOOGLE_CLIENT_SECRET```: Thông tin định danh ứng dụng lấy từ Google Cloud Console để kích hoạt tính năng đăng nhập bằng Google.

- ```ACCESS_EXPIRE```: Thời gian của Token đăng nhập (tính bằng phút).

**D. Dịch vụ Email (Notification)**
- ```MAIL_USERNAME```: Email dùng để gửi thông báo (ví dụ: gmail).

- ```MAIL_PASSWORD```: Mật khẩu ứng dụng (app password) của Gmail, không phải mật khẩu tài khoản chính.

> [!IMPORTANT]
>
> **Quy tắc về localhost trong Docker**
> 
> Nếu chạy hệ thống bằng docker, tuyệt đối không sử dụng ```localhost``` cho các biến kết nối giữa các dịch vụ (như ```MONGODB_CONNECT``` hay ```KAFKA_SERVER```)
>
> Thay vào đó, hãy sử dụng tên dịch vụ được định nghĩa trong file ```docker-compose.yaml``` (ví dụ: ```mongodb```, ```kafka```)

**6. Kiểm tra trạng thái hệ thống**
> Sau khi khởi chạy, bạn có thể kiểm tra xem các thành phần đã thông với nhau chưa bằng cách:
> 
> 1. Truy cập vào Dashboard tại: ```http://localhost:3000```
>
> 2. Kiểm tra log của Master để xem các worker đã đăng ký thành công chưa: ```docker logs -f hautoml-toolkit```

---

## Xem tài liệu trên máy Local

Trước khi triển khai, bạn có thể xem trước trang web tài liệu trên máy tính của mình.

1.  **Cài đặt các gói cần thiết (chỉ cần làm một lần):**
    Mở terminal và chạy lệnh sau để cài đặt MkDocs và theme Material:
    ```bash
    pip install mkdocs-material
    ```

2.  **Chạy máy chủ phát triển:**
    Từ thư mục gốc của dự án, chạy lệnh:
    ```bash
    mkdocs serve
    ```

3.  **Xem trang tài liệu:**
    Mở trình duyệt và truy cập vào địa chỉ `http://127.0.0.1:8000`. Máy chủ này có tính năng tự động tải lại (live-reloading), có nghĩa là bất kỳ khi nào bạn lưu một thay đổi trong các tệp Markdown, trang web trên trình duyệt sẽ tự động cập nhật.
