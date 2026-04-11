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
- Giao diện người dùng: http://localhost:3000
- Backend API: http://localhost:8000

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
